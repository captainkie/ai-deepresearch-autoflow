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


class RunConfig(BaseModel):
    llm_provider: str = "mock"
    llm_model: str = "mock-1"
    search_provider: str = "mock"
    crawl_provider: str = "mock"
    language: Language = Language.en
    template: str = "deep_research"
    require_plan_approval: bool = False
    max_sections: int = 6
    max_iters_per_section: int = 2
    results_per_query: int = 6
    fetch_per_query: int = 3
    section_concurrency: int = 3
    fetch_concurrency: int = 6
