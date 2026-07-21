from __future__ import annotations

from app.core.events import EventEmitter, ListSink
from app.core.synthesizer import (
    build_comparison_table,
    ensure_sources_section,
    extract_title,
    summarize_confidence,
    synthesize,
)
from app.models.schemas import (
    Claim,
    Contradiction,
    EventType,
    Language,
    PlanSection,
    ResearchBrief,
    RunConfig,
    Source,
    Verification,
)
from app.prompts.templates import EntityField
from app.providers.llm.mock import MockLLMProvider


def _claim(cid, entity, attr, text, sids):
    return Claim(id=cid, text=text, entity=entity, attribute=attr, source_ids=sids, quote="q")


def _ver(cid, verdict="supported"):
    return Verification(claim_id=cid, verdict=verdict, confidence=0.9)


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


# --- M3.5b: comparison-table synthesis ------------------------------------- #

_SCHEMA = [
    EntityField("pricing", "Pricing", "text"),
    EntityField("audience", "Audience", "text"),
]


def test_comparison_table_pivots_entities_by_attribute():
    claims = [
        _claim("c1", "BrandX", "pricing", "$9/mo", [1]),
        _claim("c2", "BrandX", "audience", "Gen Z", [1, 2]),
        _claim("c3", "BrandY", "pricing", "$12/mo", [3]),
    ]
    verifs = [_ver("c1"), _ver("c2"), _ver("c3")]
    table = build_comparison_table(_SCHEMA, claims, verifs)

    assert "Pricing" in table and "Audience" in table  # column headers
    assert "BrandX" in table and "BrandY" in table  # entity rows
    assert "$9/mo" in table and "[1]" in table
    assert "$12/mo" in table and "[3]" in table
    assert "—" in table  # BrandY has no audience claim → placeholder
    assert "---" in table  # markdown header separator


def test_comparison_table_excludes_unsupported_claims():
    claims = [
        _claim("c1", "BrandX", "pricing", "$9/mo", [1]),
        _claim("c2", "BrandX", "pricing", "$999/mo", [2]),  # unsupported → excluded
    ]
    verifs = [_ver("c1", "supported"), _ver("c2", "unsupported")]
    table = build_comparison_table(_SCHEMA, claims, verifs)
    assert "$9/mo" in table
    assert "$999/mo" not in table


def test_comparison_table_confidence_marker_reflects_corroboration():
    high = build_comparison_table(
        _SCHEMA, [_claim("c1", "X", "pricing", "$9", [1, 2])], [_ver("c1")]
    )
    med = build_comparison_table(_SCHEMA, [_claim("c2", "X", "pricing", "$9", [1])], [_ver("c2")])
    assert "🟢" in high  # ≥2 sources → high
    assert "🟡" in med  # single source → medium


def test_summarize_confidence_wire_shape():
    claims = [
        _claim("c1", "X", "pricing", "t1", [1, 2]),  # supported ×2 → high
        _claim("c2", "X", "audience", "t2", [1]),  # supported ×1 → medium
        _claim("c3", "Y", "pricing", "t3", [1]),  # unsupported → low
    ]
    verifs = [_ver("c1"), _ver("c2"), _ver("c3", "unsupported")]
    contradictions = [Contradiction(id="x", claim_id_a="c1", claim_id_b="c3")]
    summary = summarize_confidence(claims, verifs, contradictions)
    assert summary == {"high": 1, "medium": 1, "low": 1, "contradictions": 1}


async def test_synthesize_entity_mode_projects_only_verified_claims():
    sink = ListSink()
    emitter = EventEmitter("run-e", sink)
    brief = ResearchBrief(objective="Compare brands", key_questions=["q"])
    sections = [PlanSection(id="s1", title="Overview", goal="ctx")]
    sources = [Source(id=1, title="A", url="https://a"), Source(id=2, title="B", url="https://b")]
    config = RunConfig(template="competitor_brand")
    claims = [
        _claim("c1", "BrandX", "pricing", "$9/mo", [1]),
        _claim("c2", "BrandY", "pricing", "$12/mo", [2]),
        _claim("c3", "BrandX", "channels", "spammy ad tactics", [1]),  # unsupported
    ]
    verifs = [_ver("c1"), _ver("c2"), _ver("c3", "unsupported")]

    md, title = await synthesize(
        brief,
        sections,
        sources,
        MockLLMProvider(),
        emitter.emit,
        config,
        claims=claims,
        verifications=verifs,
        contradictions=[],
    )

    # streamed the report
    assert any(e.type == EventType.report_delta for e in sink.events)
    # comparison table pivots the verified claims
    assert "## Comparison" in md
    assert "BrandX" in md and "BrandY" in md and "$9/mo" in md and "$12/mo" in md
    # the report body = only verified claims; the unsupported one is quarantined
    # to the Unverified appendix.
    body, sep, appendix = md.partition("Unverified")
    assert sep, "report must have an Unverified appendix section"
    assert "spammy ad tactics" not in body  # not in the verified body/table
    assert "spammy ad tactics" in appendix  # only in the appendix
    assert "$9/mo" in body
    assert "## Sources" in md
    assert title


async def test_synthesize_non_entity_template_skips_comparison_table():
    sink = ListSink()
    emitter = EventEmitter("run-n", sink)
    brief = ResearchBrief(objective="Some topic", key_questions=["q"])
    sections = [PlanSection(id="s1", title="Overview", goal="ctx")]
    sources = [Source(id=1, title="A", url="https://a")]
    config = RunConfig(template="deep_research")  # narrative, not entity_mode

    md, _ = await synthesize(
        brief,
        sections,
        sources,
        MockLLMProvider(),
        emitter.emit,
        config,
        claims=[_claim("c1", "X", "pricing", "t", [1])],
        verifications=[_ver("c1")],
    )
    assert "## Comparison" not in md  # no comparison table for narrative templates
