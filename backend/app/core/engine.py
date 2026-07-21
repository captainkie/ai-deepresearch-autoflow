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
from app.core.researcher import Researcher, SectionResult
from app.core.sources import SourceRegistry
from app.core.synthesizer import summarize_confidence, synthesize
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
            results = await self._research_all(sections, registry, emitter, config)
            claims = [c for r in results for c in r.claims]
            verifications = [v for r in results for v in r.verifications]
            contradictions = [x for r in results for x in r.contradictions]

            await emit(
                EventType.status,
                {"stage": RunStatus.writing.value, "message": "Writing report"},
            )
            markdown, title = await synthesize(
                plan.brief,
                sections,
                registry.all(),
                self._llm,
                emit,
                config,
                claims=claims,
                verifications=verifications,
                contradictions=contradictions,
            )
            # Attach the trust summary to report/done only when verification ran.
            summary = (
                summarize_confidence(claims, verifications, contradictions) if claims else None
            )
            report_data = {"markdown": markdown, "title": title}
            done_data = {"title": title, "source_count": len(registry.all())}
            if summary is not None:
                report_data["confidence_summary"] = summary
                done_data["confidence_summary"] = summary
            await emit(EventType.report, report_data)
            await emit(EventType.done, done_data)
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
    ) -> list[SectionResult]:
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

        # Collect by index so results keep plan order regardless of completion order.
        results: list[SectionResult | None] = [None] * len(sections)

        async def run_section(idx: int, section: PlanSection) -> None:
            async with section_sem:
                results[idx] = await researcher.research(section)

        # TaskGroup (not gather) so the first section failure cancels its
        # siblings — otherwise orphaned section tasks keep emitting events onto
        # the shared emitter after the `error` event and get destroyed at
        # shutdown. Surface the original error (unwrapped) to run().
        try:
            async with asyncio.TaskGroup() as tg:
                for idx, section in enumerate(sections):
                    tg.create_task(run_section(idx, section))
        except* Exception as eg:
            raise eg.exceptions[0] from None

        return [r for r in results if r is not None]
