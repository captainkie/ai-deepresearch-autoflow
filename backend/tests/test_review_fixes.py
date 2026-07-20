"""Regression tests for the M1 code-review fixes.

- Engine surfaces the original (unwrapped) error and cancels sibling sections
  on the first failure — no events after `error` (TaskGroup, not gather).
- Planner rejects a degenerate plan with zero sections instead of silently
  producing an empty report.
- Researcher does not waste a reflect LLM call on the final allowed iteration.
- A crawl that raises does not abort the whole fetch batch.
"""

from __future__ import annotations

import json as jsonlib  # avoid shadowing by the `json: bool` provider param
from collections.abc import AsyncIterator

import pytest

from app.core.engine import ResearchEngine
from app.core.events import EventEmitter, ListSink
from app.core.planner import Planner
from app.core.researcher import Researcher
from app.core.sources import SourceRegistry
from app.models.schemas import EventType, PlanSection, RunConfig
from app.providers.crawl.mock import MockCrawlProvider
from app.providers.llm.mock import MockLLMProvider
from app.providers.search.mock import MockSearchProvider


class _NoStreamMixin:
    async def stream(
        self,
        messages: list[dict],
        *,
        tag: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        yield ""


async def test_engine_error_surfaces_unwrapped_and_is_terminal() -> None:
    class BoomSearch:
        async def search(self, query: str, k: int = 6):
            raise RuntimeError("search boom")

    sink = ListSink()
    engine = ResearchEngine(llm=MockLLMProvider(), search=BoomSearch(), crawl=MockCrawlProvider())

    with pytest.raises(RuntimeError, match="search boom"):
        await engine.run("r1", "Brand X", RunConfig(), sink)

    types = [e.type for e in sink.events]
    assert EventType.error in types
    # error is terminal: no orphaned sibling emitted anything after it.
    assert types[-1] == EventType.error


async def test_planner_empty_sections_raises() -> None:
    class EmptyPlanLLM(_NoStreamMixin):
        async def complete(
            self, messages, *, tag=None, temperature=0.3, max_tokens=None, json=False
        ):
            return '{"brief": {"objective": "X"}, "sections": []}'

    with pytest.raises(ValueError, match="no sections"):
        await Planner(EmptyPlanLLM()).plan("X", RunConfig())


async def test_researcher_skips_reflect_on_final_iteration() -> None:
    reflect_calls = 0

    class SpyLLM(MockLLMProvider):
        async def complete(
            self, messages, *, tag=None, temperature=0.3, max_tokens=None, json=False
        ):
            nonlocal reflect_calls
            if tag == "reflect":
                reflect_calls += 1
                return jsonlib.dumps({"need_more": True, "queries": ["more query"]})
            return await super().complete(
                messages, tag=tag, temperature=temperature, max_tokens=max_tokens, json=json
            )

    config = RunConfig(max_iters_per_section=2)
    researcher = Researcher(
        llm=SpyLLM(),
        search=MockSearchProvider(),
        crawl=MockCrawlProvider(),
        registry=SourceRegistry(),
        emitter=EventEmitter("r", ListSink()),
        config=config,
    )
    await researcher.research(PlanSection(id="s1", title="T", goal="G", queries=["q1"]))

    # iter 0 reflects (need_more=True → continue); the final iter (1) must NOT reflect.
    assert reflect_calls == 1


async def test_fetch_batch_survives_a_raising_crawl() -> None:
    class FlakyCrawl(MockCrawlProvider):
        async def fetch(self, url: str):
            if url.endswith("/0"):
                raise RuntimeError("crawl boom")
            return await super().fetch(url)

    registry = SourceRegistry()
    sink = ListSink()
    researcher = Researcher(
        llm=MockLLMProvider(),
        search=MockSearchProvider(),
        crawl=FlakyCrawl(),
        registry=registry,
        emitter=EventEmitter("r", sink),
        config=RunConfig(max_iters_per_section=1, fetch_per_query=3),
    )
    summary = await researcher.research(PlanSection(id="s1", title="T", goal="G", queries=["q1"]))

    # The batch did not abort: a section_done was emitted and some sources survived.
    assert summary
    assert any(e.type == EventType.section_done for e in sink.events)
    assert len(registry.all()) >= 1
