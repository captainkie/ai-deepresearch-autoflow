"""Global source registry giving every cited page a stable numeric id.

Ids start at 1, are assigned in first-seen order, and are shared across the
whole report so citations ``[n]`` stay consistent. Deduplicates by url. Guarded
by an :class:`asyncio.Lock` so concurrent section research is safe.
"""

from __future__ import annotations

import asyncio

from app.models.schemas import Source


class SourceRegistry:
    def __init__(self) -> None:
        self._by_url: dict[str, int] = {}
        self._sources: list[Source] = []
        self._lock = asyncio.Lock()

    async def add(
        self,
        *,
        url: str,
        title: str,
        snippet: str = "",
        section_id: str | None = None,
    ) -> Source:
        async with self._lock:
            existing = self._by_url.get(url)
            if existing is not None:
                return self._sources[existing - 1]
            new_id = len(self._sources) + 1
            source = Source(
                id=new_id,
                title=title,
                url=url,
                snippet=snippet,
                section_id=section_id,
            )
            self._by_url[url] = new_id
            self._sources.append(source)
            return source

    def all(self) -> list[Source]:
        return list(self._sources)

    def __len__(self) -> int:
        return len(self._sources)
