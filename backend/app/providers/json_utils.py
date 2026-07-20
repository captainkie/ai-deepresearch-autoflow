"""Tolerant JSON extraction for LLM output.

LLMs wrap JSON in prose, fenced code blocks, and occasionally emit trailing
commas. ``extract_json`` recovers the first balanced JSON object from such text.
"""

from __future__ import annotations

import json
import re

__all__ = ["JSONParseError", "extract_json"]

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


class JSONParseError(ValueError):
    """Raised when no valid JSON object can be extracted from the text."""


def _find_object(text: str) -> str | None:
    """Return the first balanced ``{...}`` block, ignoring braces in strings."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _loads(candidate: str) -> dict:
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        repaired = _TRAILING_COMMA_RE.sub(r"\1", candidate)
        return json.loads(repaired)


def extract_json(text: str) -> dict:
    """Extract the first JSON object from ``text``.

    Strips ```` ```json ```` fences, brace-counts to isolate the object
    (ignoring braces inside strings), and retries once after removing trailing
    commas. Raises :class:`JSONParseError` if no valid object survives.
    """
    if not isinstance(text, str):  # defensive; callers pass provider output
        raise JSONParseError("expected str input")

    candidates: list[str] = []
    for match in _FENCE_RE.finditer(text):
        block = _find_object(match.group(1))
        if block is not None:
            candidates.append(block)
    whole = _find_object(text)
    if whole is not None:
        candidates.append(whole)

    for candidate in candidates:
        try:
            result = _loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(result, dict):
            return result

    raise JSONParseError("no valid JSON object found in text")
