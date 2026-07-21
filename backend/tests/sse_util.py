"""Helpers for reading Server-Sent-Event streams in tests.

Each SSE frame is a ``data: <json>`` line (comment/ping lines like ``: ping``
are ignored). We parse the JSON payload into a plain dict ``Event``.
"""

from __future__ import annotations

import json
from typing import Any

_TERMINAL = ("done", "error")


async def collect_stream(
    client, run_id: str, stop_types: tuple[str, ...] = _TERMINAL, max_events: int = 2000
) -> list[dict[str, Any]]:
    """Open the SSE stream and drain events until a terminal type (or cap)."""
    events: list[dict[str, Any]] = []
    async with client.stream("GET", f"/api/v1/runs/{run_id}/stream") as resp:
        assert resp.status_code == 200
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            payload = line[len("data:") :].strip()
            if not payload:
                continue
            events.append(json.loads(payload))
            if events[-1]["type"] in stop_types or len(events) >= max_events:
                break
    return events


def first_index(events: list[dict[str, Any]], predicate) -> int:
    return next(i for i, e in enumerate(events) if predicate(e))
