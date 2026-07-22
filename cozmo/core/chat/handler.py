import logging
from datetime import datetime
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from ..model_manager import ModelManager

log = logging.getLogger("cozmo.chat")

_CHAT_SYSTEM_PROMPT = (
    "You are Cozmo, a capable local AI assistant running entirely on-device via Ollama. "
    "Today's date is {date}. Your training data is older than this — for "
    "anything time-sensitive, trust tool results over your own knowledge.\n\n"
    "Answer conversationally and concisely. Be direct. No hedging, no filler."
)


class ChatHandler:
    """Lightweight conversational handler. Fast path — no agent overhead.

    Queries persistent memory for relevant context before responding.
    """

    def __init__(self, model_manager: ModelManager, cfg: dict | None = None, memory=None):
        self.model_manager = model_manager
        self.cfg = cfg or {}
        self.memory = memory
        self._summary: str = ""
        self._max_memory_results = cfg.get("runtime", {}).get("max_memory_results", 3)
        self._memory_distance_threshold = cfg.get("runtime", {}).get("memory_distance_threshold", 0.5)

    def _query_memory(self, text: str) -> str:
        if not self.memory:
            return ""
        try:
            results = self.memory.query(text, k=self._max_memory_results * 2)
            if not results:
                return ""
            filtered = [r for r in results if r.get("distance", 0) < self._memory_distance_threshold]
            filtered = filtered[:self._max_memory_results]
            if not filtered:
                return ""
            return "\n".join(f"- {r['text']}" for r in filtered)
        except Exception:
            return ""

    def _build_messages(self, user_input: str, history: list[tuple[str, str]]) -> list:
        now = datetime.now().strftime("%A, %B %d, %Y")
        parts = [_CHAT_SYSTEM_PROMPT.format(date=now)]

        personality = (self.cfg.get("personality") or "").strip()
        if personality:
            parts.append(f"USER PREFERENCES:\n{personality}")

        memory = self._query_memory(user_input)
        if memory:
            parts.append(f"Relevant memory from past sessions:\n{memory}")

        if self._summary:
            parts.append(f"Context from earlier in this session:\n{self._summary}")

        system = "\n\n".join(parts)
        messages = [SystemMessage(content=system)]

        for user_msg, assistant_msg in history:
            messages.append(HumanMessage(content=user_msg))
            messages.append(SystemMessage(content=assistant_msg))

        messages.append(HumanMessage(content=user_input))
        return messages

    def stream(self, user_input: str, history: list[tuple[str, str]] | None = None):
        """Yield (kind, text) tuples for a chat response.
        kind is 'token' for visible text, 'reasoning' for model chain-of-thought."""
        msgs = self._build_messages(user_input, history or [])
        llm = self.model_manager.client("chat", temperature=0.6)
        for chunk in llm.stream(msgs):
            reasoning_content = chunk.additional_kwargs.get("reasoning_content", "")
            if reasoning_content:
                yield ("reasoning", reasoning_content)
            if chunk.content:
                yield ("token", chunk.content)

    def invoke(self, user_input: str, history: list[tuple[str, str]] | None = None) -> str:
        """Non-streaming invoke. Returns full response text."""
        parts = [text for kind, text in self.stream(user_input, history or []) if kind == "token"]
        return "".join(parts)
