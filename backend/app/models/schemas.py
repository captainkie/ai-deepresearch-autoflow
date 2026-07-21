"""Core data models and enums — the single source of truth for data shapes.

Mirrors ``docs/API_CONTRACT.md``. Everything else (engine, providers, CLI)
imports its vocabulary from here.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Language(str, Enum):
    th = "th"
    en = "en"


class RunStatus(str, Enum):
    queued = "queued"
    planning = "planning"
    awaiting_plan = "awaiting_plan"
    researching = "researching"
    writing = "writing"
    done = "done"
    error = "error"
    cancelled = "cancelled"


class EventType(str, Enum):
    status = "status"
    plan = "plan"
    awaiting_plan = "awaiting_plan"
    section_start = "section_start"
    search = "search"
    source = "source"
    note = "note"
    section_done = "section_done"
    report_delta = "report_delta"
    report = "report"
    error = "error"
    done = "done"
    # Engine v2 (M3.5): claim-grounded verification.
    claim = "claim"
    verification = "verification"
    contradiction = "contradiction"


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str = ""
    score: float | None = None


class PageContent(BaseModel):
    url: str
    title: str = ""
    text: str = ""
    ok: bool = True
    error: str | None = None


class Source(BaseModel):
    id: int
    title: str
    url: str
    snippet: str = ""
    section_id: str | None = None


class PlanSection(BaseModel):
    id: str
    title: str
    goal: str
    queries: list[str] = Field(default_factory=list)


class ResearchBrief(BaseModel):
    objective: str
    audience: str = ""
    key_questions: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    brief: ResearchBrief
    sections: list[PlanSection]


class Event(BaseModel):
    seq: int
    run_id: str
    ts: int
    type: EventType
    data: dict


# --- Engine v2 (M3.5): claims, verification, contradictions --------------- #


class Verdict(str, Enum):
    supported = "supported"
    partial = "partial"
    unsupported = "unsupported"
    contradicted = "contradicted"


class ConfidenceLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class Claim(BaseModel):
    """An atomic, source-grounded assertion — the unit the report is built from.

    Every claim MUST carry ≥1 ``source_ids`` and a ``quote`` copied verbatim from
    the page, so verification is a grounding check rather than a re-derivation.
    ``entity``/``attribute`` are set in entity-mode templates so the verified set
    can be pivoted into a comparison table.
    """

    id: str
    text: str
    source_ids: list[int] = Field(default_factory=list)
    quote: str = ""
    section_id: str | None = None
    entity: str | None = None
    attribute: str | None = None
    stance: str | None = None


class Verification(BaseModel):
    """A separate (adversarial) verifier's judgement of one claim vs its source."""

    claim_id: str
    verdict: Verdict
    confidence: float = 0.0
    rationale: str = ""
    verifier_model: str | None = None


class Contradiction(BaseModel):
    """Two supported claims on the same ``(entity, attribute)`` that disagree."""

    id: str
    claim_id_a: str
    claim_id_b: str
    entity: str | None = None
    attribute: str | None = None
    note: str = ""


class ConfidenceSummary(BaseModel):
    """Aggregate verification outcome for a run (attached to ``report``/``done``)."""

    supported: int = 0
    partial: int = 0
    unsupported: int = 0
    contradicted: int = 0
    total: int = 0
    overall: ConfidenceLevel | None = None


class RunConfig(BaseModel):
    llm_provider: str = "mock"
    llm_model: str = "mock-1"
    search_provider: str = "mock"
    crawl_provider: str = "mock"
    language: Language = Language.en
    template: str = "deep_research"
    require_plan_approval: bool = False
    # Engine v2 verifier (empty ⇒ reuse the main llm_provider/llm_model).
    verifier_provider: str = ""
    verifier_model: str = ""
    max_sections: int = 6
    max_iters_per_section: int = 2
    results_per_query: int = 6
    fetch_per_query: int = 3
    section_concurrency: int = 3
    fetch_concurrency: int = 6
    # Runaway-run guards (enforced by the API layer in M2).
    max_llm_calls: int = 60
    timeout_s: int = 900
