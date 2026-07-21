"""Synthesizer: turn the run into the final Markdown report.

Two paths:

* **Narrative** (non-entity templates) — stream an LLM-written report and
  guarantee a trailing Sources list. Unchanged since M2.
* **Entity projection** (``entity_mode`` templates, Engine v2/M3.5b) — the report
  is a *projection of verified claims*: an LLM executive summary (fed only the
  verified findings) followed by a deterministic, cited **comparison table**
  (rows = entities, cols = the template's ``entity_schema``), per-entity detail,
  contradictions, and an **Unverified appendix** that quarantines every claim the
  verifier did not support. The body therefore never contains an unverified claim.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable

from app.core.verifier import confidence
from app.models.schemas import (
    Claim,
    ConfidenceLevel,
    Contradiction,
    EventType,
    PlanSection,
    ResearchBrief,
    RunConfig,
    Source,
    Verdict,
    Verification,
)
from app.providers.llm.base import LLMProvider
from app.prompts.synthesizer import build_exec_summary_messages, build_report_messages
from app.prompts.templates import EntityField, get_template

EmitFn = Callable[[EventType, dict], Awaitable[object]]

_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)

# Localized "Sources" heading so a non-English report ends with a heading in its
# own language — and so the writer's own sources heading is recognized and
# de-duplicated instead of leaving two side by side.
_SOURCES_HEADINGS = {"en": "Sources", "th": "แหล่งอ้างอิง"}

_CONF_MARKER = {
    ConfidenceLevel.high: "🟢",
    ConfidenceLevel.medium: "🟡",
    ConfidenceLevel.low: "🔴",
}

# Localized section headings for the entity-projection report.
_ENTITY_HEADINGS = {
    "en": {
        "summary": "Executive Summary",
        "comparison": "Comparison",
        "detail": "Per-Entity Detail",
        "contradictions": "Contradictions",
        "unverified": "Unverified — needs checking",
        "next": "Next Actions",
    },
    "th": {
        "summary": "บทสรุปผู้บริหาร",
        "comparison": "ตารางเปรียบเทียบ",
        "detail": "รายละเอียดรายหน่วย",
        "contradictions": "ข้อขัดแย้งที่พบ",
        "unverified": "ยังไม่ยืนยัน — ต้องตรวจสอบ",
        "next": "ขั้นตอนถัดไป",
    },
}


async def synthesize(
    brief: ResearchBrief,
    sections: list[PlanSection],
    sources: list[Source],
    llm: LLMProvider,
    emit: EmitFn,
    config: RunConfig | None = None,
    *,
    claims: list[Claim] | None = None,
    verifications: list[Verification] | None = None,
    contradictions: list[Contradiction] | None = None,
) -> tuple[str, str]:
    """Stream the report (emitting ``report_delta``) and return ``(markdown, title)``.

    When the template is ``entity_mode`` and the run produced claims, the report
    is the entity projection (comparison table + verified-only body); otherwise
    the legacy narrative path runs.
    """
    config = config or RunConfig()
    template = get_template(config.template)
    claims = claims or []
    verifications = verifications or []
    contradictions = contradictions or []

    lang = str(getattr(config.language, "value", config.language) or "en")
    heading = _SOURCES_HEADINGS.get(lang, "Sources")

    if template.entity_mode and claims:
        return await _synthesize_entity(
            brief,
            template,
            sources,
            llm,
            emit,
            config,
            claims,
            verifications,
            contradictions,
            lang,
            heading,
        )

    messages = build_report_messages(brief, sections, sources, config)
    parts: list[str] = []
    async for delta in llm.stream(messages, tag="report"):
        parts.append(delta)
        await emit(EventType.report_delta, {"text": delta})
    markdown = ensure_sources_section("".join(parts), sources, heading)
    title = extract_title(markdown) or brief.objective
    return markdown, title


async def _synthesize_entity(
    brief: ResearchBrief,
    template,
    sources: list[Source],
    llm: LLMProvider,
    emit: EmitFn,
    config: RunConfig,
    claims: list[Claim],
    verifications: list[Verification],
    contradictions: list[Contradiction],
    lang: str,
    heading: str,
) -> tuple[str, str]:
    supported = [c for c in claims if _is_supported(c.id, verifications)]
    exec_summary = await llm.complete(
        build_exec_summary_messages(brief, supported, contradictions, config),
        tag="exec_summary",
    )
    body = _render_entity_report(
        brief=brief,
        template=template,
        claims=claims,
        verifications=verifications,
        contradictions=contradictions,
        exec_summary=exec_summary,
        lang=lang,
    )
    markdown = ensure_sources_section(body, sources, heading)
    # Stream the assembled report so the UI renders it progressively.
    for i in range(0, len(markdown), 200):
        await emit(EventType.report_delta, {"text": markdown[i : i + 200]})
    title = extract_title(markdown) or brief.objective
    return markdown, title


def _is_supported(claim_id: str, verifications: list[Verification]) -> bool:
    for v in verifications:
        if v.claim_id == claim_id:
            return v.verdict is Verdict.supported
    return False


def _cell(text: str) -> str:
    """Collapse whitespace and escape pipes so a claim can't break the table."""
    return " ".join(text.split()).replace("|", "\\|")


