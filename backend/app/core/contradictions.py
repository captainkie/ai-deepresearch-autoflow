"""Contradiction detection — surface where verified claims disagree.

Groups *supported* claims by ``(entity, attribute)`` and adjudicates each pair
with the LLM. A conflict becomes a :class:`Contradiction` referencing both
claims (and, through them, both sources). Surfacing the conflict is the point —
we never silently pick a winner.
"""

from __future__ import annotations

import itertools
from collections import defaultdict
from collections.abc import Callable
from uuid import uuid4

from app.models.schemas import Claim, Contradiction, Verdict, Verification
from app.providers.json_utils import JSONParseError, extract_json
from app.providers.llm.base import LLMProvider
from app.prompts.contradictions import contradiction_messages


async def detect_contradictions(
    claims: list[Claim],
    verifications: list[Verification],
    llm: LLMProvider,
    *,
    new_id: Callable[[], str] | None = None,
) -> list[Contradiction]:
    make_id = new_id or (lambda: uuid4().hex)
    supported = {v.claim_id for v in verifications if v.verdict is Verdict.supported}

    groups: dict[tuple[str, str], list[Claim]] = defaultdict(list)
    for claim in claims:
        if claim.id in supported and claim.entity and claim.attribute:
            groups[(claim.entity, claim.attribute)].append(claim)

    out: list[Contradiction] = []
    for (entity, attribute), group in groups.items():
        for a, b in itertools.combinations(group, 2):
            raw = await llm.complete(contradiction_messages(a, b), tag="contradiction", json=True)
            try:
                data = extract_json(raw)
            except JSONParseError:
                continue
            if data.get("conflict"):
                out.append(
                    Contradiction(
                        id=make_id(),
                        entity=entity,
                        attribute=attribute,
                        claim_id_a=a.id,
                        claim_id_b=b.id,
                        note=str(data.get("note", "")),
                    )
                )
    return out
