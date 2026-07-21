"""Claim extraction — turn a fetched page into atomic, source-grounded claims.

The verifier later checks each claim against its quote, so extraction enforces
the grounding invariant up front: a claim is kept only if its ``quote`` is a
verbatim span of the page (whitespace-normalized). Ungrounded claims are dropped
rather than trusted.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from uuid import uuid4

from app.models.schemas import Claim, PageContent
from app.providers.json_utils import JSONParseError, extract_json
from app.providers.llm.base import LLMProvider
from app.prompts.claims import claims_messages

_WS_RE = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS_RE.sub(" ", text).strip().lower()


def _is_grounded(quote: str, page_text: str) -> bool:
    q = _norm(quote)
    return bool(q) and q in _norm(page_text)


async def extract_claims(
    *,
    llm: LLMProvider,
    page: PageContent,
    goal: str,
    source_id: int,
    section_id: str | None = None,
    entity_schema: list[dict] | None = None,
    new_id: Callable[[], str] | None = None,
) -> list[Claim]:
    """Extract grounded :class:`Claim`s from ``page`` for the given ``source_id``."""
    if not page.ok or not page.text.strip():
        return []
    make_id = new_id or (lambda: uuid4().hex)

    raw = await llm.complete(claims_messages(goal, page, entity_schema), tag="claims", json=True)
    try:
        data = extract_json(raw)  # tolerant: strips fences, repairs trailing commas
    except JSONParseError:
        return []

    claims: list[Claim] = []
    for item in data.get("claims", []) or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        quote = str(item.get("quote", "")).strip()
        if not text or not _is_grounded(quote, page.text):
            continue
        claims.append(
            Claim(
                id=make_id(),
                text=text,
                quote=quote,
                source_ids=[source_id],
                section_id=section_id,
                entity=(item.get("entity") or None),
                attribute=(item.get("attribute") or None),
                stance=(item.get("stance") or None),
            )
        )
    return claims
