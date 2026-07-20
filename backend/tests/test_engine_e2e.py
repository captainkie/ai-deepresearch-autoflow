from __future__ import annotations

import subprocess
import sys

import pytest

from app.config import load_run_config
from app.core.engine import ResearchEngine
from app.core.events import ListSink
from app.models.schemas import EventType, RunConfig, RunStatus
from app.providers.crawl.mock import MockCrawlProvider
from app.providers.llm.mock import MockLLMProvider
from app.providers.search.mock import MockSearchProvider


def _engine(llm=None):
    return ResearchEngine(
        llm=llm or MockLLMProvider(),
        search=MockSearchProvider(),
        crawl=MockCrawlProvider(),
    )


def _first_index(events, predicate):
    return next(i for i, e in enumerate(events) if predicate(e))


async def test_engine_e2e_event_order_and_report():
    sink = ListSink()
    markdown = await _engine().run(
        "run-1", "Analyze competitor brand: ExampleCo", RunConfig(), sink
    )
    events = sink.events
    types = [e.type for e in events]

    # Monotonic, contiguous seq starting at 0.
    assert [e.seq for e in events] == list(range(len(events)))

    # Starts at status(planning); ends at done; no awaiting_plan in auto mode.
    assert events[0].type == EventType.status
    assert events[0].data["stage"] == RunStatus.planning.value
    assert events[-1].type == EventType.done
    assert EventType.awaiting_plan not in types

    idx_plan = _first_index(events, lambda e: e.type == EventType.plan)
    idx_first_start = _first_index(events, lambda e: e.type == EventType.section_start)
    last_section_done = max(
        i for i, e in enumerate(events) if e.type == EventType.section_done
    )
    idx_writing = _first_index(
        events,
        lambda e: e.type == EventType.status and e.data["stage"] == RunStatus.writing.value,
    )
    idx_first_delta = _first_index(events, lambda e: e.type == EventType.report_delta)
    idx_report = _first_index(events, lambda e: e.type == EventType.report)
    idx_done = _first_index(events, lambda e: e.type == EventType.done)

    assert idx_plan < idx_first_start
    assert idx_first_start < last_section_done
    assert last_section_done < idx_writing < idx_first_delta < idx_report < idx_done

    # Per section: section_start precedes its section_done.
    for e in events:
        if e.type == EventType.section_start:
            sid = e.data["section_id"]
            start_i = _first_index(
                events,
                lambda ev, sid=sid: ev.type == EventType.section_start
                and ev.data["section_id"] == sid,
            )
            done_i = _first_index(
                events,
                lambda ev, sid=sid: ev.type == EventType.section_done
                and ev.data["section_id"] == sid,
            )
            assert start_i < done_i

    report_event = events[idx_report]
    assert report_event.data["markdown"].strip()
    assert "## Sources" in report_event.data["markdown"]
    assert events[-1].data["source_count"] >= 1
    assert markdown.strip()


async def test_engine_hitl_awaiting_plan_and_approval():
    sink = ListSink()
    captured = {}

    async def approval(plan):
        captured["plan"] = plan
        return plan.sections[:1]  # approve just the first section

    await _engine().run("run-2", "brand X", RunConfig(require_plan_approval=True), sink, approval)

    types = [e.type for e in sink.events]
    assert EventType.awaiting_plan in types
    assert "plan" in captured
    section_starts = [e for e in sink.events if e.type == EventType.section_start]
    assert len(section_starts) == 1


class _BoomLLM:
    async def complete(self, *args, **kwargs):
        raise RuntimeError("boom")

    async def stream(self, *args, **kwargs):
        if False:  # pragma: no cover - makes this an async generator
            yield ""


async def test_engine_emits_error_on_failure():
    sink = ListSink()
    with pytest.raises(RuntimeError):
        await _engine(llm=_BoomLLM()).run("run-3", "q", RunConfig(), sink)
    assert any(e.type == EventType.error for e in sink.events)


def test_load_run_config_override_beats_env(monkeypatch):
    monkeypatch.setenv("AUTOFLOW_LLM_PROVIDER", "mock")
    monkeypatch.setenv("AUTOFLOW_LANGUAGE", "th")
    cfg = load_run_config(language="en")  # explicit override wins over env
    assert cfg.llm_provider == "mock"
    assert cfg.language.value == "en"


def test_cli_research_smoke():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.cli",
            "research",
            "Analyze competitor brand: ExampleCo",
            "--lang",
            "en",
            "--llm",
            "mock",
            "--search",
            "mock",
            "--crawl",
            "mock",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "## Sources" in result.stdout
