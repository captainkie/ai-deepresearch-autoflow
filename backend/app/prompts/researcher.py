"""Researcher prompts: summarize a page, reflect on progress, compress notes."""

from __future__ import annotations

from app.models.schemas import PageContent


def summarize_messages(goal: str, page: PageContent) -> list[dict]:
    system = (
        "You summarize a web page strictly in service of a research goal. "
        "Be concise and factual; keep only what is relevant to the goal."
    )
    user = (
        f"GOAL: {goal}\n"
        f"SOURCE URL: {page.url}\n"
        f"PAGE TITLE: {page.title}\n"
        "PAGE CONTENT:\n"
        f"{page.text}\n"
        "Write a short summary of only the parts relevant to the goal."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def reflect_messages(goal: str, notes: str) -> list[dict]:
    system = (
        "You judge whether the notes gathered so far are sufficient for the goal. "
        'Respond with a single JSON object: {"need_more": bool, "queries": [str, ...]}. '
        "If more research is needed, include up to 3 new search queries; otherwise use "
        "an empty list."
    )
    user = f"GOAL: {goal}\nNOTES SO FAR:\n{notes}\nReturn only the JSON object."
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def compress_messages(goal: str, notes: str) -> list[dict]:
    system = (
        "You compress research notes into tight bullet findings with inline citations "
        "[n] that reference source ids. Keep only what serves the goal."
    )
    user = (
        f"GOAL: {goal}\n"
        f"NOTES:\n{notes}\n"
        "Return markdown bullets under a '### <goal>' heading, each citing its source [n]."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
