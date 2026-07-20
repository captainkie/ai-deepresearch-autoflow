"""Per-section bounded research loop.

For a section: search -> fetch top-K pages (concurrently, capped) -> summarize
each against the goal -> record a cited note -> reflect (stop unless more is
needed) up to ``max_iters_per_section`` -> compress into section notes. Sources
are deduped through the shared :class:`SourceRegistry`; every step emits an event.
"""

from __future__ import annotations

import asyncio

from app.core.events import EventEmitter
from app.core.sources import SourceRegistry
from app.models.schemas import EventType, PageContent, PlanSection, RunConfig, SearchResult
from app.providers.crawl.base import CrawlProvider
from app.providers.json_utils import JSONParseError, extract_json
from app.providers.llm.base import LLMProvider
from app.providers.search.base import SearchProvider
from app.prompts.researcher import compress_messages, reflect_messages, summarize_messages


class Researcher:
    def __init__(
        self,
        *,
        llm: LLMProvider,
        search: SearchProvider,
        crawl: CrawlProvider,
        registry: SourceRegistry,
        emitter: EventEmitter,
        config: RunConfig,
        fetch_semaphore: asyncio.Semaphore | None = None,
    ) -> None:
        self._llm = llm
        self._search = search
        self._crawl = crawl
        self._registry = registry
        self._emitter = emitter
        self._config = config
        self._fetch_sem = fetch_semaphore or asyncio.Semaphore(config.fetch_concurrency)

    async def research(self, section: PlanSection) -> str:
        emit = self._emitter.emit
        await emit(
            EventType.section_start,
            {"section_id": section.id, "title": section.title},
        )

        notes: list[str] = []
        seen_queries: set[str] = set()
        queries = list(section.queries) or [section.title]

        max_iters = max(1, self._config.max_iters_per_section)
        for i in range(max_iters):
            await self._run_queries(section, queries, seen_queries, notes)
            if i == max_iters - 1:
                break  # last allowed pass — a reflection here could only be discarded
            reflection = await self._reflect(section.goal, notes)
            if not reflection.get("need_more"):
                break
            follow = [q for q in reflection.get("queries", []) if q and q not in seen_queries]
            if not follow:
                break
            queries = follow

        compressed = await self._llm.complete(
            compress_messages(section.goal, "\n".join(notes)), tag="compress"
        )
        source_count = sum(1 for s in self._registry.all() if s.section_id == section.id)
        await emit(
            EventType.section_done,
            {"section_id": section.id, "summary": compressed, "source_count": source_count},
        )
        return compressed

    async def _run_queries(
        self,
        section: PlanSection,
        queries: list[str],
        seen_queries: set[str],
        notes: list[str],
    ) -> None:
        emit = self._emitter.emit
        for query in queries:
            if not query or query in seen_queries:
                continue
            seen_queries.add(query)
            await emit(EventType.search, {"section_id": section.id, "query": query})
            results = await self._search.search(query, self._config.results_per_query)
            top = results[: self._config.fetch_per_query]
            pages = await self._fetch_all(top)
            for result, page in zip(top, pages):
                if not page.ok or not page.text:
                    continue
                source = await self._registry.add(
                    url=result.url,
                    title=result.title,
                    snippet=result.snippet,
                    section_id=section.id,
                )
                await emit(
                    EventType.source,
                    {"section_id": section.id, "source": source.model_dump()},
                )
                summary = await self._llm.complete(
                    summarize_messages(section.goal, page), tag="summarize"
                )
                note = f"{summary} [{source.id}]"
                notes.append(note)
                await emit(EventType.note, {"section_id": section.id, "content": note})

    async def _fetch_all(self, results: list[SearchResult]) -> list[PageContent]:
        async def fetch_one(result: SearchResult) -> PageContent:
            async with self._fetch_sem:
                try:
                    return await self._crawl.fetch(result.url)
                except Exception as exc:  # noqa: BLE001 - a bad page must not abort the batch
                    return PageContent(url=result.url, ok=False, error=str(exc))

        return await asyncio.gather(*(fetch_one(r) for r in results))

    async def _reflect(self, goal: str, notes: list[str]) -> dict:
        raw = await self._llm.complete(reflect_messages(goal, "\n".join(notes)), tag="reflect")
        try:
            return extract_json(raw)
        except JSONParseError:
            return {"need_more": False, "queries": []}
