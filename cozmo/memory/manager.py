from datetime import datetime
from .chroma_store import ChromaStore


SUMMARIZE_PROMPT = """Condense the following conversation into 2-3 sentences.
Capture key facts, user preferences, and any actionable items.
Do not include greetings or small talk.

Conversation:
{text}

Summary:"""


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

        self.chroma.add_texts(
            [summary],
            [{"timestamp": datetime.now().isoformat(), "turns": self.turn_count}],
        )
        self.short_term = self.short_term[-1:]
        self.turn_count = 0

    def query(self, text: str, k: int = 5) -> str:
        results = self.chroma.similarity_search(text, k)
        if not results:
            return ""
        lines = ["Relevant past memories:"]
        for r in results:
            lines.append(f"- {r['text']}")
        return "\n".join(lines)
