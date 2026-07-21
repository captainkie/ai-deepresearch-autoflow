from __future__ import annotations

from app.models.schemas import PageContent, PlanSection, ResearchBrief, RunConfig, Source
from app.prompts.planner import build_planner_messages
from app.prompts.researcher import compress_messages, reflect_messages, summarize_messages
from app.prompts.synthesizer import build_report_messages
from app.prompts.templates import TEMPLATES, get_template, language_directive


def _is_message_list(messages: object) -> bool:
    return (
        isinstance(messages, list)
        and len(messages) > 0
        and all(isinstance(m, dict) and m.get("role") and m.get("content") for m in messages)
    )


def test_templates_present():
    for key in ("deep_research", "competitor_brand", "market_landscape"):
        assert key in TEMPLATES
        assert TEMPLATES[key].report_outline
    assert get_template("unknown").id == "deep_research"


def test_engine_v2_template_set_present():
    # M3.5b ships the structured marketing set (Competitor Teardown maps to the
    # existing competitor_brand key so older runs/tests keep working).
    for key in (
        "deep_research",
        "competitor_brand",
        "market_landscape",
        "swot",
        "pricing_analysis",
    ):
        assert key in TEMPLATES


def test_templates_carry_entity_metadata():
    from app.prompts.templates import EntityField

    # A plain narrative template: no entity comparison.
    dr = TEMPLATES["deep_research"]
    assert dr.entity_mode is False
    assert dr.entity_schema == ()

    # An entity template pivots verified claims into a comparison table.
    comp = TEMPLATES["competitor_brand"]
    assert comp.entity_mode is True
    assert len(comp.entity_schema) >= 2
    assert all(isinstance(f, EntityField) for f in comp.entity_schema)
    assert all(f.key and f.label and f.type in {"text", "list"} for f in comp.entity_schema)

    # Every template declares a default verification level.
    for t in TEMPLATES.values():
        assert t.verification_level in {"off", "light", "strict"}


def test_language_directive():
    from app.models.schemas import Language

    assert language_directive(Language.th) == "Write the report in Thai."
    assert language_directive(Language.en) == "Write the report in English."


def test_planner_messages_embed_query():
    msgs = build_planner_messages("brand X", RunConfig(), get_template("deep_research"))
    assert _is_message_list(msgs)
    assert any("QUERY: brand X" in m["content"] for m in msgs)


def test_researcher_message_builders():
    page = PageContent(url="https://example.com/a", title="A", text="body")
    assert _is_message_list(summarize_messages("goal", page))
    reflect = reflect_messages("goal", "notes")
    assert _is_message_list(reflect)
    assert any("need_more" in m["content"] for m in reflect)
    compress = compress_messages("goal", "notes")
    assert _is_message_list(compress)
    assert any("GOAL: goal" in m["content"] for m in compress)


def test_synthesizer_messages_embed_objective():
    brief = ResearchBrief(objective="brand X", key_questions=["q"])
    sections = [PlanSection(id="s1", title="Overview", goal="ctx", queries=["q"])]
    sources = [Source(id=1, title="A", url="https://example.com/a", snippet="s")]
    msgs = build_report_messages(brief, sections, sources, RunConfig())
    assert _is_message_list(msgs)
    assert any("OBJECTIVE: brand X" in m["content"] for m in msgs)
    assert any("## Sources" in m["content"] for m in msgs)
