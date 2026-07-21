from __future__ import annotations

from app.core.verifier import confidence, verify, verify_claims
from app.models.schemas import Claim, ConfidenceLevel, RunConfig, Verdict, Verification
from app.providers.llm.mock import MockLLMProvider


def _claim(cid: str, quote: str, sources: list[int] | None = None) -> Claim:
    return Claim(id=cid, text=f"claim {cid}", quote=quote, source_ids=sources or [1])


async def test_verify_supported_when_quote_backs_the_claim():
    v = await verify(
        _claim("c1", "priced at $9"),
        source_text="BrandX is priced at $9 per month.",
        llm=MockLLMProvider(),
    )
    assert isinstance(v, Verification)
    assert v.claim_id == "c1"
    assert v.verdict is Verdict.supported
    assert v.confidence > 0.5


async def test_verify_unsupported_when_quote_absent_from_source():
    v = await verify(
        _claim("c2", "the moon is made of cheese"),
        source_text="BrandX is priced at $9 per month.",
        llm=MockLLMProvider(),
    )
    assert v.verdict is Verdict.unsupported


async def test_verify_claims_batches_and_judges_each():
    claims = [_claim("a", "alpha"), _claim("b", "not in the text")]
    vs = await verify_claims(claims, source_text="alpha beta gamma", llm=MockLLMProvider())
    by_id = {v.claim_id: v for v in vs}
    assert set(by_id) == {"a", "b"}
    assert by_id["a"].verdict is Verdict.supported
    assert by_id["b"].verdict is Verdict.unsupported


def test_confidence_is_pure_high_medium_low():
    v_sup = Verification(claim_id="c", verdict="supported", confidence=0.9)
    # supported + corroborated by ≥2 sources → high
    assert confidence(_claim("c", "q", [1, 2]), [v_sup]) is ConfidenceLevel.high
    # supported by a single source → medium
    assert confidence(_claim("c", "q", [1]), [v_sup]) is ConfidenceLevel.medium
    # unsupported → low; contradicted → low
    assert (
        confidence(_claim("c", "q", [1]), [Verification(claim_id="c", verdict="unsupported")])
        is ConfidenceLevel.low
    )
    assert (
        confidence(_claim("c", "q", [1, 2]), [Verification(claim_id="c", verdict="contradicted")])
        is ConfidenceLevel.low
    )
    # no verification for the claim → low
    assert confidence(_claim("c", "q", [1]), []) is ConfidenceLevel.low


def test_runconfig_has_verifier_settings():
    cfg = RunConfig()
    # Present with an "inherit the main LLM" default (empty string).
    assert cfg.verifier_provider == ""
    assert cfg.verifier_model == ""
