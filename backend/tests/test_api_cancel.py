"""Cancelling a run records a terminal state.

Regression: cancelling used to update the run row to ``cancelled`` but never emit
a terminal event, so a client that reconnected replayed the events up to
``awaiting_plan`` and stayed stuck on a "working" spinner. Cancel now emits a
persisted ``status: cancelled`` event that is the last thing a reconnecting
client sees.

Note on the test transport: ``httpx.ASGITransport`` buffers the whole SSE
response until the generator completes, so we drain the stream (which ends when
the server closes it on cancel) and poll ``GET /runs/{id}`` for status — same
approach as ``test_api_plan_approval``.
"""

from __future__ import annotations

import asyncio
import json

_MOCK = {"llm_provider": "mock", "search_provider": "mock", "crawl_provider": "mock"}


async def _drain_stream(auth_client, run_id: str, events: list[dict]) -> None:
    """Read the stream until the server closes it (no terminal-type shortcut)."""
    async with auth_client.stream("GET", f"/api/runs/{run_id}/stream") as resp:
        assert resp.status_code == 200
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            payload = line[len("data:") :].strip()
            if payload:
                events.append(json.loads(payload))


async def _wait_for_status(auth_client, run_id: str, target: str, tries=250, delay=0.02):
    for _ in range(tries):
        detail = (await auth_client.get(f"/api/runs/{run_id}")).json()
        if detail["status"] == target:
            return detail
        await asyncio.sleep(delay)
    raise AssertionError(f"run {run_id} never reached status {target!r}")


async def _create(auth_client, *, require_plan_approval: bool) -> str:
    resp = await auth_client.post(
        "/api/runs",
        json={
            "query": "brand X",
            "config": _MOCK,
            "require_plan_approval": require_plan_approval,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["run_id"]


async def test_cancel_awaiting_plan_emits_terminal_cancelled(auth_client):
    run_id = await _create(auth_client, require_plan_approval=True)
    events: list[dict] = []
    reader = asyncio.create_task(_drain_stream(auth_client, run_id, events))

    await _wait_for_status(auth_client, run_id, "awaiting_plan")
    resp = await auth_client.post(f"/api/runs/{run_id}/cancel")
    assert resp.status_code == 200

    # The server closes the stream on cancel, so the reader completes.
    await asyncio.wait_for(reader, timeout=5)

    detail = (await auth_client.get(f"/api/runs/{run_id}")).json()
    assert detail["status"] == "cancelled"

    cancelled = [
        e for e in events if e["type"] == "status" and e["data"].get("stage") == "cancelled"
    ]
    assert cancelled, f"no cancelled status event in {[e['type'] for e in events]}"


async def test_cancel_terminal_event_is_replayed_on_reconnect(auth_client):
    run_id = await _create(auth_client, require_plan_approval=True)
    first: list[dict] = []
    reader = asyncio.create_task(_drain_stream(auth_client, run_id, first))
    await _wait_for_status(auth_client, run_id, "awaiting_plan")
    await auth_client.post(f"/api/runs/{run_id}/cancel")
    await asyncio.wait_for(reader, timeout=5)

    # A fresh subscriber replays the persisted history; the LAST event it sees
    # must be the cancellation, not the earlier awaiting_plan (the bug).
    replay: list[dict] = []
    await asyncio.wait_for(_drain_stream(auth_client, run_id, replay), timeout=5)
    assert replay, "reconnect replayed no events"
    last = replay[-1]
    assert last["type"] == "status" and last["data"].get("stage") == "cancelled"


async def test_cancel_finished_run_is_noop(auth_client):
    run_id = await _create(auth_client, require_plan_approval=False)
    events: list[dict] = []
    await asyncio.wait_for(_drain_stream(auth_client, run_id, events), timeout=5)
    assert (await auth_client.get(f"/api/runs/{run_id}")).json()["status"] == "done"

    resp = await auth_client.post(f"/api/runs/{run_id}/cancel")
    assert resp.status_code == 200
    # A completed run must not be flipped to cancelled.
    assert (await auth_client.get(f"/api/runs/{run_id}")).json()["status"] == "done"


async def test_cancel_unknown_run_404(auth_client):
    resp = await auth_client.post("/api/runs/nope/cancel")
    assert resp.status_code == 404


async def test_submit_plan_after_cancel_conflicts(auth_client):
    # Cancelling a run awaiting approval must make a later /plan submit 409, not
    # silently 'succeed' on a dead approval future.
    run_id = await _create(auth_client, require_plan_approval=True)
    events: list[dict] = []
    reader = asyncio.create_task(_drain_stream(auth_client, run_id, events))
    await _wait_for_status(auth_client, run_id, "awaiting_plan")
    await auth_client.post(f"/api/runs/{run_id}/cancel")
    await asyncio.wait_for(reader, timeout=5)

    resp = await auth_client.post(f"/api/runs/{run_id}/plan", json={"approve": True})
    assert resp.status_code == 409