def build_comparison_table(
    entity_schema: list[EntityField],
    claims: list[Claim],
    verifications: list[Verification],
) -> str:
    """Pivot the *supported* claims into a Markdown comparison table.

    Rows are entities (first-seen order), columns are the ``entity_schema``
    attributes. Each filled cell carries the claim value, its ``[n]`` citations,
    and a confidence marker; an empty cell is ``—``. Unsupported claims are
    excluded entirely. Returns ``""`` when there is nothing to compare.
    """
    ver_by_id = {v.claim_id: v for v in verifications}
    supported = [
        c
        for c in claims
        if (v := ver_by_id.get(c.id)) is not None and v.verdict is Verdict.supported
    ]
    entities: list[str] = []
    for c in supported:
        if c.entity and c.entity not in entities:
            entities.append(c.entity)
    if not entities or not entity_schema:
        return ""

    headers = ["Entity"] + [f.label for f in entity_schema]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for entity in entities:
        row = [entity]
        for field in entity_schema:
            cells = [c for c in supported if c.entity == entity and c.attribute == field.key]
            if not cells:
                row.append("—")
                continue
            parts = []
            for c in cells:
                level = confidence(c, [ver_by_id[c.id]])
                cites = "".join(f"[{s}]" for s in c.source_ids)
                parts.append(f"{_cell(c.text)} {cites} {_CONF_MARKER[level]}".strip())
            row.append("; ".join(parts))
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def summarize_confidence(
    claims: list[Claim],
    verifications: list[Verification],
    contradictions: list[Contradiction],
) -> dict:
    """Aggregate per-claim confidence into the API-contract wire summary
    ``{high, medium, low, contradictions}``."""
    by_id: dict[str, list[Verification]] = {}
    for v in verifications:
        by_id.setdefault(v.claim_id, []).append(v)
    counts = {"high": 0, "medium": 0, "low": 0}
    for c in claims:
        counts[confidence(c, by_id.get(c.id, [])).value] += 1
    counts["contradictions"] = len(contradictions)
    return counts


def _render_entity_report(
    *,
    brief: ResearchBrief,
    template,
    claims: list[Claim],
    verifications: list[Verification],
    contradictions: list[Contradiction],
    exec_summary: str,
    lang: str,
) -> str:
    h = _ENTITY_HEADINGS.get(lang, _ENTITY_HEADINGS["en"])
    ver_by_id = {v.claim_id: v for v in verifications}
    supported_ids = {c.id for c in claims if _is_supported(c.id, verifications)}
    supported = [c for c in claims if c.id in supported_ids]
    unsupported = [c for c in claims if c.id not in supported_ids]

    out: list[str] = [f"# {brief.objective}", ""]
    out += [f"## {h['summary']}", exec_summary.strip(), ""]

    # Comparison table (the payoff).
    table = build_comparison_table(list(template.entity_schema), claims, verifications)
    out += [f"## {h['comparison']}", ""]
    if table:
        out += [table, "", "> 🟢 high · 🟡 medium confidence · citations in [n]", ""]
    else:
        out += ["(no verified comparisons yet)", ""]

    # Per-entity detail — supported claims grouped by entity.
    entities: list[str] = []
    for c in supported:
        if c.entity and c.entity not in entities:
            entities.append(c.entity)
    if entities:
        label_by_key = {f.key: f.label for f in template.entity_schema}
        out += [f"## {h['detail']}", ""]
        for entity in entities:
            out.append(f"### {entity}")
            for c in supported:
                if c.entity != entity:
                    continue
                label = label_by_key.get(c.attribute or "", c.attribute or "")
                cites = "".join(f"[{s}]" for s in c.source_ids)
                level = confidence(c, [ver_by_id[c.id]])
                prefix = f"**{label}**: " if label else ""
                out.append(f"- {prefix}{c.text} {cites} {_CONF_MARKER[level]}".rstrip())
            out.append("")

    # Contradictions — surfaced, never hidden.
    if contradictions:
        out += [f"## {h['contradictions']}", ""]
        for x in contradictions:
            tag = " / ".join(p for p in (x.entity, x.attribute) if p)
            head = f"{tag}: " if tag else ""
            note = f" — {x.note}" if x.note else ""
            out.append(f"- {head}claims {x.claim_id_a} vs {x.claim_id_b}{note}")
        out.append("")

    # Unverified appendix — everything the verifier did not support.
    if unsupported:
        out += [f"## {h['unverified']}", ""]
        for c in unsupported:
            v = ver_by_id.get(c.id)
            verdict = v.verdict.value if v else "unverified"
            cites = "".join(f"[{s}]" for s in c.source_ids)
            ent = f"{c.entity} — " if c.entity else ""
            out.append(f"- {ent}{c.text} {cites} — _{verdict}_".rstrip())
        out.append("")

    # Next actions.
    out += [f"## {h['next']}", ""]
    if lang == "th":
        out += [
            "- ตรวจสอบรายการใน “ยังไม่ยืนยัน” และที่ทำเครื่องหมาย 🔴 ก่อนนำไปใช้",
            "- เติมช่องว่าง (—) ในตารางด้วยการค้นเพิ่มแบบเจาะจง",
            "",
        ]
    else:
        out += [
            "- Verify the Unverified items (and any 🔴) before publishing.",
            "- Fill comparison gaps (—) with a targeted follow-up search.",
            "",
        ]
    return "\n".join(out).rstrip() + "\n"


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
