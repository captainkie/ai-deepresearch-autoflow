from __future__ import annotations

from app.models.schemas import (
    EventType,
    Language,
    Plan,
    PlanSection,
    ResearchBrief,
    RunConfig,
    RunStatus,
)


def test_runconfig_defaults():
    cfg = RunConfig()
    assert cfg.llm_provider == "mock"
    assert cfg.llm_model == "mock-1"
    assert cfg.search_provider == "mock"
    assert cfg.crawl_provider == "mock"
    assert cfg.language == Language.en
    assert cfg.require_plan_approval is False
    assert cfg.max_sections == 6
    assert cfg.max_iters_per_section == 2


def test_plan_round_trips_from_dict():
    data = {
        "brief": {"objective": "Study brand X", "key_questions": ["q1", "q2"]},
        "sections": [
            {"id": "s1", "title": "Overview", "goal": "Understand", "queries": ["a"]},
            {"id": "s2", "title": "Market", "goal": "Compare", "queries": ["b", "c"]},
        ],
    }
    plan = Plan.model_validate(data)
    assert isinstance(plan.brief, ResearchBrief)
    assert plan.brief.objective == "Study brand X"
    assert len(plan.sections) == 2
    assert all(isinstance(s, PlanSection) for s in plan.sections)
    assert plan.model_dump()["sections"][1]["queries"] == ["b", "c"]


def test_event_type_values():
    assert EventType.report_delta.value == "report_delta"
    assert EventType.done.value == "done"
    assert EventType.awaiting_plan.value == "awaiting_plan"


def test_run_status_values():
    assert RunStatus.awaiting_plan.value == "awaiting_plan"
    assert RunStatus.done.value == "done"
