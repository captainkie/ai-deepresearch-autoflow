"""Contradiction adjudication prompt: do two same-topic claims conflict?"""

from __future__ import annotations

from app.models.schemas import Claim

_SYSTEM = (
    "Two claims describe the same entity and attribute. Decide whether they CONFLICT "
    "(assert incompatible values/facts) or are compatible. Judge only the facts, not the "
    'wording. Respond as a single JSON object: {"conflict": bool, "note": str} where note '
    "briefly states the disagreement (empty if none)."
)


def contradiction_messages(a: Claim, b: Claim) -> list[dict]:
    user = (
        f"ENTITY: {a.entity}\n"
        f"ATTRIBUTE: {a.attribute}\n"
        f"CLAIM_A: {a.text}\n"
        f"CLAIM_B: {b.text}\n"
        "Return only the JSON object."
    )
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user},
    ]
