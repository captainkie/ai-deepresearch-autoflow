"""Request/response models for the HTTP API — mirrors ``docs/API_CONTRACT.md``.

Kept separate from ``models/schemas.py`` (the engine's vocabulary): these are
the wire shapes the Next.js frontend consumes.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    version: str


class AuthorOut(BaseModel):
    name: str
    handle: str
    role: str


class AckOut(BaseModel):
    name: str
    url: str
    license: str


class OrgOut(BaseModel):
    name: str
    url: str


class AboutResponse(BaseModel):
    app: str
    version: str
    license: str
    org: OrgOut
    authors: list[AuthorOut]
    acknowledgements: list[AckOut]


class LlmConfig(BaseModel):
    provider: str
    model: str
    available: list[str]


class SearchConfig(BaseModel):
    provider: str
    available: list[str]


class ConfigResponse(BaseModel):
    llm: LlmConfig
    search: SearchConfig
    require_plan_approval: bool
    verification_level: str = "light"


class ConfigUpdate(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    search_provider: str | None = None
    require_plan_approval: bool | None = None
    verification_level: str | None = None


class EntityFieldOut(BaseModel):
    key: str
    label: str
    type: str = "text"


class TemplateOut(BaseModel):
    id: str
    name: str
    description: str
    audience: str
    # Engine v2 (M3.5b): entity_mode templates carry a comparison schema.
    entity_mode: bool = False
    entity_schema: list[EntityFieldOut] = Field(default_factory=list)
    verification_level: str = "light"


class TemplatesResponse(BaseModel):
    templates: list[TemplateOut]


class RunConfigIn(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    search_provider: str | None = None


class CreateRun(BaseModel):
    query: str = Field(min_length=1)
    template: str | None = None
    language: str | None = None
    require_plan_approval: bool | None = None
    config: RunConfigIn | None = None


class CreateRunResponse(BaseModel):
    run_id: str


class RunSummary(BaseModel):
    run_id: str
    query: str
    template: str
    status: str
    created_at: str
    title: str | None = None


class RunsResponse(BaseModel):
    runs: list[RunSummary]
    has_more: bool = False


class PlanSectionIn(BaseModel):
    id: str
    title: str
    goal: str
    queries: list[str] = Field(default_factory=list)


class PlanSubmit(BaseModel):
    approve: bool | None = None
    sections: list[PlanSectionIn] | None = None


class PlanOut(BaseModel):
    brief: str
    sections: list[PlanSectionIn]


class SectionOut(BaseModel):
    id: str
    idx: int
    title: str | None = None
    goal: str | None = None
    queries: list[str] = Field(default_factory=list)
    summary: str | None = None
    status: str | None = None


class SourceOut(BaseModel):
    id: int
    title: str | None = None
    url: str | None = None
    snippet: str | None = None
    section_id: str | None = None


class RunProviders(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    search_provider: str | None = None
    crawl_provider: str | None = None


class ConfidenceSummaryOut(BaseModel):
    high: int = 0
    medium: int = 0
    low: int = 0
    contradictions: int = 0


class RunDetail(BaseModel):
    run_id: str
    query: str
    template: str
    language: str
    status: str
    title: str | None = None
    require_plan_approval: bool
    config: RunProviders
    report: str | None = None
    error: str | None = None
    created_at: str
    updated_at: str
    confidence_summary: ConfidenceSummaryOut | None = None
    plan: PlanOut | None = None
    sections: list[SectionOut] = Field(default_factory=list)
    sources: list[SourceOut] = Field(default_factory=list)


class OkResponse(BaseModel):
    ok: bool = True
