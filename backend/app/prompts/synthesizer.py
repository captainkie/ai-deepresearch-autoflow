"""Synthesizer prompt: brief + sections + sources -> final Markdown report."""

from __future__ import annotations

from app.models.schemas import Claim, Contradiction, PlanSection, ResearchBrief, RunConfig, Source
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


def build_exec_summary_messages(
    brief: ResearchBrief,
    verified_claims: list[Claim],
    contradictions: list[Contradiction],
    config: RunConfig,
) -> list[dict]:
    """Prompt for the entity report's executive summary.

    Fed ONLY the verified findings so the summary can't introduce unverified
    material; the deterministic comparison table + appendix are assembled around it.
    """
    template = get_template(config.template)
    system = (
        "You are an expert research writer. Write ONLY a concise executive summary "
        "(2-4 sentences) of the verified findings below. Do not introduce any fact "
        "that is not in the findings. Cite sources inline as '[n]'. "
        f"{language_directive(config.language)}"
    )
    findings = (
        "\n".join(f"- {c.text} " + "".join(f"[{s}]" for s in c.source_ids) for c in verified_claims)
        or "(no verified findings)"
    )
    contra = (
        f"\nNOTE: {len(contradictions)} unresolved contradiction(s) across sources."
        if contradictions
        else ""
    )
    user = (
        f"OBJECTIVE: {brief.objective}\n"
        f"AUDIENCE: {brief.audience or template.audience}\n"
        f"VERIFIED FINDINGS:\n{findings}{contra}\n"
        "Write the executive summary now."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
