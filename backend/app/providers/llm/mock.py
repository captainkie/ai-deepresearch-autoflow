"""Deterministic mock LLM provider.

Switches on ``tag`` to return canned, fully deterministic responses so the whole
pipeline is unit- and E2E-testable without API keys. No randomness, no network,
no time-dependent content. Prompt builders may embed ``QUERY:`` / ``OBJECTIVE:``
/ ``GOAL:`` marker lines, which the mock reads to tailor its output.
"""

from __future__ import annotations

import json
import re
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


def _wants_thai(messages: list[dict]) -> bool:
    """Detect the Thai ``language_directive`` the planner/synthesizer inject.

    Real providers honour the directive naturally; the mock has to look for it so
    the offline demo actually renders Thai when the user picks ไทย.
    """
    return any("in Thai" in str(m.get("content", "")) for m in messages)


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
        if tag == "claims":
            return self._claims(messages)
        if tag == "verify":
            return self._verify(messages)
        if tag == "contradiction":
            return self._contradiction(messages)
        if tag == "compress":
            goal = _marker(messages, "GOAL") or "Section findings"
            return f"### {goal}\n- Key point drawn from the sources. [1]\n- Supporting detail. [2]"
        if tag == "report":
            return self._report(messages)
        if tag == "exec_summary":
            return self._exec_summary(messages)
        return "OK: " + _last_user(messages)[:80]

    def _exec_summary(self, messages: list[dict]) -> str:
        """Short, deterministic executive summary for the entity report."""
        subject = _marker(messages, "OBJECTIVE") or "the subject"
        if _wants_thai(messages):
            return f"บทวิเคราะห์ที่ตรวจสอบแล้วของ {subject} ชี้ให้เห็นความแตกต่างสำคัญที่นำไปใช้ได้ [1]"
        return f"This verified analysis of {subject} surfaces the key differences that matter. [1]"

    def _claims(self, messages: list[dict]) -> str:
        """Emit one deterministic claim whose quote is a real span of the page."""
        content = _last_user(messages)
        page_text = ""
        if "PAGE CONTENT:\n" in content:
            page_text = content.split("PAGE CONTENT:\n", 1)[1].split("\nReturn only", 1)[0].strip()
        quote = page_text[:60].strip()  # a verbatim prefix → passes the grounding check
        if not quote:
            return json.dumps({"claims": []})
        entity = attribute = None
        if "ENTITY_MODE: true" in content:
            entity = _marker(messages, "PAGE TITLE") or "Entity"
            attrs = _marker(messages, "ATTRIBUTES")
            attribute = attrs.split(",")[0].strip() if attrs else None
        claim = {
            "text": "A grounded finding relevant to the goal.",
            "quote": quote,
            "entity": entity,
            "attribute": attribute,
            "stance": "neutral",
        }
        return json.dumps({"claims": [claim]})

    def _verify(self, messages: list[dict]) -> str:
        """Grounding-only verifier: a claim is 'supported' iff its quote appears
        in the source text, else 'unsupported' — deterministic and offline."""
        content = _last_user(messages)
        source_text = ""
        if "SOURCE TEXT:\n" in content:
            source_text = content.split("SOURCE TEXT:\n", 1)[1].split("\n\nCLAIMS", 1)[0]
        source_norm = " ".join(source_text.split()).lower()
        verifications = []
        if "CLAIMS" in content:
            block = content.split("CLAIMS", 1)[1]
            for line in block.splitlines():
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                claim_id, quote = parts[0].strip(), parts[1]
                supported = " ".join(quote.split()).lower() in source_norm
                verifications.append(
                    {
                        "claim_id": claim_id,
                        "verdict": "supported" if supported else "unsupported",
                        "confidence": 0.9 if supported else 0.2,
                        "rationale": ("quote found in source" if supported else "quote not found"),
                    }
                )
        return json.dumps({"verifications": verifications})

    def _contradiction(self, messages: list[dict]) -> str:
        """Two claims conflict (deterministically) iff they cite different numeric
        values (e.g. $9 vs $12) for the same attribute."""
        a = _marker(messages, "CLAIM_A") or ""
        b = _marker(messages, "CLAIM_B") or ""
        nums_a = set(re.findall(r"\d+", a))
        nums_b = set(re.findall(r"\d+", b))
        conflict = bool(nums_a and nums_b and nums_a != nums_b)
        note = f"{a.strip()} vs {b.strip()}" if conflict else ""
        return json.dumps({"conflict": conflict, "note": note})

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
            _marker(messages, "OBJECTIVE") or _marker(messages, "QUERY") or "Deep Research Report"
        )
        if _wants_thai(messages):
            return (
                f"# {title}\n\n"
                "## บทสรุปผู้บริหาร\n"
                f"รายงานนี้วิเคราะห์ {title} โดยอ้างอิงจากแหล่งข้อมูลที่รวบรวมมา [1]\n\n"
                "## ผลการค้นพบสำคัญ\n"
                "- ประเด็นแรก มีหลักฐานสนับสนุนจากการวิจัย [1]\n"
                "- ประเด็นที่สอง พร้อมบริบทและการเปรียบเทียบเพิ่มเติม [2]\n\n"
                "## บทสรุป\n"
                "การวิเคราะห์ชี้ให้เห็นข้อมูลเชิงลึกที่ชัดเจนและนำไปใช้ได้จริงสำหรับผู้อ่าน\n\n"
                "## แหล่งอ้างอิง\n"
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
