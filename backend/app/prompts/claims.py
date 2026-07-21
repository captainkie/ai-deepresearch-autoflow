"""Claim-extraction prompt: turn one page into atomic, source-grounded claims."""

from __future__ import annotations

from app.models.schemas import PageContent

_SYSTEM = (
    "You extract atomic, independently checkable claims from a web page, only ones "
    "that serve the research goal. Every claim MUST include a 'quote': a short span "
    "copied verbatim from the page that directly supports the claim (no paraphrase). "
    'Respond as a single JSON object: {"claims": [{"text": str, "quote": str, '
    '"entity": str|null, "attribute": str|null, "stance": "positive"|"neutral"|'
    '"negative"|null}]}. Omit anything you cannot ground in a verbatim quote.'
)


def claims_messages(
    goal: str, page: PageContent, entity_schema: list[dict] | None = None
) -> list[dict]:
    entity_block = ""
    if entity_schema:
        attrs = ", ".join(str(item.get("key", "")) for item in entity_schema if item.get("key"))
        entity_block = (
            "ENTITY_MODE: true\n"
            f"ATTRIBUTES: {attrs}\n"
            "Tag each claim with the entity it is about and, when it fits one of the "
            "ATTRIBUTES above, that attribute key.\n"
        )
    user = (
        f"GOAL: {goal}\n"
        f"{entity_block}"
        f"SOURCE URL: {page.url}\n"
        f"PAGE TITLE: {page.title}\n"
        "PAGE CONTENT:\n"
        f"{page.text}\n"
        "Return only the JSON object."
    )
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user},
    ]
