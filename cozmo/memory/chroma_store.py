import chromadb
from uuid import uuid4
from langchain_ollama import OllamaEmbeddings


class ChromaStore:
    def __init__(self, collection_name: str, persist_dir: str, model="nomic-embed-text:latest"):
        self.embedding = OllamaEmbeddings(model=model)
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_texts(self, texts: list[str], metadatas: list[dict] | None = None):
        ids = [str(uuid4()) for _ in texts]
        self.collection.add(
            documents=texts,
            metadatas=metadatas or [{}] * len(texts),
            ids=ids,
        )

    def similarity_search(self, query: str, k: int = 5) -> list[dict]:
        count = self.collection.count()
        if count == 0:
            return []
        results = self.collection.query(
            query_texts=[query],
            n_results=min(k, count),
        )
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]
        return [
            {"text": d, "metadata": m, "distance": dist}
            for d, m, dist in zip(docs, metas, dists)
        ]

    def count(self) -> int:
        return self.collection.count()
