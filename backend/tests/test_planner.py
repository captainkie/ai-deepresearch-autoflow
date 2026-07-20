from __future__ import annotations

from app.core.planner import Planner
from app.models.schemas import Plan, PlanSection, RunConfig
from app.providers.llm.mock import MockLLMProvider


async def test_planner_returns_valid_plan():
    plan = await Planner(MockLLMProvider()).plan("Analyze brand X", RunConfig())
    assert isinstance(plan, Plan)
    assert len(plan.sections) >= 2
    assert all(isinstance(s, PlanSection) for s in plan.sections)
    assert all(s.goal for s in plan.sections)
    assert all(len(s.queries) >= 1 for s in plan.sections)
    ids = [s.id for s in plan.sections]
    assert len(ids) == len(set(ids))


async def test_planner_clamps_to_max_sections():
    plan = await Planner(MockLLMProvider()).plan("Analyze brand X", RunConfig(max_sections=1))
    assert len(plan.sections) == 1
