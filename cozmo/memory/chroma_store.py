from datetime import datetime
import chromadb
from uuid import uuid4
from langchain_ollama import OllamaEmbeddings


class ChromaStore:
    def __init__(self, collection_name: str, persist_dir: str, model: str | None = None):
        if model is None:
            from ..ollama_util import get_ollama_models, pick_model
            installed = get_ollama_models()
            model = pick_model(installed, "embedding") or "nomic-embed-text:latest"
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

    def hybrid_search(
        self,
        query: str,
        k: int = 5,
        distance_threshold: float | None = None,
        keyword_boost: float = 0.3,
    ) -> list[dict]:
        """Search combining ChromaDB cosine similarity with keyword matching boost.

        Results from similarity search are re-scored: documents containing
        query keywords get a boost (lower distance = better).
        """
        sim_results = self.similarity_search(query, k=k * 2, distance_threshold=distance_threshold)
        if not sim_results:
            return []

        keywords = set(query.lower().split())
        for item in sim_results:
            text_lower = item["text"].lower()
            keyword_hits = sum(1 for kw in keywords if kw in text_lower)
            boost = (keyword_hits / max(len(keywords), 1)) * keyword_boost
            item["distance"] = max(0, item["distance"] - boost)

        sim_results.sort(key=lambda x: x["distance"])
        return sim_results[:k]

    def search_with_importance(
        self,
        query: str,
        k: int = 5,
        distance_threshold: float | None = None,
    ) -> list[dict]:
        """Search with importance scoring: recency + relevance + frequency boost."""
        results = self.hybrid_search(query, k=k * 2, distance_threshold=distance_threshold)
        if not results:
            return []

        now = datetime.now()
        for item in results:
            meta = item["metadata"]
            score = 1.0 - item["distance"]

            # Recency boost: newer memories score higher
            ts = meta.get("timestamp", "")
            if ts:
                try:
                    mem_time = datetime.fromisoformat(ts)
                    days_old = (now - mem_time).days
                    recency = max(0, 1.0 - (days_old / 30.0))  # 30-day decay
                    score = score * 0.7 + recency * 0.3
                except ValueError:
                    pass

            # Frequency boost: memories referenced more score higher
            freq = meta.get("frequency", 1)
            if freq > 1:
                freq_boost = min(0.15, (freq - 1) * 0.02)
                score += freq_boost

            item["score"] = round(score, 4)

        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results[:k]

    def increment_frequency(self, id: str):
        """Increment frequency counter for a memory (boost importance)."""
        try:
            results = self.collection.get(ids=[id], include=["metadatas"])
            if results and results.get("metadatas"):
                meta = results["metadatas"][0]
                freq = meta.get("frequency", 1) + 1
                meta["frequency"] = freq
                self.collection.update(ids=[id], metadatas=[meta])
        except Exception:
            pass

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        distance_threshold: float | None = None,
    ) -> list[dict]:
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
        items = [
            {"text": d, "metadata": m, "distance": dist}
            for d, m, dist in zip(docs, metas, dists)
        ]
        if distance_threshold is not None:
            items = [i for i in items if i["distance"] < distance_threshold]
        return items

    def count(self) -> int:
        return self.collection.count()

    def list_all(self, limit: int = 100) -> list[dict]:
        """Return all stored documents with metadata."""
        count = self.collection.count()
        if count == 0:
            return []
        results = self.collection.get(
            limit=min(limit, count),
            include=["documents", "metadatas"],
        )
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])
        ids = results.get("ids", [])
        return [
            {"id": id_, "text": doc, "metadata": meta}
            for id_, doc, meta in zip(ids, docs, metas)
        ]

    def delete(self, id: str) -> bool:
        """Delete a document by ID."""
        try:
            self.collection.delete(ids=[id])
            return True
        except Exception:
            return False
