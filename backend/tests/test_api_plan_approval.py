"""Human-in-the-loop plan approval.

NOTE on the test transport: ``httpx.ASGITransport`` buffers the whole SSE
response and only releases it once the response generator completes, so a reader
cannot observe ``awaiting_plan`` mid-stream. The run task runs independently and
persists ``awaiting_plan`` to SQLite regardless, so we detect the pause by
polling ``GET /runs/{id}`` and then POST ``/plan``; once the run finishes, the
buffered stream delivers the full event history. Under real uvicorn (see the
``serve`` command) sse-starlette streams incrementally — this buffering is purely
a test-auth_client artifact.
"""

from __future__ import annotations

import asyncio
import json

_MOCK_CONFIG = {"llm_provider": "mock", "search_provider": "mock", "crawl_provider": "mock"}


async def _create_run(auth_client):
    resp = await auth_client.post(
        "/api/v1/runs",
        json={"query": "brand X", "config": _MOCK_CONFIG, "require_plan_approval": True},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["run_id"]


async def _collect_stream(auth_client, run_id, events):
    async with auth_client.stream("GET", f"/api/v1/runs/{run_id}/stream") as resp:
        assert resp.status_code == 200
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            payload = line[len("data:") :].strip()
            if not payload:
                continue
            events.append(json.loads(payload))
            if events[-1]["type"] in ("done", "error"):
                break


async def _wait_for_status(auth_client, run_id, target, tries=250, delay=0.02):
    for _ in range(tries):
        detail = (await auth_client.get(f"/api/v1/runs/{run_id}")).json()
        if detail["status"] == target:
            return detail
        await asyncio.sleep(delay)
    raise AssertionError(f"run {run_id} never reached status {target!r}")


async def test_awaiting_plan_then_approve_as_is(auth_client):
    run_id = await _create_run(auth_client)
    events: list[dict] = []
    reader = asyncio.create_task(_collect_stream(auth_client, run_id, events))

    await _wait_for_status(auth_client, run_id, "awaiting_plan")

    resp = await auth_client.post(f"/api/v1/runs/{run_id}/plan", json={"approve": True})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    await asyncio.wait_for(reader, timeout=5)
    types = [e["type"] for e in events]
    assert "awaiting_plan" in types
    assert types[-1] == "done"
    # Mock plan has two sections; approve-as-is runs both.
    starts = [e for e in events if e["type"] == "section_start"]
    assert len(starts) == 2


async def test_awaiting_plan_then_edit_sections(auth_client):
    run_id = await _create_run(auth_client)
    events: list[dict] = []
    reader = asyncio.create_task(_collect_stream(auth_client, run_id, events))

    detail = await _wait_for_status(auth_client, run_id, "awaiting_plan")
    original = detail["plan"]["sections"]
    assert len(original) >= 1
    # Keep only the first section, with an edited title.
    edited = [
        {
            "id": original[0]["id"],
            "title": "EDITED " + original[0]["title"],
            "goal": original[0]["goal"],
            "queries": original[0]["queries"],
        }
    ]

    resp = await auth_client.post(f"/api/v1/runs/{run_id}/plan", json={"sections": edited})
    assert resp.status_code == 200

    await asyncio.wait_for(reader, timeout=5)
    starts = [e for e in events if e["type"] == "section_start"]
    assert len(starts) == 1
    assert starts[0]["data"]["title"].startswith("EDITED")

    final = (await auth_client.get(f"/api/v1/runs/{run_id}")).json()
    assert final["status"] == "done"
    assert len(final["sections"]) == 1
    assert final["sections"][0]["title"].startswith("EDITED")


async def test_plan_on_non_awaiting_run_conflicts(auth_client):
    # Auto-run (no approval required) never enters awaiting_plan.
    resp = await auth_client.post(
        "/api/v1/runs",
        json={"query": "auto", "config": _MOCK_CONFIG, "require_plan_approval": False},
    )
    run_id = resp.json()["run_id"]
    resp = await auth_client.post(f"/api/v1/runs/{run_id}/plan", json={"approve": True})
    assert resp.status_code == 409


async def test_plan_unknown_run_404(auth_client):
    resp = await auth_client.post("/api/v1/runs/nope/plan", json={"approve": True})
    assert resp.status_code == 404
