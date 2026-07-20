from __future__ import annotations

from app.core.events import EventEmitter, ListSink
from app.core.researcher import Researcher
from app.core.sources import SourceRegistry
from app.models.schemas import EventType, PlanSection, RunConfig
from app.providers.crawl.mock import MockCrawlProvider
from app.providers.llm.mock import MockLLMProvider
from app.providers.search.mock import MockSearchProvider


def _make_researcher(registry, emitter, config):
    return Researcher(
        llm=MockLLMProvider(),
        search=MockSearchProvider(),
        crawl=MockCrawlProvider(),
        registry=registry,
        emitter=emitter,
        config=config,
    )


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
