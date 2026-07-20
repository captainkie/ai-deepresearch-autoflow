"""Synthesizer prompt: brief + sections + sources -> final Markdown report."""

from __future__ import annotations

from app.models.schemas import PlanSection, ResearchBrief, RunConfig, Source
from app.prompts.templates import get_template, language_directive


def _format_sources(sources: list[Source]) -> str:
    if not sources:
        return "(no sources)"
    lines = []
    for source in sources:
        snippet = f" — {source.snippet}" if source.snippet else ""
        lines.append(f"[{source.id}] {source.title} — {source.url}{snippet}")
    return "\n".join(lines)


def _format_sections(sections: list[PlanSection]) -> str:
    return "\n".join(f"- {s.title}: {s.goal}" for s in sections)


def build_report_messages(
    brief: ResearchBrief,
    sections: list[PlanSection],
    sources: list[Source],
    config: RunConfig,
) -> list[dict]:
    template = get_template(config.template)
    system = (
        "You are an expert research writer. Produce a detailed, well-structured "
        "Markdown report:\n"
        "- Start with a single '# ' title.\n"
        "- Use '## ' headings following the report outline and research sections.\n"
        "- Support claims with inline citations '[n]' referencing the source ids.\n"
        "- End with a '## Sources' section listing every source as '[n] title — url'.\n"
        f"{language_directive(config.language)}"
    )
    key_questions = "\n".join(f"- {q}" for q in brief.key_questions) or "(none)"
    user = (
        f"OBJECTIVE: {brief.objective}\n"
        f"AUDIENCE: {brief.audience or template.audience}\n"
        f"KEY QUESTIONS:\n{key_questions}\n"
        f"REPORT OUTLINE:\n{template.report_outline}\n"
        f"RESEARCH SECTIONS:\n{_format_sections(sections)}\n"
        f"SOURCES:\n{_format_sources(sources)}\n"
        "Write the full report now, ending with the '## Sources' list."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
