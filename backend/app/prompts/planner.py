"""Planner prompt: turn a query + template into a structured JSON plan."""

from __future__ import annotations

from app.models.schemas import RunConfig
from app.prompts.templates import Template, language_directive


def build_planner_messages(query: str, config: RunConfig, template: Template) -> list[dict]:
    system = (
        "You are a meticulous research planner. Produce a single JSON object and "
        "nothing else, with this shape:\n"
        '  "brief": { "objective": str, "audience": str, "key_questions": [str, ...] }\n'
        '  "sections": [ { "id": "s1", "title": str, "goal": str, '
        '"queries": [str, ...] }, ... ]\n'
        f"Create between 3 and {config.max_sections} sections. Each section needs a "
        "clear goal and 2-4 focused search queries. Follow the report outline."
    )
    user = (
        f"QUERY: {query}\n"
        f"TEMPLATE: {template.name} — {template.description}\n"
        f"AUDIENCE: {template.audience}\n"
        f"REPORT OUTLINE:\n{template.report_outline}\n"
        f"{language_directive(config.language)}\n"
        "Return only the JSON plan."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
