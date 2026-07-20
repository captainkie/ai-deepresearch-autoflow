"""Deterministic mock LLM provider.

Switches on ``tag`` to return canned, fully deterministic responses so the whole
pipeline is unit- and E2E-testable without API keys. No randomness, no network,
no time-dependent content. Prompt builders may embed ``QUERY:`` / ``OBJECTIVE:``
/ ``GOAL:`` marker lines, which the mock reads to tailor its output.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

_STREAM_CHUNK = 40


def _last_user(messages: list[dict]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return str(messages[-1].get("content", "")) if messages else ""


def _marker(messages: list[dict], name: str) -> str | None:
    prefix = f"{name}:"
    for message in messages:
        for line in str(message.get("content", "")).splitlines():
            stripped = line.strip()
            if stripped.startswith(prefix):
                return stripped[len(prefix) :].strip()
    return None


class MockLLMProvider:
    def __init__(self, model: str = "mock-1") -> None:
        self.model = model

    async def complete(
        self,
        messages: list[dict],
        *,
        tag: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        json: bool = False,
    ) -> str:
        return self._render(tag, messages)

    async def stream(
        self,
        messages: list[dict],
        *,
        tag: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        text = self._render(tag, messages)
        for i in range(0, len(text), _STREAM_CHUNK):
            yield text[i : i + _STREAM_CHUNK]

    def _render(self, tag: str | None, messages: list[dict]) -> str:
        if tag == "plan":
            return self._plan(messages)
        if tag == "summarize":
            return "Summary: " + _last_user(messages)[:160]
        if tag == "reflect":
            return json.dumps({"need_more": False, "queries": []})
        if tag == "compress":
            goal = _marker(messages, "GOAL") or "Section findings"
            return f"### {goal}\n- Key point drawn from the sources. [1]\n- Supporting detail. [2]"
        if tag == "report":
            return self._report(messages)
        return "OK: " + _last_user(messages)[:80]

    def _plan(self, messages: list[dict]) -> str:
        query = _marker(messages, "QUERY") or (_last_user(messages)[:120] or "the topic")
        plan = {
            "brief": {
                "objective": query,
                "audience": "marketing team",
                "key_questions": [
                    f"What is notable about {query}?",
                    f"How does {query} compare to peers?",
                ],
            },
            "sections": [
                {
                    "id": "s1",
                    "title": f"Overview of {query}",
                    "goal": f"Establish background and context on {query}",
                    "queries": [f"{query} overview", f"{query} background"],
                },
                {
                    "id": "s2",
                    "title": f"Analysis of {query}",
                    "goal": f"Analyze key aspects and positioning of {query}",
                    "queries": [f"{query} analysis", f"{query} comparison"],
                },
            ],
        }
        return json.dumps(plan)

    def _report(self, messages: list[dict]) -> str:
        title = (
            _marker(messages, "OBJECTIVE")
            or _marker(messages, "QUERY")
            or "Deep Research Report"
        )
        return (
            f"# {title}\n\n"
            "## Executive Summary\n"
            f"This report analyzes {title} using the gathered sources. [1]\n\n"
            "## Key Findings\n"
            "- Finding one, supported by evidence from the research. [1]\n"
            "- Finding two, with additional context and comparison. [2]\n\n"
            "## Conclusion\n"
            "The analysis surfaces clear, actionable insights for the reader.\n\n"
            "## Sources\n"
        )
