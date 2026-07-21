from __future__ import annotations

import json

from app.core.events import EventEmitter, ListSink
from app.core.researcher import Researcher
from app.core.sources import SourceRegistry
from app.models.schemas import EventType, PlanSection, RunConfig, SearchResult
from app.providers.crawl.mock import MockCrawlProvider
from app.providers.llm.mock import MockLLMProvider
from app.providers.search.mock import MockSearchProvider


def _make_researcher(registry, emitter, config, *, search=None, llm=None):
    return Researcher(
        llm=llm or MockLLMProvider(),
        search=search or MockSearchProvider(),
        crawl=MockCrawlProvider(),
        registry=registry,
        emitter=emitter,
        config=config,
    )


class _ConstantSearch:
    """Returns the same three URLs for every query (so later rounds add 0 sources)."""

    async def search(self, query: str, n: int) -> list[SearchResult]:
        return [SearchResult(title=f"S{i}", url=f"https://example.com/const/{i}") for i in range(3)]


class _KeepGoingLLM:
    """Delegates to the mock, but its reflection always asks for more (fresh query)."""

    def __init__(self) -> None:
        self._mock = MockLLMProvider()
        self._n = 0

    async def complete(self, messages, *, tag=None, **kwargs) -> str:
        if tag == "reflect":
            self._n += 1
            return json.dumps({"need_more": True, "queries": [f"followup-{self._n}"]})
        return await self._mock.complete(messages, tag=tag, **kwargs)

    def stream(self, messages, *, tag=None, **kwargs):
        return self._mock.stream(messages, tag=tag, **kwargs)


async def test_research_emits_expected_events_and_registers_sources():
    sink = ListSink()
    registry = SourceRegistry()
    emitter = EventEmitter("run-1", sink)
    section = PlanSection(
        id="s1",
        title="Overview",
        goal="Establish background",
        queries=["brand X overview", "brand X background"],
    )
    researcher = _make_researcher(registry, emitter, RunConfig())

    summary = await researcher.research(section)

    types = [e.type for e in sink.events]
    assert types[0] == EventType.section_start
    assert types[-1] == EventType.section_done
    assert EventType.search in types
    assert EventType.source in types
    assert EventType.note in types
    assert summary
    assert len(registry.all()) >= 1
    assert all(s.section_id == "s1" for s in registry.all())


async def test_research_dedups_sources_across_queries():
    sink = ListSink()
    registry = SourceRegistry()
    emitter = EventEmitter("run-1", sink)
    # Two identical queries produce identical urls -> deduped in the registry.
    section = PlanSection(id="s1", title="T", goal="G", queries=["same query", "same query"])
    researcher = _make_researcher(registry, emitter, RunConfig(fetch_per_query=3))

    await researcher.research(section)

    urls = [s.url for s in registry.all()]
    assert len(urls) == len(set(urls))


# --- Engine v2: verification_level ---------------------------------------- #


async def test_v2_light_emits_claim_and_verification_events():
    sink = ListSink()
    registry = SourceRegistry()
    emitter = EventEmitter("run-1", sink)
    section = PlanSection(id="s1", title="Overview", goal="Establish background", queries=["q"])
    researcher = _make_researcher(registry, emitter, RunConfig(verification_level="light"))

    summary = await researcher.research(section)

    types = [e.type for e in sink.events]
    assert EventType.claim in types
    assert EventType.verification in types
    assert types[0] == EventType.section_start
    assert types[-1] == EventType.section_done
    # Claim events precede their verifications; notes come after verifications.
    assert types.index(EventType.claim) < types.index(EventType.verification)
    assert summary


async def test_off_uses_legacy_path_without_claim_events():
    sink = ListSink()
    registry = SourceRegistry()
    emitter = EventEmitter("run-1", sink)
    section = PlanSection(id="s1", title="Overview", goal="G", queries=["q"])
    researcher = _make_researcher(registry, emitter, RunConfig(verification_level="off"))

    await researcher.research(section)

    types = [e.type for e in sink.events]
    # Back-compat: legacy path emits notes/sources but no claim/verification events.
    assert EventType.claim not in types
    assert EventType.verification not in types
    assert EventType.note in types
    assert EventType.source in types
    assert types[-1] == EventType.section_done


async def test_adaptive_stop_on_diminishing_returns():
    sink = ListSink()
    registry = SourceRegistry()
    emitter = EventEmitter("run-1", sink)
    section = PlanSection(id="s1", title="T", goal="G", queries=["q0"])
    # Reflection always asks for more, but every query returns the same 3 URLs, so
    # the 2nd round adds 0 new sources → the loop must stop despite max_iters=6.
    researcher = _make_researcher(
        registry,
        emitter,
        RunConfig(verification_level="light", max_iters_per_section=6),
        search=_ConstantSearch(),
        llm=_KeepGoingLLM(),
    )

    await researcher.research(section)

    searches = [e for e in sink.events if e.type == EventType.search]
    sources = [e for e in sink.events if e.type == EventType.source]
    assert len(sources) == 3  # only the first round adds sources
    assert len(searches) == 2  # round 0 (q0) + one diminishing round, then stop
