"""End-to-end language selection: a run created with ``language: "th"`` produces
a Thai report with a single localized sources heading.

Regression: the frontend never sent a language, so every run defaulted to
English; and even when Thai was selected the report ended with two source
sections (a localized one plus an appended English "## Sources").
"""

from __future__ import annotations

import asyncio
import json

_MOCK = {"llm_provider": "mock", "search_provider": "mock", "crawl_provider": "mock"}


async def _drain_stream(auth_client, run_id: str, events: list[dict]) -> None:
    async with auth_client.stream("GET", f"/api/runs/{run_id}/stream") as resp:
        assert resp.status_code == 200
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            payload = line[len("data:") :].strip()
            if payload:
                events.append(json.loads(payload))


async def _run_to_completion(auth_client, *, language: str) -> dict:
    resp = await auth_client.post(
        "/api/runs",
        json={
            "query": "brand X",
            "language": language,
            "config": _MOCK,
            "require_plan_approval": False,
        },
    )
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["run_id"]
    events: list[dict] = []
    await asyncio.wait_for(_drain_stream(auth_client, run_id, events), timeout=5)
    detail = (await auth_client.get(f"/api/runs/{run_id}")).json()
    assert detail["status"] == "done", detail
    return detail


async def test_thai_run_produces_thai_report(auth_client):
    detail = await _run_to_completion(auth_client, language="th")
    assert detail["language"] == "th"
    report = detail["report"]
    assert "บทสรุปผู้บริหาร" in report  # Thai "Executive Summary"
    assert report.count("## แหล่งอ้างอิง") == 1  # single localized sources heading
    assert "## Sources" not in report  # no duplicate English heading


async def test_english_run_stays_english(auth_client):
    detail = await _run_to_completion(auth_client, language="en")
    assert detail["language"] == "en"
    report = detail["report"]
    assert "Executive Summary" in report
    assert "## Sources" in report
    assert "บทสรุป" not in report
