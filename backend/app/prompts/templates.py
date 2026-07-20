"""Research templates + i18n language directive.

Each :class:`Template` carries the API-contract fields (id/name/description/
audience) plus a ``report_outline`` used by the planner and synthesizer prompts.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import Language


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    description: str
    audience: str
    report_outline: str


TEMPLATES: dict[str, Template] = {
    "deep_research": Template(
        id="deep_research",
        name="Deep Research",
        description="A thorough, well-cited investigation of any topic.",
        audience="general professional audience",
        report_outline=(
            "1. Executive Summary\n"
            "2. Background & Context\n"
            "3. Key Findings (one subsection per research section)\n"
            "4. Analysis & Implications\n"
            "5. Conclusion\n"
        ),
    ),
    "competitor_brand": Template(
        id="competitor_brand",
        name="Competitor Brand Analysis",
        description="Deep-dive on a competitor brand: positioning, products, and perception.",
        audience="marketing team",
        report_outline=(
            "1. Executive Summary\n"
            "2. Brand Overview & Positioning\n"
            "3. Products & Pricing\n"
            "4. Marketing & Channels\n"
            "5. Strengths, Weaknesses & Market Perception\n"
            "6. Opportunities & Recommendations\n"
        ),
    ),
    "market_landscape": Template(
        id="market_landscape",
        name="Market Landscape",
        description="Survey of a market: size, segments, key players, and trends.",
        audience="marketing and strategy team",
        report_outline=(
            "1. Executive Summary\n"
            "2. Market Size & Segments\n"
            "3. Key Players\n"
            "4. Trends & Drivers\n"
            "5. Risks & Outlook\n"
            "6. Conclusion\n"
        ),
    ),
}


def get_template(template_id: str) -> Template:
    """Return the named template, falling back to ``deep_research``."""
    return TEMPLATES.get(template_id, TEMPLATES["deep_research"])


def language_directive(lang: Language) -> str:
    if lang == Language.th:
        return "Write the report in Thai."
    return "Write the report in English."
