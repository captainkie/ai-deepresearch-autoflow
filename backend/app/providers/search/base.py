"""Search provider interface."""

from __future__ import annotations

from typing import Protocol

from app.models.schemas import SearchResult


class SearchProvider(Protocol):
    async def search(self, query: str, k: int = 6) -> list[SearchResult]: ...
