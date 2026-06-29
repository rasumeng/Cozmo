import re
from pathlib import Path
from .llm import OllamaModel
from .agent import Agent
from .. import config
from ..memory.manager import MemoryManager


_GREETINGS = {"hi", "hello", "hey", "sup", "yo", "what's up", "howdy"}

def _pre_filter(text: str) -> str | None:
    t = text.strip().lower()
    if t in _GREETINGS or len(t) < 10:
        return "simple"
    if len(t) > 500:
        return "complex"
    if re.search(r"```|def |class |import |async def|from \w+ import", t):
        return "complex"
    return None


_CLASSIFIER_PROMPT = """You are a task router. Classify the request as exactly one word:
simple: chat, greetings, quick facts, yes/no
moderate: explanations, research, analysis, summaries
complex: coding, debugging, scripts, multi-step projects

Request: {text}
Classification:"""


class Orchestrator:
    def __init__(self, cfg: dict | None = None):
        self.cfg = cfg or config.load()
        classifier_model = self.cfg.get("models", {}).get("classifier", "qwen3:0.6b")
        self.classifier = OllamaModel(classifier_model)
        self.memory = MemoryManager(
            self.classifier,
            persist_dir=str(Path.home() / ".cozmo" / "memory"),
        )
        self.conversation: list[tuple[str, str]] = []
        self.max_history = 10

    def _classify(self, text: str) -> str:
        result = _pre_filter(text)
        if result:
            return result

        raw = self.classifier.invoke(_CLASSIFIER_PROMPT.format(text=text)).strip().lower()
        if raw in ("simple", "moderate", "complex"):
            return raw
        return "moderate"

    def _get_model_name(self, task_type: str) -> str:
        m = {"simple": "fast", "moderate": "balanced", "complex": "heavy"}
        return self.cfg["models"].get(m[task_type], "qwen3:8b")

    def _build_prompt(self, user_input: str, memories: str = "") -> str:
        parts = []
        if memories:
            parts.append(memories)
        for role, text in self.conversation:
            parts.append(f"{role}: {text}")
        parts.append(f"user: {user_input}")
        return "\n".join(parts)

    def _add_to_history(self, user: str, assistant: str):
        self.conversation.append(("user", user))
        self.conversation.append(("assistant", assistant))
        while len(self.conversation) > self.max_history:
            self.conversation.pop(0)

    def run(self, user_input: str) -> str:
        task_type = self._classify(user_input)
        model_name = self._get_model_name(task_type)
        memories = self.memory.query(user_input)
        prompt = self._build_prompt(user_input, memories)

        agent = Agent(model_name)
        result = agent.run(prompt)

        self.memory.add_interaction(user_input, result)
        self._add_to_history(user_input, result)
        return result
