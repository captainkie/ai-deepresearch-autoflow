from __future__ import annotations

from app.core.events import EventEmitter, ListSink
from app.core.synthesizer import ensure_sources_section, extract_title, synthesize
from app.models.schemas import EventType, Language, PlanSection, ResearchBrief, RunConfig, Source
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


def test_ensure_sources_dedupes_localized_thai_heading():
    # A Thai report whose body already ends with a localized sources heading must
    # not end up with two source sections (regression: only "Sources" was matched).
    md = "# T\n\nเนื้อหา\n\n## แหล่งอ้างอิง\n"
    out = ensure_sources_section(md, [Source(id=1, title="A", url="https://a")], "แหล่งอ้างอิง")
    assert out.count("## แหล่งอ้างอิง") == 1
    assert "## Sources" not in out
    assert "[1] A — https://a" in out


def test_ensure_sources_localized_strips_english_heading_too():
    # If the writer emitted an English "Sources" heading in a Thai report, the
    # localized pass still collapses it into a single localized section.
    md = "# T\n\nเนื้อหา\n\n## Sources\n"
    out = ensure_sources_section(md, [Source(id=1, title="A", url="https://a")], "แหล่งอ้างอิง")
    assert out.count("## แหล่งอ้างอิง") == 1
    assert "## Sources" not in out


async def test_synthesize_thai_has_single_localized_sources_heading():
    sink = ListSink()
    emitter = EventEmitter("run-th", sink)
    brief = ResearchBrief(objective="แบรนด์ X", key_questions=["q"])
    sections = [PlanSection(id="s1", title="ภาพรวม", goal="ctx", queries=["q"])]
    sources = [Source(id=1, title="A", url="https://example.com/a")]
    config = RunConfig(language=Language.th)

    markdown, _ = await synthesize(
        brief, sections, sources, MockLLMProvider(), emitter.emit, config
    )

    assert "บทสรุปผู้บริหาร" in markdown  # body rendered in Thai
    assert markdown.count("## แหล่งอ้างอิง") == 1  # exactly one sources heading
    assert "## Sources" not in markdown  # no duplicate English heading
