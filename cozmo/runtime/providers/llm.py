"""Backward-compat re-exports.  Real code moved to cozmo/providers/.

Phase A: import path unchanged for all existing callers.
"""

from cozmo.providers import (
    LLMProvider,
    OllamaProvider,
    OpenAIProvider,
    PROVIDER_REGISTRY,
    create_provider,
    parse_model_spec,
)

__all__ = [
    "LLMProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "PROVIDER_REGISTRY",
    "create_provider",
    "parse_model_spec",
]
