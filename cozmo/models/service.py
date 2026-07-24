"""ModelService — resolves configured models and coordinates providers.

Phase B: core resolution + provider coordination.
Phase C: reads from llm.roles (new config) with models (legacy) fallback.
"""

from __future__ import annotations

import logging
from typing import Optional

from .registry import ModelRegistry as _ModelRegistry
from ..providers import LLMProvider, ModelInfo, PROVIDER_REGISTRY, create_provider, parse_model_spec

log = logging.getLogger("cozmo.models.service")


class ModelUnavailableError(Exception):
    """Raised when a configured model is not found in the registry."""

    def __init__(self, role: str, configured: str, available: list[str]):
        self.role = role
        self.configured = configured
        self.available = available
        super().__init__(f"Model '{configured}' for role '{role}' not found. "
                         f"Available: {', '.join(available) if available else '(none)'}")


class ModelService:
    """Coordinates providers and resolves roles to (provider, model_name)."""

    def __init__(self, config: dict, registry: _ModelRegistry):
        self._config = config
        self._registry = registry
        self._provider_cache: dict[str, LLMProvider] = {}

    # ── public API ──────────────────────────────────────────────────────

    def resolve(self, role: str) -> tuple[str, str]:
        """Resolve role to (provider_name, model_name).

        Reads llm.roles (new format) first, falls back to models (legacy).
        Raises ModelUnavailableError if configured model is not in registry.
        """
        provider_name, model_name = self._resolve_spec(role)[:2]
        return provider_name, model_name

    def bind_model(self, model_name: str, tools: list,
                   temperature: float = 0.0):
        provider = self._get_provider_for_model(model_name)
        return provider.bind_tools(tools, temperature)

    def client_for_model(self, model_name: str,
                         temperature: float = 0.0):
        provider = self._get_provider_for_model(model_name)
        return provider.get_chat_model(temperature)

    def client(self, role: str, temperature: float = 0.0):
        provider_name, model_name = self.resolve(role)
        provider = self._get_provider_for_model(model_name)
        return provider.get_chat_model(temperature)

    def list_available(self) -> dict[str, list[ModelInfo]]:
        result: dict[str, list[ModelInfo]] = {}
        for m in self._registry.list_all():
            result.setdefault(m.provider, []).append(m)
        return result

    def refresh(self):
        """Force re-discovery from all configured providers."""
        self._registry.clear()
        self._provider_cache.clear()

        providers_cfg = self._config.get("providers", {})
        for provider_name in PROVIDER_REGISTRY:
            prov_cfg = providers_cfg.get(provider_name, {})
            try:
                provider = create_provider(provider_name, "", prov_cfg)
                models = provider.list_models()
                if models:
                    self._registry.update(provider_name, models)
            except Exception as e:
                log.warning("refresh: provider '%s' failed: %s", provider_name, e)

    def validate(self) -> list[ModelUnavailableError]:
        """Check every configured role. Returns list of errors (non-raising)."""
        errors: list[ModelUnavailableError] = []
        roles = self._get_roles_config()

        for role, spec in roles.items():
            if not spec:
                continue
            provider_name, model_name, _ = self._parse_spec(spec)
            if model_name and not self._registry.validate(model_name):
                available = [m.name for m in self._registry.list_all()]
                errors.append(ModelUnavailableError(role, model_name, available))
        return errors

    # ── internal ────────────────────────────────────────────────────────

    def _get_roles_config(self) -> dict:
        """Read role→model assignments from new (llm.roles) or legacy (models) config."""
        llm = self._config.get("llm", {})
        roles = llm.get("roles", {})
        if roles:
            return roles
        # Legacy fallback: models section
        models = self._config.get("models", {})
        return {k: v for k, v in models.items() if k != "max_tokens"}

    def _parse_spec(self, spec) -> tuple[str, str, dict]:
        providers_cfg = self._config.get("providers", {})
        default_provider = providers_cfg.get("default", "ollama")
        return parse_model_spec(spec, providers_cfg, default_provider)

    def _resolve_spec(self, role: str) -> tuple[str, str, dict]:
        roles = self._get_roles_config()
        spec = roles.get(role, "")
        provider_name, model_name, prov_cfg = self._parse_spec(spec)

        if model_name and not self._registry.validate(model_name):
            available = [m.name for m in self._registry.list_all()]
            raise ModelUnavailableError(role, model_name, available)

        return provider_name, model_name, prov_cfg

    def _get_provider_for_model(self, model_name: str) -> LLMProvider:
        cache_key = f"model:{model_name}"
        if cache_key in self._provider_cache:
            return self._provider_cache[cache_key]

        info = self._registry.find(model_name)
        if info:
            provider_name = info.provider
        else:
            provider_name = self._config.get("providers", {}).get("default", "ollama")

        providers_cfg = self._config.get("providers", {})
        prov_cfg = providers_cfg.get(provider_name, {})

        provider = create_provider(provider_name, model_name, prov_cfg)
        self._provider_cache[cache_key] = provider
        return provider
