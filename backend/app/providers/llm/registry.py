"""LLM provider registry — the only place config maps to a concrete LLM."""

from __future__ import annotations

from collections.abc import Callable

from app.models.schemas import RunConfig

GetKey = Callable[[str], str | None]

_LITELLM_PROVIDERS = {"anthropic", "openai", "gemini", "litellm"}


def get_llm_provider(config: RunConfig, get_key: GetKey):
    name = config.llm_provider
    if name == "mock":
        from app.providers.llm.mock import MockLLMProvider

        return MockLLMProvider(model=config.llm_model)
    if name in _LITELLM_PROVIDERS:
        from app.providers.llm.litellm_provider import LiteLLMProvider

        return LiteLLMProvider(provider=name, model=config.llm_model, get_key=get_key)
    raise ValueError(f"unknown llm provider: {name!r}")
