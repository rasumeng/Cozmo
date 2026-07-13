from datetime import datetime
from .chroma_store import ChromaStore


SUMMARIZE_PROMPT = """Condense the following conversation into 2-3 sentences.
Capture key facts, user preferences, and any actionable items.
Do not include greetings or small talk.

Conversation:
{text}

Summary:"""

MEMORY_TYPES = {
    "conversation": "Conversation summaries from chat sessions",
    "preference": "User preferences and settings",
    "project": "Project context and file structure",
    "fact": "Learned facts and references",
}

SIMILARITY_THRESHOLD = 0.85  # Above this cosine similarity = duplicate


class MemoryManager:
    def __init__(self, llm, persist_dir: str):
        self.llm = llm
        self.chroma = ChromaStore("cozmo_memories", persist_dir)
        self.short_term = []
        self.max_turns = 5
        self.turn_count = 0

    def add_interaction(self, user: str, assistant: str):
        self.short_term.append({"user": user, "assistant": assistant})
        self.turn_count += 1
        if self.turn_count >= self.max_turns:
            self._summarize_and_store()

    def _summarize_and_store(self):
        text = "\n".join(
            f"User: {m['user']}\nCozmo: {m['assistant']}"
            for m in self.short_term
        )
        summary = self.llm.invoke(SUMMARIZE_PROMPT.format(text=text))

        meta = {
            "timestamp": datetime.now().isoformat(),
            "turns": self.turn_count,
            "type": "conversation",
            "frequency": 1,
        }
        self.chroma.add_texts([summary], [meta])
        self.short_term = self.short_term[-1:]
        self.turn_count = 0

    def store_preference(self, key: str, value: str):
        """Store a user preference as a memory."""
        text = f"User preference: {key} = {value}"
        meta = {
            "timestamp": datetime.now().isoformat(),
            "type": "preference",
            "key": key,
            "frequency": 1,
        }
        self.chroma.add_texts([text], [meta])

    def store_project_context(self, context: str):
        """Store project context as a memory."""
        meta = {
            "timestamp": datetime.now().isoformat(),
            "type": "project",
            "frequency": 1,
        }
        self.chroma.add_texts([context], [meta])

    def store_fact(self, fact: str, tags: list[str] | None = None):
        """Store a learned fact."""
        meta = {
            "timestamp": datetime.now().isoformat(),
            "type": "fact",
            "tags": tags or [],
            "frequency": 1,
        }
        self.chroma.add_texts([fact], [meta])

    def query(self, text: str, k: int = 5, distance_threshold: float | None = 0.5) -> list[dict]:
        """Query memory using importance-weighted hybrid search."""
        results = self.chroma.search_with_importance(
            text, k=k, distance_threshold=distance_threshold
        )
        # Increment frequency for accessed memories
        for item in results:
            if "id" in item:
                self.chroma.increment_frequency(item["id"])
        return results

    def consolidate(self) -> int:
        """Find and merge similar/duplicate memories. Returns count of merges."""
        all_memories = self.chroma.list_all(limit=500)
        if len(all_memories) < 2:
            return 0

        merged = 0
        seen = set()
        for i, mem_a in enumerate(all_memories):
            if mem_a["id"] in seen:
                continue
            for j in range(i + 1, len(all_memories)):
                mem_b = all_memories[j]
                if mem_b["id"] in seen:
                    continue
                # Quick text overlap check before expensive embedding comparison
                words_a = set(mem_a["text"].lower().split())
                words_b = set(mem_b["text"].lower().split())
                overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)
                if overlap > 0.7:
                    # Mark newer one to keep, delete older
                    freq_a = mem_a.get("metadata", {}).get("frequency", 1)
                    freq_b = mem_b.get("metadata", {}).get("frequency", 1)
                    if freq_a >= freq_b:
                        seen.add(mem_b["id"])
                    else:
                        seen.add(mem_a["id"])
                        break

        # Delete duplicates
        for id_ in seen:
            self.chroma.delete(id_)
            merged += 1

        return merged
