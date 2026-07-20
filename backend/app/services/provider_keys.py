"""Resolve a provider's API key from the environment.

Demo-first: keys live in ``os.environ`` (``ANTHROPIC_API_KEY`` etc.). M3 swaps
this single function for the encrypted vault without touching call sites — the
registries and config service depend only on ``get_key(provider) -> str | None``.
"""

from __future__ import annotations

import os

_KEY_ENV: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "litellm": "LITELLM_API_KEY",
    "tavily": "TAVILY_API_KEY",
    "serper": "SERPER_API_KEY",
    "exa": "EXA_API_KEY",
    "jina": "JINA_API_KEY",
}


def get_key(provider: str) -> str | None:
    env_name = _KEY_ENV.get(provider)
    if not env_name:
        return None
    value = os.environ.get(env_name)
    return value or None
