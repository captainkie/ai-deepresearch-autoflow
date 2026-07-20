"""ResearchEngine — orchestrates plan -> (approve) -> research -> synthesize.

Pure engine: depends only on provider interfaces + an event sink. Emits typed
events (see docs/API_CONTRACT.md) through a shared EventEmitter and shares one
SourceRegistry so citation ids are stable across the whole report.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.core.events import EventEmitter, Sink
from app.core.planner import Planner
from app.core.researcher import Researcher
from app.core.sources import SourceRegistry
from app.core.synthesizer import synthesize
from app.models.schemas import EventType, Plan, PlanSection, RunConfig, RunStatus
from app.providers.crawl.base import CrawlProvider
from app.providers.llm.base import LLMProvider
from app.providers.search.base import SearchProvider

# Given the proposed plan, return the (possibly edited) list of sections to run.
ApprovalFn = Callable[[Plan], Awaitable[list[PlanSection]]]


class ResearchEngine:
    def __init__(
        self,
        *,
        llm: LLMProvider,
        search: SearchProvider,
        crawl: CrawlProvider,
    ) -> None:
        self._llm = llm
        self._search = search
        self._crawl = crawl

    async def run(
        self,
        run_id: str,
        query: str,
        config: RunConfig,
        sink: Sink,
        approval: ApprovalFn | None = None,
    ) -> str:
        emitter = EventEmitter(run_id, sink)
        emit = emitter.emit
        registry = SourceRegistry()
        try:
            await emit(
                EventType.status,
                {"stage": RunStatus.planning.value, "message": "Planning research"},
            )
            plan = await Planner(self._llm).plan(query, config)
            await emit(
                EventType.plan,
                {
                    "brief": plan.brief.objective,
                    "sections": [s.model_dump() for s in plan.sections],
                },
            )

            sections = plan.sections
            if config.require_plan_approval and approval is not None:
                await emit(EventType.awaiting_plan, {})
                approved = await approval(plan)
                sections = approved or plan.sections

            await emit(
                EventType.status,
                {"stage": RunStatus.researching.value, "message": "Researching sections"},
            )
            await self._research_all(sections, registry, emitter, config)

            await emit(
                EventType.status,
                {"stage": RunStatus.writing.value, "message": "Writing report"},
            )
            markdown, title = await synthesize(
                plan.brief, sections, registry.all(), self._llm, emit, config
            )
            await emit(EventType.report, {"markdown": markdown, "title": title})
            await emit(
                EventType.done,
                {"title": title, "source_count": len(registry.all())},
            )
            return markdown
        except Exception as exc:  # noqa: BLE001 - surface any failure as an error event
            await emit(EventType.error, {"message": str(exc)})
            raise

    async def _research_all(
        self,
        sections: list[PlanSection],
        registry: SourceRegistry,
        emitter: EventEmitter,
        config: RunConfig,
    ) -> None:
        fetch_sem = asyncio.Semaphore(config.fetch_concurrency)
        section_sem = asyncio.Semaphore(config.section_concurrency)
        researcher = Researcher(
            llm=self._llm,
            search=self._search,
            crawl=self._crawl,
            registry=registry,
            emitter=emitter,
            config=config,
            fetch_semaphore=fetch_sem,
        )

        async def run_section(section: PlanSection) -> None:
            async with section_sem:
                await researcher.research(section)

        await asyncio.gather(*(run_section(s) for s in sections))
