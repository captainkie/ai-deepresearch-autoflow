"""Planner: LLM query -> validated :class:`Plan` (brief + sections)."""

from __future__ import annotations

from pydantic import ValidationError

from app.models.schemas import Plan, RunConfig
from app.providers.json_utils import JSONParseError, extract_json
from app.providers.llm.base import LLMProvider
from app.prompts.planner import build_planner_messages
from app.prompts.templates import get_template


class Planner:
    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def plan(self, query: str, config: RunConfig) -> Plan:
        template = get_template(config.template)
        messages = build_planner_messages(query, config, template)

        raw = await self._llm.complete(messages, tag="plan", json=True)
        plan = self._parse(raw)
        if plan is None:
            # One repair retry with an explicit "valid JSON only" nudge.
            repair = [
                *messages,
                {
                    "role": "user",
                    "content": "Output valid JSON only, matching the required shape.",
                },
            ]
            raw = await self._llm.complete(repair, tag="plan", json=True)
            plan = self._parse(raw)
        if plan is None:
            raise ValueError("planner failed to produce a valid plan")

        return self._finalize(plan, config)

    @staticmethod
    def _parse(raw: str) -> Plan | None:
        try:
            data = extract_json(raw)
        except JSONParseError:
            return None
        sections = data.get("sections")
        if isinstance(sections, list):
            for i, section in enumerate(sections, start=1):
                if isinstance(section, dict) and not section.get("id"):
                    section["id"] = f"s{i}"
        try:
            return Plan.model_validate(data)
        except ValidationError:
            return None

    @staticmethod
    def _finalize(plan: Plan, config: RunConfig) -> Plan:
        sections = plan.sections[: config.max_sections]
        seen: set[str] = set()
        fixed = []
        for i, section in enumerate(sections, start=1):
            sid = section.id if section.id and section.id not in seen else f"s{i}"
            seen.add(sid)
            fixed.append(section.model_copy(update={"id": sid}))
        if not fixed:
            # A degenerate plan (no sections) must fail loudly, not silently
            # produce an empty report.
            raise ValueError("planner produced a plan with no sections")
        return plan.model_copy(update={"sections": fixed})
