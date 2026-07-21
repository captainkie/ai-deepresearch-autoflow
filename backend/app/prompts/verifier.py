"""Verifier prompt: an adversarial check of claims against their source text.

Batches every claim from one source into a single call. The claim list is
tab-separated (claim_id, supporting quote, claim text) so it parses cleanly.
"""

from __future__ import annotations

from app.models.schemas import Claim

_SYSTEM = (
    "You are an adversarial fact-checker. For each claim, decide ONLY from the SOURCE "
    "TEXT whether it holds: 'supported' if the source explicitly backs it, 'partial' if "
    "it backs part of it, 'unsupported' if the source does not back it, 'contradicted' "
    "if the source states the opposite. Do not use outside knowledge. Respond as a single "
    'JSON object: {"verifications": [{"claim_id": str, "verdict": "supported"|"partial"|'
    '"unsupported"|"contradicted", "confidence": <0..1>, "rationale": str}]}.'
)


def verify_messages(claims: list[Claim], source_text: str) -> list[dict]:
    lines = "\n".join(f"{c.id}\t{c.quote}\t{c.text}" for c in claims)
    user = (
        "SOURCE TEXT:\n"
        f"{source_text}\n\n"
        "CLAIMS (one per line, tab-separated: claim_id, supporting_quote, claim_text):\n"
        f"{lines}\n\n"
        "Return only the JSON object."
    )
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user},
    ]
