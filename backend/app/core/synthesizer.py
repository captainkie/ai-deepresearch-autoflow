"""Synthesizer: stream the final Markdown report and guarantee a Sources list."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable

from app.models.schemas import EventType, PlanSection, ResearchBrief, RunConfig, Source
from app.providers.llm.base import LLMProvider
from app.prompts.synthesizer import build_report_messages

EmitFn = Callable[[EventType, dict], Awaitable[object]]

_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)

# Localized "Sources" heading so a non-English report ends with a heading in its
# own language — and so the writer's own sources heading is recognized and
# de-duplicated instead of leaving two side by side.
_SOURCES_HEADINGS = {"en": "Sources", "th": "แหล่งอ้างอิง"}


async def synthesize(
    brief: ResearchBrief,
    sections: list[PlanSection],
    sources: list[Source],
    llm: LLMProvider,
    emit: EmitFn,
    config: RunConfig | None = None,
) -> tuple[str, str]:
    """Stream the report (emitting ``report_delta``) and return ``(markdown, title)``."""
    config = config or RunConfig()
    messages = build_report_messages(brief, sections, sources, config)

    parts: list[str] = []
    async for delta in llm.stream(messages, tag="report"):
        parts.append(delta)
        await emit(EventType.report_delta, {"text": delta})

    lang = getattr(config.language, "value", config.language) or "en"
    heading = _SOURCES_HEADINGS.get(str(lang), "Sources")
    markdown = ensure_sources_section("".join(parts), sources, heading)
    title = extract_title(markdown) or brief.objective
    return markdown, title


def extract_title(markdown: str) -> str:
    match = _TITLE_RE.search(markdown)
    return match.group(1).strip() if match else ""


def ensure_sources_section(markdown: str, sources: list[Source], heading: str = "Sources") -> str:
    """Ensure exactly one trailing sources list containing every source id.

    ``heading`` is the localized section title. The writer's own sources heading
    (the localized one or a literal English "Sources") is stripped so the report
    never shows two source sections.
    """
    lines = [f"## {heading}", ""]
    if sources:
        lines.extend(f"[{s.id}] {s.title} — {s.url}" for s in sources)
    else:
        lines.append("(no sources)")
    block = "\n".join(lines)

    variants = "|".join(sorted({re.escape(heading), "Sources"}))
    heading_re = re.compile(rf"^##\s+(?:{variants})\s*$", re.MULTILINE | re.IGNORECASE)
    matches = list(heading_re.finditer(markdown))
    if matches:
        head = markdown[: matches[-1].start()].rstrip()
        return f"{head}\n\n{block}\n"
    return f"{markdown.rstrip()}\n\n{block}\n"
