"""ModelManager — per-role model dispatch with multi-provider support.

Routes each request to the model+provider configured for that role.
Supports Ollama, OpenAI, etc. via the LLMProvider abstraction.

Backward-compatible API: all callers unchanged.
"""

from .llm import OllamaModel
from .providers.llm import create_provider, parse_model_spec
from ..ollama_util import get_ollama_models, pick_model

ROLE_MODEL_KEY = {
    "chat": "chat",
    "work": "coder",
    "research": "research",
    "vision": "vision",
    "agent": "agent",
}


class ModelManager:
    def __init__(
        self,
        ollama_url: str,
        models_cfg: dict,
        lightweight_model: str | None = None,
        providers_cfg: dict | None = None,
    ):
        self.ollama_url = ollama_url
        self.models_cfg = models_cfg
        self.lightweight_model = lightweight_model
        self.providers_cfg = providers_cfg or {"default": "ollama", "ollama": {"url": ollama_url}}
        self._instances: dict[str, OllamaModel] = {}
        self._provider_instances: dict[str, object] = {}
        self._overrides: dict[str, str] = {}
        self._installed: list[str] | None = None
        self._default_provider = self.providers_cfg.get("default", "ollama")

    def set_override(self, role: str, model_name: str):
        self._overrides[role] = model_name

    def clear_override(self, role: str):
        self._overrides.pop(role, None)

    def reload_models(self, models_cfg: dict):
        """Hot-reload model assignments. Clears cached LLM providers so next
        call picks up the new model name. Called after config save."""
        self.models_cfg = models_cfg
        self._installed = None
        self._instances.clear()
        self._provider_instances.clear()

    def set_lightweight_mode(self, enabled: bool, model: str | None = None):
        """Toggle lightweight mode at runtime. Clears cached providers so the
        lightweight model takes effect on the next LLM call."""
        self.lightweight_model = model if enabled else None
        self._provider_instances.clear()

    def _installed_models(self) -> list[str]:
        if self._installed is None:
            self._installed = get_ollama_models(self.ollama_url)
        return self._installed

    def _model_spec(self, role: str) -> str | dict:
        if role in self._overrides:
            return self._overrides[role]
        if self.lightweight_model:
            return self.lightweight_model
        cfg_key = ROLE_MODEL_KEY.get(role, "chat")
        configured = self.models_cfg.get(cfg_key)
        if configured:
            return configured
        installed = self._installed_models()
        return pick_model(installed, cfg_key)

    def _get_provider(self, role: str):
        """Return LLMProvider for the given role, creating if needed."""
        spec = self._model_spec(role)
        cache_key = str(spec)  # hashable for cache
        if cache_key not in self._provider_instances:
            provider_name, model_name, prov_cfg = parse_model_spec(
                spec, self.providers_cfg, self._default_provider
            )
            self._provider_instances[cache_key] = create_provider(provider_name, model_name, prov_cfg)
        return self._provider_instances[cache_key]

    def _llm(self, role: str) -> OllamaModel:
        """Fallback legacy OllamaModel instance (for router_llm compat)."""
        name = self._model_spec(role)
        if isinstance(name, dict):
            name = name.get("model", "")
        if name not in self._instances:
            self._instances[name] = OllamaModel(name, self.ollama_url)
        return self._instances[name]

    def bind_tools(self, role: str, tools: list, temperature: float = 0.0):
        provider = self._get_provider(role)
        return provider.bind_tools(tools, temperature)

    def client(self, role: str, temperature: float = 0.0):
        provider = self._get_provider(role)
        return provider.get_chat_model(temperature)
