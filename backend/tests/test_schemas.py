from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.schemas import (
    Claim,
    ConfidenceLevel,
    ConfidenceSummary,
    Contradiction,
    EventType,
    Language,
    Plan,
    PlanSection,
    ResearchBrief,
    RunConfig,
    RunStatus,
    Verdict,
    Verification,
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


# --- Engine v2: claim / verification / contradiction schemas -------------- #


def test_event_type_has_engine_v2_values():
    assert EventType.claim.value == "claim"
    assert EventType.verification.value == "verification"
    assert EventType.contradiction.value == "contradiction"


def test_verdict_values():
    assert {v.value for v in Verdict} == {
        "supported",
        "partial",
        "unsupported",
        "contradicted",
    }


def test_claim_requires_source_and_quote_defaults():
    claim = Claim(id="c1", text="BrandX is priced at $9.", source_ids=[1], quote="priced at $9")
    assert claim.id == "c1"
    assert claim.source_ids == [1]
    assert claim.quote == "priced at $9"
    # Optional entity/attribute tagging defaults to None.
    assert claim.entity is None
    assert claim.attribute is None
    assert claim.section_id is None


def test_claim_round_trips_with_entity_tagging():
    claim = Claim.model_validate(
        {
            "id": "c2",
            "section_id": "s1",
            "text": "BrandX targets Gen Z.",
            "entity": "BrandX",
            "attribute": "target_segment",
            "quote": "targets Gen Z",
            "source_ids": [2, 3],
            "stance": "positive",
        }
    )
    assert claim.entity == "BrandX"
    assert claim.attribute == "target_segment"
    assert claim.model_dump()["source_ids"] == [2, 3]


def test_verification_validates_verdict():
    v = Verification(claim_id="c1", verdict="supported", confidence=0.9, rationale="quote matches")
    assert v.verdict is Verdict.supported
    assert v.confidence == 0.9
    with pytest.raises(ValidationError):
        Verification(claim_id="c1", verdict="maybe")


def test_contradiction_references_two_claims():
    c = Contradiction(
        id="x1",
        entity="BrandX",
        attribute="pricing",
        claim_id_a="c1",
        claim_id_b="c2",
        note="$9 vs $12",
    )
    assert c.claim_id_a == "c1"
    assert c.claim_id_b == "c2"


def test_confidence_summary_counts_and_overall():
    summary = ConfidenceSummary(
        supported=4, partial=1, unsupported=1, contradicted=0, total=6, overall="high"
    )
    assert summary.supported == 4
    assert summary.total == 6
    assert summary.overall is ConfidenceLevel.high
    # A blank summary is valid (all zero).
    assert ConfidenceSummary().total == 0
