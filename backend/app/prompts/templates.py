"""Research templates + i18n language directive.

Each :class:`Template` carries the API-contract fields (id/name/description/
audience) plus a ``report_outline`` used by the planner and synthesizer prompts.

Engine v2 (M3.5b) adds structure: an ``entity_mode`` template declares an
``entity_schema`` (the attributes to compare across entities, e.g. competitor
brands). The synthesizer pivots the run's *verified* claims — tagged
``(entity, attribute)`` — into a cited, confidence-marked comparison table.
Non-entity templates keep the plain narrative path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.models.schemas import Language

FieldType = Literal["text", "list"]


@dataclass(frozen=True)
class EntityField:
    """One comparable attribute in an entity-mode template.

    ``key`` matches the ``attribute`` tag the claim extractor assigns; ``label``
    is the human column header; ``type`` hints rendering (a single value vs a
    list of values).
    """

    key: str
    label: str
    type: FieldType = "text"


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    description: str
    audience: str
    report_outline: str
    # Engine v2 (M3.5b), all optional so non-entity templates stay unchanged.
    entity_mode: bool = False
    entity_schema: tuple[EntityField, ...] = ()
    report_sections: tuple[str, ...] = ()
    verification_level: str = "light"


# Projection order the synthesizer renders for an entity-mode report.
_ENTITY_REPORT_SECTIONS: tuple[str, ...] = (
    "Executive Summary",
    "Comparison",
    "Per-Entity Detail",
    "Contradictions",
    "Unverified",
    "Next Actions",
    "Sources",
)


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
        name="Competitor Teardown",
        description="Side-by-side teardown of competitor brands: positioning, products, pricing, channels.",
        audience="marketing team",
        report_outline=(
            "1. Executive Summary\n"
            "2. Competitor Comparison\n"
            "3. Per-Competitor Detail\n"
            "4. Strengths, Weaknesses & Perception\n"
            "5. Opportunities & Recommendations\n"
        ),
        entity_mode=True,
        entity_schema=(
            EntityField("positioning", "Positioning", "text"),
            EntityField("target_audience", "Target Audience", "text"),
            EntityField("products", "Products", "list"),
            EntityField("pricing", "Pricing", "text"),
            EntityField("channels", "Channels", "list"),
            EntityField("differentiator", "Differentiator", "text"),
        ),
        report_sections=_ENTITY_REPORT_SECTIONS,
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
        entity_mode=True,
        entity_schema=(
            EntityField("segment", "Segment", "text"),
            EntityField("offering", "Offering", "text"),
            EntityField("market_share", "Market Share", "text"),
            EntityField("differentiator", "Differentiator", "text"),
        ),
        report_sections=_ENTITY_REPORT_SECTIONS,
    ),
    "swot": Template(
        id="swot",
        name="SWOT Analysis",
        description="Structured strengths, weaknesses, opportunities, and threats for one subject.",
        audience="marketing and strategy team",
        report_outline=(
            "1. Executive Summary\n"
            "2. Strengths\n"
            "3. Weaknesses\n"
            "4. Opportunities\n"
            "5. Threats\n"
            "6. Strategic Implications\n"
        ),
    ),
    "pricing_analysis": Template(
        id="pricing_analysis",
        name="Pricing Analysis",
        description="Compare pricing plans across products/competitors: tiers, price, billing, features.",
        audience="marketing and product team",
        report_outline=(
            "1. Executive Summary\n"
            "2. Pricing Comparison\n"
            "3. Per-Plan Detail\n"
            "4. Value & Positioning\n"
            "5. Recommendations\n"
        ),
        entity_mode=True,
        entity_schema=(
            EntityField("plan", "Plan", "text"),
            EntityField("price", "Price", "text"),
            EntityField("billing", "Billing", "text"),
            EntityField("key_features", "Key Features", "list"),
        ),
        report_sections=_ENTITY_REPORT_SECTIONS,
    ),
}


def get_template(template_id: str) -> Template:
    """Return the named template, falling back to ``deep_research``."""
    return TEMPLATES.get(template_id, TEMPLATES["deep_research"])


def language_directive(lang: Language) -> str:
    if lang == Language.th:
        return "Write the report in Thai."
    return "Write the report in English."
