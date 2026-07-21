"""RunService + RunHub — own the lifecycle of every research run.

A :class:`RunHub` wraps one active run: the background ``asyncio.Task`` executing
the engine, the set of connected SSE subscriber queues, and (M2 Task 7) the
plan-approval future. The engine talks to the outside only through a *sink*; ours
persists every event to SQLite **before** fanning it out to subscribers, so a
reconnecting client that replays from the ``events`` table can never observe an
event that live subscribers missed. The frontend de-dupes by ``seq``, so the
replay/live overlap on ``subscribe`` is safe.

Runs start lazily on first ``subscribe`` (stream connect) and keep running if the
client disconnects — the task is independent of any subscriber generator.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import httpx

from app.api.schemas_api import CreateRun, PlanSubmit, RunConfigIn
from app.core.engine import ResearchEngine
from app.core.events import Sink, now_ms
from app.db.database import Database
from app.db.repositories import (
    ClaimRepo,
    ContradictionRepo,
    EventRepo,
    RunRepo,
    VerificationRepo,
)
from app.models.schemas import Event, EventType, PlanSection, RunConfig, RunStatus
from app.providers.crawl.registry import get_crawl_provider
from app.providers.llm.registry import get_llm_provider
from app.providers.search.registry import get_search_provider
from app.services.config_service import ConfigService
from app.services.provider_keys import get_key as env_get_key
from app.settings import AppSettings

if TYPE_CHECKING:
    from app.services.vault_service import VaultService

GetKey = Callable[[str], str | None]

logger = logging.getLogger(__name__)

_TERMINAL = {EventType.done, EventType.error}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_event(run_id: str, row: Any) -> Event:
    return Event(
        seq=row["seq"],
        run_id=run_id,
        ts=row["ts"],
        type=row["type"],
        data=json.loads(row["data_json"]),
    )


class LlmCallCap:
    """Wrap an ``LLMProvider`` to bound total calls per run.

    Guards against a runaway research loop burning tokens/quota: after
    ``max_calls`` invocations of ``complete``/``stream`` the next call raises,
    which the engine surfaces as an ``error`` event. Transparent otherwise.
    """

    def __init__(self, inner: Any, max_calls: int) -> None:
        self._inner = inner
        self._max = max_calls
        self._count = 0

    def _bump(self) -> None:
        self._count += 1
        if self._count > self._max:
            raise RuntimeError(f"LLM call cap exceeded ({self._max})")

    async def complete(self, *args: Any, **kwargs: Any) -> str:
        self._bump()
        return await self._inner.complete(*args, **kwargs)

    def stream(self, *args: Any, **kwargs: Any):
        self._bump()
        return self._inner.stream(*args, **kwargs)


@dataclass
class RunHub:
    run_id: str
    task: asyncio.Task | None = None
    subscribers: set[asyncio.Queue] = field(default_factory=set)
    finished: asyncio.Event = field(default_factory=asyncio.Event)
    approval: asyncio.Future | None = None
    cancelled: bool = False
    # Single authority for event ``seq`` + write ordering. Every event write
    # (engine sink and terminal cancel/timeout emits) allocates its seq and
    # persists/fans-out while holding ``write_lock``, so there is exactly one
    # monotonic seq source (no collision with the engine's emitter) and live
    # fan-out order matches seq order.
    write_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    next_seq: int = 0


class RunService:
    def __init__(
        self,
        db: Database,
        config_service: ConfigService,
        app_settings: AppSettings,
        vault: "VaultService | None" = None,
    ) -> None:
        self._db = db
        self._config = config_service
        self._app = app_settings
        self._vault = vault
        self._runs = RunRepo(db)
        self._events = EventRepo(db)
        self._claims = ClaimRepo(db)
        self._verifications = VerificationRepo(db)
        self._contradictions = ContradictionRepo(db)
        self._hubs: dict[str, RunHub] = {}
        self._lock = asyncio.Lock()
        self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    # --- Create / query ------------------------------------------------------

    async def create(self, create: CreateRun, owner_id: str | None = None) -> str:
        current = await self._config.current()
        cfg_in = create.config or RunConfigIn()
        # Demo default: providers fall back to the runtime config (mock in dev).
        llm_provider = cfg_in.llm_provider or current["llm"]["provider"] or "mock"
        llm_model = cfg_in.llm_model or current["llm"]["model"] or "mock-1"
        search_provider = cfg_in.search_provider or current["search"]["provider"] or "mock"
        crawl_provider = "mock"  # not exposed in the contract yet; mock in dev
        template = create.template or "deep_research"
        language = create.language or self._app.default_language
        require = create.require_plan_approval
        if require is None:
            require = current["require_plan_approval"]

        run_id = uuid4().hex
        now = _now_iso()
        await self._runs.create(
            id=run_id,
            query=create.query,
            template=template,
            language=language,
            require_plan_approval=bool(require),
            llm_provider=llm_provider,
            llm_model=llm_model,
            search_provider=search_provider,
            crawl_provider=crawl_provider,
            status=RunStatus.queued.value,
            created_at=now,
            updated_at=now,
            owner_id=owner_id,
        )
        return run_id

    async def exists(self, run_id: str) -> bool:
        return await self._runs.get(run_id) is not None

    async def get_owner(self, run_id: str) -> str | None:
        row = await self._runs.get(run_id)
        return row["owner_id"] if row is not None else None

    async def list_runs(
        self, owner_id: str | None = None, *, limit: int | None = None, offset: int = 0
    ) -> tuple[list[dict[str, Any]], bool]:
        """Return a page of runs (newest first) and whether more exist.

        Fetches one extra row past ``limit`` to derive ``has_more`` without a
        separate COUNT. ``limit=None`` returns everything (``has_more`` False).
        """
        fetch = None if limit is None else limit + 1
        rows = await self._runs.list(owner_id, limit=fetch, offset=offset)
        has_more = limit is not None and len(rows) > limit
        if limit is not None:
            rows = rows[:limit]
        runs = [
            {
                "run_id": r["id"],
                "query": r["query"],
                "template": r["template"],
                "status": r["status"],
                "created_at": r["created_at"],
                "title": r["title"],
            }
            for r in rows
        ]
        return runs, has_more

    async def get_detail(self, run_id: str) -> dict[str, Any] | None:
        row = await self._runs.get(run_id)
        if row is None:
            return None
        sections = await self._runs.get_sections(run_id)
        sources = await self._runs.get_sources(run_id)
        return {
            "run_id": row["id"],
            "query": row["query"],
            "template": row["template"],
            "language": row["language"],
            "status": row["status"],
            "title": row["title"],
            "require_plan_approval": bool(row["require_plan_approval"]),
            "config": {
                "llm_provider": row["llm_provider"],
                "llm_model": row["llm_model"],
                "search_provider": row["search_provider"],
                "crawl_provider": row["crawl_provider"],
            },
            "report": row["report_markdown"],
            "error": row["error"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "confidence_summary": await self._confidence_from_events(run_id),
            "plan": await self._plan_from_events(run_id),
            "sections": [
                {
                    "id": s["id"],
                    "idx": s["idx"],
                    "title": s["title"],
                    "goal": s["goal"],
                    "queries": json.loads(s["queries_json"]) if s["queries_json"] else [],
                    "summary": s["summary"],
                    "status": s["status"],
                }
                for s in sections
            ],
            "sources": [
                {
                    "id": s["ref_num"],
                    "title": s["title"],
                    "url": s["url"],
                    "snippet": s["snippet"],
                    "section_id": s["section_id"],
                }
                for s in sources
            ],
        }

    async def _plan_from_events(self, run_id: str) -> dict[str, Any] | None:
        for row in reversed(await self._events.list_by_run(run_id)):
            if row["type"] == EventType.plan.value:
                data = json.loads(row["data_json"])
                return {"brief": data.get("brief", ""), "sections": data.get("sections", [])}
        return None

    async def _confidence_from_events(self, run_id: str) -> dict[str, Any] | None:
        """The trust summary the engine attached to the report event (if any), so
        a reloaded finished run shows its confidence badge without a live stream."""
        for row in reversed(await self._events.list_by_run(run_id)):
            if row["type"] == EventType.report.value:
                return json.loads(row["data_json"]).get("confidence_summary")
        return None

    # --- Execution -----------------------------------------------------------

    async def ensure_started(self, run_id: str) -> RunHub:
        async with self._lock:
            hub = self._hubs.get(run_id)
            if hub is None:
                if await self._runs.get(run_id) is None:
                    raise LookupError(run_id)
                hub = RunHub(run_id=run_id)
                self._hubs[run_id] = hub
            if hub.task is not None:
                return hub

            query, config = await self._resolve_run(run_id)
            if config.require_plan_approval:
                hub.approval = asyncio.get_running_loop().create_future()
            key_fn = await self._build_get_key(config)
            llm = LlmCallCap(get_llm_provider(config, key_fn), config.max_llm_calls)
            search = get_search_provider(config, self._client, key_fn)
            crawl = get_crawl_provider(config, self._client, key_fn)
            hub.task = asyncio.create_task(
                self._run(run_id, query, config, hub, llm, search, crawl)
            )
            return hub

    async def _build_get_key(self, config: RunConfig) -> GetKey:
        """A per-run key resolver: vault credential first, env var as fallback.

        Vault lookups are async (DB), but the provider adapters call ``get_key``
        synchronously mid-request — so we pre-resolve the providers this run uses
        into a snapshot and close over it. Mock providers need no key.
        """
        resolved: dict[str, str] = {}
        if self._vault is not None:
            for provider in {
                config.llm_provider,
                config.search_provider,
                config.crawl_provider,
            }:
                secret = await self._vault.resolve(provider)
                if secret:
                    resolved[provider] = secret

        def get_key(provider: str) -> str | None:
            return resolved.get(provider) or env_get_key(provider)

        return get_key

    async def _resolve_run(self, run_id: str) -> tuple[str, RunConfig]:
        row = await self._runs.get(run_id)
        if row is None:
            raise LookupError(run_id)
        current = await self._config.current()
        config = RunConfig(
            llm_provider=row["llm_provider"] or "mock",
            llm_model=row["llm_model"] or "mock-1",
            search_provider=row["search_provider"] or "mock",
            crawl_provider=row["crawl_provider"] or "mock",
            language=row["language"] or "en",
            template=row["template"],
            require_plan_approval=bool(row["require_plan_approval"]),
            verification_level=current.get("verification_level", "light"),
        )
        return row["query"], config

    async def _run(self, run_id, query, config, hub, llm, search, crawl) -> None:
        engine = ResearchEngine(llm=llm, search=search, crawl=crawl)
        sink = self._make_sink(run_id, hub)
        approval = self._make_approval(config, hub)
        try:
            async with asyncio.timeout(config.timeout_s):
                await engine.run(run_id, query, config, sink, approval)
        except TimeoutError:
            # The engine was cancelled by the wallclock guard before it could
            # emit its own error, so emit one here.
            await self._emit_error(run_id, hub, f"run exceeded time limit of {config.timeout_s}s")
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - engine already emitted an `error` event
            logger.exception("run %s failed", run_id)
        finally:
            hub.finished.set()
            for queue in list(hub.subscribers):
                queue.put_nowait(None)

    async def _emit_error(self, run_id: str, hub: RunHub, message: str) -> None:
        """Persist + fan out an ``error`` event (wallclock-timeout path)."""
        await self._emit_out_of_band(run_id, hub, EventType.error, {"message": message})

    async def _emit_status(self, run_id: str, hub: RunHub | None, stage: str, message: str) -> None:
        """Persist + fan out a ``status`` event.

        Used to record a terminal ``cancelled`` state so a client that reconnects
        replays it as the last event (``_persist`` also flips the run's DB status).
        """
        await self._emit_out_of_band(
            run_id, hub, EventType.status, {"stage": stage, "message": message}
        )

    async def _emit_out_of_band(
        self, run_id: str, hub: RunHub | None, type_: EventType, data: dict
    ) -> None:
        """Emit an event that originates outside the engine (cancel/timeout).

        Allocates its ``seq`` from the hub's single authority under ``write_lock``
        so it can never collide with a concurrently-emitting engine (the old
        ``count_by_run`` path could duplicate a seq and hit the events PK). These
        are terminal signals, so they are written even when the hub is cancelled.
        """
        if hub is None:
            # Never started (no task/subscribers): no concurrent writer to race.
            seq = await self._events.count_by_run(run_id)
            event = Event(seq=seq, run_id=run_id, ts=now_ms(), type=type_, data=data)
            await self._persist(run_id, event)
            return
        async with hub.write_lock:
            event = Event(seq=hub.next_seq, run_id=run_id, ts=now_ms(), type=type_, data=data)
            hub.next_seq += 1
            await self._persist(run_id, event)
            for queue in list(hub.subscribers):
                queue.put_nowait(event)

    def _make_sink(self, run_id: str, hub: RunHub) -> Sink:
        async def sink(event: Event) -> None:
            async with hub.write_lock:
                # Drop anything the engine emits after cancellation so a late
                # done/error can't overwrite the terminal 'cancelled' state.
                if hub.cancelled:
                    return
                event.seq = hub.next_seq
                hub.next_seq += 1
                await self._persist(run_id, event)
                for queue in list(hub.subscribers):
                    queue.put_nowait(event)

        return sink

    def _make_approval(self, config: RunConfig, hub: RunHub):
        if not config.require_plan_approval:
            return None

        async def approval(plan) -> list[PlanSection]:
            # ``hub.approval`` is created eagerly in ``ensure_started`` so a POST
            # /plan that arrives the instant ``awaiting_plan`` is seen still lands
            # on a live future (no race with the engine reaching this await).
            return await hub.approval

        return approval

    async def submit_plan(self, run_id: str, submit: PlanSubmit) -> bool:
        """Resolve a paused run's plan future. Returns False if not awaiting."""
        hub = self._hubs.get(run_id)
        if hub is None or hub.approval is None or hub.approval.done() or hub.cancelled:
            return False
        if submit.sections:
            sections = [
                PlanSection(id=s.id, title=s.title, goal=s.goal, queries=s.queries)
                for s in submit.sections
            ]
            await self._replace_sections(run_id, sections)
        else:
            sections = await self._sections_from_db(run_id)
        hub.approval.set_result(sections)
        return True

    async def _sections_from_db(self, run_id: str) -> list[PlanSection]:
        return [
            PlanSection(
                id=row["id"],
                title=row["title"] or "",
                goal=row["goal"] or "",
                queries=json.loads(row["queries_json"]) if row["queries_json"] else [],
            )
            for row in await self._runs.get_sections(run_id)
        ]

    async def _replace_sections(self, run_id: str, sections: list[PlanSection]) -> None:
        await self._runs.delete_sections(run_id)
        for idx, section in enumerate(sections):
            await self._runs.upsert_section(
                run_id,
                id=section.id,
                idx=idx,
                title=section.title,
                goal=section.goal,
                queries=section.queries,
                status="pending",
            )

    async def _persist(self, run_id: str, event: Event) -> None:
        now = _now_iso()
        await self._events.append(
            run_id,
            seq=event.seq,
            type_=event.type.value,
            data_json=json.dumps(event.data),
            ts=event.ts,
        )
        data = event.data
        et = event.type
        if et == EventType.plan:
            for idx, section in enumerate(data.get("sections", [])):
                await self._runs.upsert_section(
                    run_id,
                    id=section["id"],
                    idx=idx,
                    title=section.get("title", ""),
                    goal=section.get("goal", ""),
                    queries=section.get("queries", []),
                    status="pending",
                )
        elif et == EventType.section_start:
            await self._runs.set_section_status(run_id, data["section_id"], "researching")
        elif et == EventType.source:
            source = data.get("source", {})
            await self._runs.insert_source(
                run_id,
                ref_num=source["id"],
                title=source.get("title", ""),
                url=source.get("url", ""),
                snippet=source.get("snippet", ""),
                section_id=source.get("section_id"),
            )
        elif et == EventType.claim:
            await self._claims.create(
                run_id,
                id=data["claim_id"],
                text=data.get("text", ""),
                source_ids=list(data.get("source_ids", [])),
                quote=data.get("quote", ""),
                section_id=data.get("section_id"),
                entity=data.get("entity"),
                attribute=data.get("attribute"),
                stance=data.get("stance"),
                created_at=now,
            )
        elif et == EventType.verification:
            await self._verifications.upsert(
                run_id,
                claim_id=data["claim_id"],
                verdict=data.get("verdict", ""),
                confidence=data.get("confidence"),
                rationale=data.get("rationale", ""),
                verifier_model=data.get("verifier_model"),
                created_at=now,
            )
        elif et == EventType.contradiction:
            claim_ids = data.get("claim_ids", ["", ""])
            await self._contradictions.create(
                run_id,
                id=data["id"],
                claim_id_a=claim_ids[0],
                claim_id_b=claim_ids[1],
                entity=data.get("entity"),
                attribute=data.get("attribute"),
                note=data.get("note", ""),
            )
        elif et == EventType.section_done:
            await self._runs.set_section_summary(
                run_id, data["section_id"], data.get("summary", ""), "done"
            )
        elif et == EventType.report:
            await self._runs.set_report(
                run_id, data.get("markdown", ""), data.get("title", ""), now
            )
        elif et == EventType.status:
            await self._runs.update_status(run_id, data.get("stage", ""), now)
        elif et == EventType.awaiting_plan:
            await self._runs.update_status(run_id, RunStatus.awaiting_plan.value, now)
        elif et == EventType.done:
            await self._runs.update_status(run_id, RunStatus.done.value, now)
        elif et == EventType.error:
            await self._runs.update_status(
                run_id, RunStatus.error.value, now, error=data.get("message")
            )

    async def subscribe(self, run_id: str) -> AsyncIterator[Event]:
        await self.ensure_started(run_id)
        hub = self._hubs[run_id]
        queue: asyncio.Queue = asyncio.Queue()
        hub.subscribers.add(queue)
        # If the run already finished, guarantee a stop signal for this late
        # subscriber (see the atomic add/check reasoning in _run's fan-out).
        if hub.finished.is_set():
            queue.put_nowait(None)
        try:
            seen = -1
            for row in await self._events.list_by_run(run_id):
                event = _row_to_event(run_id, row)
                yield event
                seen = event.seq
                if event.type in _TERMINAL:
                    return
            while True:
                item = await queue.get()
                if item is None:
                    break
                if item.seq <= seen:
                    continue  # already replayed from the DB
                yield item
                seen = item.seq
                if item.type in _TERMINAL:
                    break
        finally:
            hub.subscribers.discard(queue)

    async def cancel(self, run_id: str) -> None:
        row = await self._runs.get(run_id)
        if row is None or row["status"] in {
            RunStatus.done.value,
            RunStatus.error.value,
            RunStatus.cancelled.value,
        }:
            return  # nothing to cancel — unknown or already finished
        hub = self._hubs.get(run_id)
        # Mark cancelled first so the sink drops any further engine events, then
        # emit the terminal 'cancelled' status and fan it out BEFORE tearing the
        # task down. Cancelling the task/approval makes the engine push its
        # end-of-stream sentinel, which would otherwise close the subscriber
        # stream before the cancelled event is delivered.
        if hub is not None:
            hub.cancelled = True
        await self._emit_status(run_id, hub, RunStatus.cancelled.value, "Cancelled")
        if hub is not None:
            # Unblock a pending plan-approval wait so a racing submit_plan can't
            # 'succeed' on a cancelled run, then stop the background task.
            if hub.approval is not None and not hub.approval.done():
                hub.approval.cancel()
            if hub.task is not None and not hub.task.done():
                hub.task.cancel()

    async def aclose(self) -> None:
        for hub in self._hubs.values():
            if hub.task is not None and not hub.task.done():
                hub.task.cancel()
        for hub in self._hubs.values():
            if hub.task is not None:
                try:
                    await hub.task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass
        await self._client.aclose()
