"""Claim verification + confidence.

``verify_claims`` sends every claim from one source to a (separate, adversarial)
verifier LLM in a single call and returns a :class:`Verification` per claim.
``confidence`` is a pure function turning a claim + its verifications into a
categorical high/medium/low level (corroboration comes from the claim's sources).
"""

from __future__ import annotations

from app.models.schemas import Claim, ConfidenceLevel, Verdict, Verification
from app.providers.json_utils import JSONParseError, extract_json
from app.providers.llm.base import LLMProvider
from app.prompts.verifier import verify_messages

_VALID_VERDICTS = {v.value for v in Verdict}


async def verify_claims(
    claims: list[Claim],
    source_text: str,
    llm: LLMProvider,
    *,
    verifier_model: str | None = None,
) -> list[Verification]:
    """Verify every claim against ``source_text`` in one batched call."""
    if not claims:
        return []
    raw = await llm.complete(verify_messages(claims, source_text), tag="verify", json=True)
    try:
        data = extract_json(raw)
    except JSONParseError:
        data = {}
    by_id: dict[str, Verification] = {}
    for item in data.get("verifications", []) or []:
        if not isinstance(item, dict):
            continue
        verdict = str(item.get("verdict", "")).lower()
        if verdict not in _VALID_VERDICTS:
            continue
        claim_id = str(item.get("claim_id", ""))
        by_id[claim_id] = Verification(
            claim_id=claim_id,
            verdict=Verdict(verdict),
            confidence=float(item.get("confidence") or 0.0),
            rationale=str(item.get("rationale", "")),
            verifier_model=verifier_model,
        )
    # A claim the verifier ignored is treated as unsupported (fail closed).
    out: list[Verification] = []
    for claim in claims:
        out.append(
            by_id.get(
                claim.id,
                Verification(
                    claim_id=claim.id,
                    verdict=Verdict.unsupported,
                    confidence=0.0,
                    rationale="verifier returned no judgement",
                    verifier_model=verifier_model,
                ),
            )
        )
    return out


async def verify(
    claim: Claim,
    source_text: str,
    llm: LLMProvider,
    *,
    verifier_model: str | None = None,
) -> Verification:
    """Verify a single claim (convenience wrapper over :func:`verify_claims`)."""
    results = await verify_claims([claim], source_text, llm, verifier_model=verifier_model)
    return results[0]


def confidence(claim: Claim, verifications: list[Verification]) -> ConfidenceLevel:
    """Pure high/medium/low confidence for a claim given its verifications.

    supported + corroborated by ≥2 sources → high; supported by one → medium;
    partial mirrors that one level lower; unsupported/contradicted/unknown → low.
    """
    verdict = next(
        (v.verdict for v in verifications if v.claim_id == claim.id),
        None,
    )
    if verdict in (None, Verdict.unsupported, Verdict.contradicted):
        return ConfidenceLevel.low
    corroborated = len(claim.source_ids) >= 2
    if verdict is Verdict.supported:
        return ConfidenceLevel.high if corroborated else ConfidenceLevel.medium
    # partial
    return ConfidenceLevel.medium if corroborated else ConfidenceLevel.low
