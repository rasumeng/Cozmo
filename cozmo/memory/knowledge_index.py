"""
KnowledgeIndex — indexes knowledge base files into LanceStore for semantic search.

Scans the knowledge/ directory (OKF markdown files with YAML frontmatter),
embeds them with Sentence Transformers, and makes them searchable.

Supports:
  - Overlapping chunking
  - Cross-encoder reranking
  - Hybrid retrieval (vector + keyword boost)
  - Metadata-preserving search
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from sentence_transformers import SentenceTransformer

from .lancedb_store import LanceStore

log = logging.getLogger("cozmo.memory.knowledge")

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def _parse_okf(filepath: Path) -> tuple[dict, str]:
    """Parse an OKF markdown file. Returns (metadata, body)."""
    text = filepath.read_text("utf-8", errors="replace")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {"type": "Reference", "title": filepath.stem, "tags": []}, text

    import yaml
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except Exception:
        meta = {}
    body = text[m.end():].strip()
    return meta, body


_global_knowledge_index: "KnowledgeIndex | None" = None


def init_knowledge_index(knowledge_dir: str | Path, persist_dir: str | Path | None = None) -> "KnowledgeIndex":
    global _global_knowledge_index
    ki = KnowledgeIndex(knowledge_dir=knowledge_dir, persist_dir=persist_dir)
    ki.index_all()
    _global_knowledge_index = ki
    return ki


def get_knowledge_index() -> "KnowledgeIndex | None":
    return _global_knowledge_index


def _chunk_with_overlap(text: str, max_chars: int = 1000, overlap_chars: int = 150) -> list[str]:
    """Split text into overlapping chunks at paragraph boundaries."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return [text[:max_chars]] if text else []

    chunks = []
    current = ""
    for p in paragraphs:
        para_len = len(p)
        if not current and para_len > max_chars:
            # Single paragraph exceeds max_chars — force-split mid-paragraph
            chunks.append(p)
            continue

        candidate = (current + "\n\n" + p).strip() if current else p
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # Carry overlap from previous chunk
            if overlap_chars and overlap_chars < len(current):
                overlap_start = -overlap_chars
                nl = current.rfind("\n", overlap_start)
                overlap_text = current[nl:] if nl >= len(current) + overlap_start else current[overlap_start:]
            elif overlap_chars:
                overlap_text = current
            else:
                overlap_text = ""
            current = overlap_text + "\n\n" + p if overlap_text else p

    if current:
        chunks.append(current)

    return chunks


class Reranker:
    """Cross-encoder reranker. Lazy-loaded model, cached across calls."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)

    def rerank(self, query: str, results: list[dict], k: int = 5) -> list[dict]:
        """Rerank results by cross-encoder relevance score."""
        if not results:
            return results
        try:
            self._load()
            pairs = [(query, r["text"]) for r in results]
            scores = self._model.predict(pairs)
            for i, s in enumerate(scores):
                results[i]["score"] = round(float(s), 4)
                results[i]["rerank_score"] = round(float(s), 4)
            results.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
            return results[:k]
        except Exception as e:
            log.warning("reranker failed, falling back: %s", e)
            return results[:k]


class KnowledgeIndex:
    """Indexes knowledge base files for semantic search with RAG pipeline.

    Args:
        knowledge_dir: Path to the knowledge base directory
        persist_dir: LanceDB storage directory
        embed_model: Sentence Transformer model name
        rerank_model: Cross-encoder model name (or None to disable reranking)
    """

    def __init__(
        self,
        knowledge_dir: str | Path = "./knowledge",
        persist_dir: Optional[str | Path] = None,
        embed_model: str = "all-MiniLM-L6-v2",
        rerank_model: Optional[str] = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    ):
        self.knowledge_dir = Path(knowledge_dir).resolve()
        self._embedder = SentenceTransformer(embed_model)
        embed_dim = self._embedder.get_sentence_embedding_dimension() or 384

        def embed(text: str) -> list[float]:
            return self._embedder.encode(text, normalize_embeddings=True).tolist()

        index_dir = Path(persist_dir) if persist_dir else Path.home() / ".cozmo" / "knowledge_index"
        self.store = LanceStore(
            uri=str(index_dir / "lancedb"),
            table_name="knowledge_index",
            embed_func=embed,
            embed_dim=embed_dim,
        )
        self._indexed_files: dict[str, float] = {}
        self._reranker = Reranker(rerank_model) if rerank_model else None

    def index_all(self, force: bool = False):
        """Index all knowledge files. Skips files with unchanged mtime."""
        if not self.knowledge_dir.is_dir():
            self.knowledge_dir.mkdir(parents=True, exist_ok=True)
            log.info("created knowledge directory at %s", self.knowledge_dir)
            return

        count = 0
        for f in sorted(self.knowledge_dir.rglob("*.md")):
            try:
                rel = str(f.relative_to(self.knowledge_dir))
                mtime = f.stat().st_mtime
                if not force and rel in self._indexed_files and self._indexed_files[rel] == mtime:
                    continue
                self.index_file(f, rel)
                self._indexed_files[rel] = mtime
                count += 1
            except Exception as e:
                log.warning("failed to index %s: %s", f, e)

        if count:
            log.info("indexed %d knowledge file(s)", count)

    def index_file(self, path: Path, rel: Optional[str] = None):
        """Index a single knowledge file."""
        if rel is None:
            rel = str(path.relative_to(self.knowledge_dir))
        meta, body = _parse_okf(path)
        title = meta.get("title", path.stem)
        tags = meta.get("tags", [])

        existing = self.store.query_sql(f"id LIKE '{rel}%'")
        for e in existing:
            self.store.delete(e.get("id", ""))

        chunks = _chunk_with_overlap(body)
        for i, chunk in enumerate(chunks):
            metadata = {
                "path": rel,
                "title": title,
                "tags": tags,
                "type": "knowledge",
                "chunk": i,
                "total_chunks": len(chunks),
                "timestamp": meta.get("timestamp", datetime.now().isoformat()),
            }
            self.store.add_texts([chunk], [metadata])

    def search(self, query: str, k: int = 5, rerank: bool = True) -> list[dict]:
        """Search knowledge base. Returns ranked results with metadata.

        Pipeline: vector search → cross-encoder rerank (if enabled).
        """
        # Fetch more candidates for reranking
        fetch_k = k * 3 if (rerank and self._reranker) else k
        results = self.store.search_with_importance(query, k=fetch_k)
        if not results:
            return []

        if rerank and self._reranker:
            results = self._reranker.rerank(query, results, k=k)

        # Normalize scores to 0-1 for consistent output
        if results and "rerank_score" in results[0]:
            scores = [r.get("rerank_score", 0) for r in results]
            if scores:
                max_s = max(scores)
                if max_s > 0:
                    for r in results:
                        r["score"] = round(max(0, r.get("rerank_score", 0) / max_s), 4)

        return results[:k]

    def search_by_tag(self, tag: str, k: int = 20) -> list[dict]:
        """Search knowledge base by tag."""
        return self.store.query_sql(
            f"metadata LIKE '%\"tags\": [%\"{tag}\"%]%' OR metadata LIKE '%\"tags\": [\"{tag}\"%'"
        )[:k]

    def count(self) -> int:
        return self.store.count()

    def get_paths(self) -> set[str]:
        all_items = self.store.list_all(limit=5000)
        return {item["metadata"].get("path", "") for item in all_items if "metadata" in item}
