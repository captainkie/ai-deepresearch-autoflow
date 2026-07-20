"""Deterministic mock search provider (offline, no network, no randomness)."""

from __future__ import annotations

import re

from app.models.schemas import SearchResult

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-") or "q"


class MockSearchProvider:
    """Returns ``k`` stable results whose urls derive only from the query."""

    async def search(self, query: str, k: int = 6) -> list[SearchResult]:
        slug = _slug(query)
        return [
            SearchResult(
                title=f"{query} — result {i}",
                url=f"https://example.com/{slug}/{i}",
                snippet=f"Deterministic snippet {i} about {query}.",
                score=round(1.0 - i * 0.1, 3),
            )
            for i in range(k)
        ]
