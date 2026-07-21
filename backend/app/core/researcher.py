"""Per-section bounded research loop.

Two paths, chosen by ``config.verification_level``:

* ``off`` — the legacy path: search -> fetch -> summarize -> cited note.
* ``light`` / ``strict`` — Engine v2: search -> fetch -> **extract claims** ->
  **verify** each against its source -> detect contradictions -> compress the
  *verified* claims into notes. Emits ``claim`` / ``verification`` /
  ``contradiction`` events. Stops on diminishing returns (a round adding 0 new
  sources and 0 new supported claims), not just an iteration count.

Sources are deduped through the shared :class:`SourceRegistry`; every step emits
an event.
"""

from __future__ import annotations

import asyncio

from app.core.claims import extract_claims
from app.core.contradictions import detect_contradictions
from app.core.events import EventEmitter
from app.core.sources import SourceRegistry
from app.core.verifier import verify_claims
from app.models.schemas import (
    Claim,
    EventType,
    PageContent,
    PlanSection,
    RunConfig,
    SearchResult,
    Verdict,
    Verification,
)
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
        verifier: LLMProvider | None = None,
    ) -> None:
        self._llm = llm
        self._search = search
        self._crawl = crawl
        self._registry = registry
        self._emitter = emitter
        self._config = config
        self._fetch_sem = fetch_semaphore or asyncio.Semaphore(config.fetch_concurrency)
        self._verifier = verifier or llm

    async def research(self, section: PlanSection) -> str:
        await self._emitter.emit(
            EventType.section_start,
            {"section_id": section.id, "title": section.title},
        )
        if self._config.verification_level == "off":
            return await self._research_legacy(section)
        return await self._research_v2(section)

    # --- legacy path (verification_level == off) --------------------------- #

    async def _research_legacy(self, section: PlanSection) -> str:
        notes: list[str] = []
        seen_queries: set[str] = set()
        queries = list(section.queries) or [section.title]

        max_iters = max(1, self._config.max_iters_per_section)
        for i in range(max_iters):
            await self._run_queries(section, queries, seen_queries, notes)
            if i == max_iters - 1:
                break
            reflection = await self._reflect(section.goal, notes)
            if not reflection.get("need_more"):
                break
            follow = [q for q in reflection.get("queries", []) if q and q not in seen_queries]
            if not follow:
                break
            queries = follow

        return await self._finish_section(section, notes)

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

    # --- Engine v2 path (verification_level == light | strict) ------------- #

    async def _research_v2(self, section: PlanSection) -> str:
        emit = self._emitter.emit
        seen_queries: set[str] = set()
        queries = list(section.queries) or [section.title]
        claims: list[Claim] = []
        verifs: list[Verification] = []

        max_iters = max(1, self._config.max_iters_per_section)
        for i in range(max_iters):
            new_sources, round_claims, round_verifs = await self._run_queries_v2(
                section, queries, seen_queries
            )
            claims.extend(round_claims)
            verifs.extend(round_verifs)
            new_supported = sum(1 for v in round_verifs if v.verdict is Verdict.supported)
            # Diminishing returns: nothing new to learn from this round.
            if new_sources == 0 and new_supported == 0:
                break
            if i == max_iters - 1:
                break
            notes_so_far = [c.text for c in round_claims]
            reflection = await self._reflect(section.goal, notes_so_far)
            if not reflection.get("need_more"):
                break
            follow = [q for q in reflection.get("queries", []) if q and q not in seen_queries]
            if not follow:
                break
            queries = follow

        # Contradictions across the whole section, then the verified findings.
        contradictions = await detect_contradictions(claims, verifs, self._verifier)
        for c in contradictions:
            await emit(
                EventType.contradiction,
                {
                    "id": c.id,
                    "entity": c.entity,
                    "attribute": c.attribute,
                    "claim_ids": [c.claim_id_a, c.claim_id_b],
                    "note": c.note,
                },
            )

        supported_ids = {v.claim_id for v in verifs if v.verdict is Verdict.supported}
        notes: list[str] = []
        for claim in claims:
            if claim.id in supported_ids:
                cites = "".join(f"[{sid}]" for sid in claim.source_ids)
                note = f"{claim.text} {cites}".strip()
                notes.append(note)
                await emit(EventType.note, {"section_id": section.id, "content": note})

        return await self._finish_section(section, notes)

    async def _run_queries_v2(
        self,
        section: PlanSection,
        queries: list[str],
        seen_queries: set[str],
    ) -> tuple[int, list[Claim], list[Verification]]:
        emit = self._emitter.emit
        new_sources = 0
        round_claims: list[Claim] = []
        round_verifs: list[Verification] = []
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
                before = len(self._registry)
                source = await self._registry.add(
                    url=result.url,
                    title=result.title,
                    snippet=result.snippet,
                    section_id=section.id,
                )
                if len(self._registry) == before:
                    continue  # already processed this source — don't re-extract
                new_sources += 1
                await emit(
                    EventType.source,
                    {"section_id": section.id, "source": source.model_dump()},
                )

                page_claims = await extract_claims(
                    llm=self._llm,
                    page=page,
                    goal=section.goal,
                    source_id=source.id,
                    section_id=section.id,
                )
                for claim in page_claims:
                    await emit(
                        EventType.claim,
                        {
                            "claim_id": claim.id,
                            "section_id": section.id,
                            "text": claim.text,
                            "entity": claim.entity,
                            "attribute": claim.attribute,
                            "source_ids": claim.source_ids,
                            "quote": claim.quote,
                        },
                    )
                page_verifs = await verify_claims(
                    page_claims,
                    page.text,
                    self._verifier,
                    verifier_model=self._config.verifier_model or None,
                )
                for v in page_verifs:
                    await emit(
                        EventType.verification,
                        {
                            "claim_id": v.claim_id,
                            "verdict": v.verdict.value,
                            "confidence": v.confidence,
                            "rationale": v.rationale,
                        },
                    )
                round_claims.extend(page_claims)
                round_verifs.extend(page_verifs)
        return new_sources, round_claims, round_verifs

    # --- shared helpers ---------------------------------------------------- #

    async def _finish_section(self, section: PlanSection, notes: list[str]) -> str:
        compressed = await self._llm.complete(
            compress_messages(section.goal, "\n".join(notes)), tag="compress"
        )
        source_count = sum(1 for s in self._registry.all() if s.section_id == section.id)
        await self._emitter.emit(
            EventType.section_done,
            {"section_id": section.id, "summary": compressed, "source_count": source_count},
        )
        return compressed

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
