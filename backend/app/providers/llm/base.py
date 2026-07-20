"""LLM provider interface.

The engine depends only on this Protocol, never on a concrete adapter. ``tag``
lets the mock select a deterministic canned response; real providers ignore it.
Values used by the engine: ``"plan" | "summarize" | "reflect" | "compress" | "report"``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol


class LLMProvider(Protocol):
    async def complete(
        self,
        messages: list[dict],
        *,
        tag: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        json: bool = False,
    ) -> str: ...

    def stream(
        self,
        messages: list[dict],
        *,
        tag: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]: ...
