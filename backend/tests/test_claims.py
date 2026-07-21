from __future__ import annotations

import json
import re

from app.core.claims import extract_claims
from app.models.schemas import Claim, PageContent
from app.providers.llm.mock import MockLLMProvider


class _FixedLLM:
    """A stub LLM returning canned JSON — for testing extraction independent of
    the deterministic mock (which always grounds its quotes)."""

    def __init__(self, payload: str) -> None:
        self._payload = payload

    async def complete(self, messages, **kwargs) -> str:
        return self._payload

    def stream(self, messages, **kwargs):  # pragma: no cover - unused here
        raise NotImplementedError

_PAGE = PageContent(
    url="https://example.com/brandx",
    title="BrandX",
    text="BrandX is priced at $9 per month and targets Gen Z shoppers in urban areas.",
    ok=True,
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


async def test_extract_claims_are_grounded_in_the_page():
    claims = await extract_claims(
        llm=MockLLMProvider(),
        page=_PAGE,
        goal="How is BrandX priced?",
        source_id=1,
        section_id="s1",
    )
    assert claims, "expected at least one claim"
    for c in claims:
        assert isinstance(c, Claim)
        assert c.source_ids == [1]  # every claim cites its source
        assert c.section_id == "s1"
        assert c.text
        assert c.quote  # a verbatim span…
        assert _norm(c.quote) in _norm(_PAGE.text)  # …actually copied from the page


async def test_extract_claims_drops_ungrounded_quotes():
    # A claim whose quote is not a verbatim span of the page is dropped —
    # grounding is enforced, not trusted.
    page = PageContent(url="https://example.com/p", title="P", text="Real page content.", ok=True)
    llm = _FixedLLM(
        json.dumps(
            {
                "claims": [
                    {"text": "grounded", "quote": "Real page content"},
                    {"text": "fabricated", "quote": "this text is nowhere on the page"},
                ]
            }
        )
    )
    claims = await extract_claims(llm=llm, page=page, goal="g", source_id=2)
    assert [c.text for c in claims] == ["grounded"]  # only the grounded claim survives


async def test_extract_claims_skips_failed_pages():
    bad = PageContent(url="https://example.com/404", ok=False, error="not found")
    assert await extract_claims(llm=MockLLMProvider(), page=bad, goal="g", source_id=3) == []


async def test_extract_claims_tags_entity_when_entity_mode():
    schema = [
        {"key": "pricing", "label": "Pricing", "type": "text"},
        {"key": "target_segment", "label": "Target segment", "type": "text"},
    ]
    claims = await extract_claims(
        llm=MockLLMProvider(),
        page=_PAGE,
        goal="pricing",
        source_id=1,
        section_id="s1",
        entity_schema=schema,
    )
    assert claims
    assert any(c.entity for c in claims)  # entity-mode tags the entity
    assert any(c.attribute in {"pricing", "target_segment"} for c in claims)
