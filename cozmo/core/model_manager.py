"""ModelManager — per-role model dispatch.

Routes each request to the model configured for that role (chat/coder/research/vision).
In lightweight mode, all roles use the same MiniCPM5 model.
Keeps one OllamaModel instance per unique model name (with per-temperature caching inside).
"""

from .llm import OllamaModel

ROLE_MODEL_KEY = {
    "chat": "chat",
    "work": "coder",
    "research": "research",
    "vision": "vision",
}

class ModelManager:
    def __init__(
        self,
        ollama_url: str,
        models_cfg: dict,
        lightweight_model: str | None = None,
    ):
        self.ollama_url = ollama_url
        self.models_cfg = models_cfg
        self.lightweight_model = lightweight_model
        self._instances: dict[str, OllamaModel] = {}

    def _model_name(self, role: str) -> str:
        if self.lightweight_model:
            return self.lightweight_model
        cfg_key = ROLE_MODEL_KEY.get(role, "chat")
        return self.models_cfg.get(cfg_key, "qwen3:8b")

    def _llm(self, role: str) -> OllamaModel:
        name = self._model_name(role)
        if name not in self._instances:
            self._instances[name] = OllamaModel(name, self.ollama_url)
        return self._instances[name]

    def bind_tools(self, role: str, tools: list, temperature: float = 0.0):
        return self._llm(role).bind_tools(tools, temperature)

    def client(self, role: str, temperature: float = 0.0):
        return self._llm(role).client(temperature)
