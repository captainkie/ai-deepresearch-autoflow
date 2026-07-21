from __future__ import annotations

from app.core.contradictions import detect_contradictions
from app.models.schemas import Claim, Verification
from app.providers.llm.mock import MockLLMProvider


def _claim(cid: str, text: str, *, entity="BrandX", attribute="pricing", source=1) -> Claim:
    return Claim(
        id=cid, text=text, quote=text, source_ids=[source], entity=entity, attribute=attribute
    )


def _supported(*ids: str) -> list[Verification]:
    return [Verification(claim_id=i, verdict="supported", confidence=0.9) for i in ids]


async def test_conflicting_supported_claims_yield_one_contradiction():
    a = _claim("a", "BrandX is priced at $9 per month", source=1)
    b = _claim("b", "BrandX is priced at $12 per month", source=2)
    cs = await detect_contradictions([a, b], _supported("a", "b"), MockLLMProvider())
    assert len(cs) == 1
    assert {cs[0].claim_id_a, cs[0].claim_id_b} == {"a", "b"}
    assert cs[0].entity == "BrandX"
    assert cs[0].attribute == "pricing"


async def test_agreeing_claims_yield_no_contradiction():
    a = _claim("a", "BrandX is priced at $9 per month", source=1)
    b = _claim("b", "BrandX is priced at $9 monthly", source=2)
    assert await detect_contradictions([a, b], _supported("a", "b"), MockLLMProvider()) == []


async def test_only_supported_claims_are_compared():
    a = _claim("a", "BrandX is priced at $9", source=1)
    b = _claim("b", "BrandX is priced at $12", source=2)
    # b is unsupported → the pair is never adjudicated.
    verifs = _supported("a") + [Verification(claim_id="b", verdict="unsupported")]
    assert await detect_contradictions([a, b], verifs, MockLLMProvider()) == []


async def test_claims_without_entity_attribute_are_skipped():
    a = _claim("a", "priced at $9", entity=None, attribute=None, source=1)
    b = _claim("b", "priced at $12", entity=None, attribute=None, source=2)
    assert await detect_contradictions([a, b], _supported("a", "b"), MockLLMProvider()) == []


async def test_contradictions_only_within_same_entity_attribute():
    a = _claim("a", "BrandX is priced at $9", entity="BrandX", attribute="pricing", source=1)
    b = _claim("b", "BrandY is priced at $12", entity="BrandY", attribute="pricing", source=2)
    # Different entities → not the same fact → no contradiction.
    assert await detect_contradictions([a, b], _supported("a", "b"), MockLLMProvider()) == []
