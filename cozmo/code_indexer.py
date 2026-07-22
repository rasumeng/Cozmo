from pathlib import Path
from sentence_transformers import SentenceTransformer
from .memory.lancedb_store import LanceStore

IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".cozmo", "target", "build", "dist"}


class ProjectIndex:
    """Project code index using LanceDB + Sentence Transformers.

    Indexes project files as chunked documents for semantic code search.
    """

    def __init__(self, project_root: str | Path, embed_model: str = "all-MiniLM-L6-v2"):
        self.root = Path(project_root).resolve()
        self._embedder = SentenceTransformer(embed_model)

        def embed(text: str) -> list[float]:
            return self._embedder.encode(text, normalize_embeddings=True).tolist()

        self.store = LanceStore(
            uri=str(self.root / ".cozmo" / "project_index"),
            table_name="project_index",
            embed_func=embed,
            embed_dim=self._embedder.get_sentence_embedding_dimension() or 384,
        )

    def index_all(self):
        docs = []
        for f in self.root.rglob("*"):
            if not f.is_file():
                continue
            if any(part in IGNORE_DIRS for part in f.parts):
                continue
            if f.name.startswith("."):
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            rel = str(f.relative_to(self.root))
            docs.append({"id": rel, "text": text, "metadata": {"path": rel}})
        if docs:
            texts = [d["text"] for d in docs]
            metas = [d["metadata"] for d in docs]
            self.store.add_texts(texts, metas)

    def query(self, text: str, k: int = 5) -> str:
        results = self.store.similarity_search(text, k=k)
        if not results:
            return ""
        return "\n".join(
            f"- {r['metadata'].get('path', '?')}: {r['text'][:500]}"
            for r in results
        )
