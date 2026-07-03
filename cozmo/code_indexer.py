from pathlib import Path
from .memory.chroma_store import ChromaStore

IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".cozmo", "target", "build", "dist"}

class ProjectIndex:
    def __init__(self, project_root: str | Path):
        self.root = Path(project_root).resolve()
        self.store = ChromaStore(
            persist_dir=str(self.root / ".cozmo" / "project_index"),
            collection_name="project_index",
        )
    
    def index_all(self):
        """Walk project dir, chunk files, store in CHroma."""
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
            self.store.add_texts(
                texts=[d["text"] for d in docs],
                metadatas=[d["metadata"] for d in docs],
            )
        return len(docs)
    
    def query(self, query: str, k: int = 3) -> str:
        """Search project index, return concise snippets."""
        results = self.store.similarity_search(query, k=k)
        if not results:
            return ""
        parts = []
        for r in results:
            path = r["metadata"].get("path", "?")
            text = r["text"][:300]
            parts.append(f"--- {path} ---\n{text}")
        return "\n".join(parts)
