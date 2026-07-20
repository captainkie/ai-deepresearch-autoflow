from __future__ import annotations

from app.core.events import EventEmitter, ListSink
from app.core.synthesizer import ensure_sources_section, extract_title, synthesize
from app.models.schemas import EventType, PlanSection, ResearchBrief, Source
from app.providers.llm.mock import MockLLMProvider


async def test_synthesize_streams_and_lists_all_sources():
    sink = ListSink()
    emitter = EventEmitter("run-1", sink)
    brief = ResearchBrief(objective="Analyze brand X", key_questions=["q"])
    sections = [PlanSection(id="s1", title="Overview", goal="ctx", queries=["q"])]
    sources = [
        Source(id=1, title="A", url="https://example.com/a"),
        Source(id=2, title="B", url="https://example.com/b"),
    ]

    markdown, title = await synthesize(brief, sections, sources, MockLLMProvider(), emitter.emit)

    deltas = [e for e in sink.events if e.type == EventType.report_delta]
    assert len(deltas) >= 1
    assert "## Sources" in markdown
    assert markdown.count("## Sources") == 1
    assert "[1]" in markdown
    assert "[2]" in markdown
    assert title


def test_extract_title():
    assert extract_title("# Hello World\n\nbody") == "Hello World"
    assert extract_title("no heading here") == ""


def test_ensure_sources_replaces_placeholder_and_lists_ids():
    md = "# T\n\nbody\n\n## Sources\n"
    sources = [Source(id=1, title="A", url="https://a"), Source(id=2, title="B", url="https://b")]
    out = ensure_sources_section(md, sources)
    assert out.count("## Sources") == 1
    assert "[1] A — https://a" in out
    assert "[2] B — https://b" in out


def test_ensure_sources_appends_when_absent():
    out = ensure_sources_section("# T\n\nbody only", [Source(id=1, title="A", url="https://a")])
    assert "## Sources" in out
    assert "[1] A — https://a" in out
