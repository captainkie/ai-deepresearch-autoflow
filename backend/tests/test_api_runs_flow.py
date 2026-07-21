from __future__ import annotations

from tests.sse_util import collect_stream, first_index

_MOCK_CONFIG = {"llm_provider": "mock", "search_provider": "mock", "crawl_provider": "mock"}


async def _create_run(auth_client, **body):
    payload = {
        "query": "Analyze competitor brand: ExampleCo",
        "config": _MOCK_CONFIG,
        "require_plan_approval": False,
    }
    payload.update(body)
    resp = await auth_client.post("/api/v1/runs", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["run_id"]


async def test_create_returns_run_id(auth_client):
    run_id = await _create_run(auth_client)
    assert isinstance(run_id, str) and run_id


async def test_stream_event_order_and_report(auth_client):
    run_id = await _create_run(auth_client)
    events = await collect_stream(auth_client, run_id)
    types = [e["type"] for e in events]

    assert events[0]["type"] == "status"
    assert events[0]["data"]["stage"] == "planning"
    assert types[-1] == "done"
    assert "awaiting_plan" not in types

    # A single fresh stream yields unique, monotonic seqs (replay/live de-duped).
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs)

    i_plan = first_index(events, lambda e: e["type"] == "plan")
    i_first_start = first_index(events, lambda e: e["type"] == "section_start")
    i_last_done = max(i for i, e in enumerate(events) if e["type"] == "section_done")
    i_writing = first_index(
        events, lambda e: e["type"] == "status" and e["data"]["stage"] == "writing"
    )
    i_first_delta = first_index(events, lambda e: e["type"] == "report_delta")
    i_report = first_index(events, lambda e: e["type"] == "report")
    i_done = first_index(events, lambda e: e["type"] == "done")

    assert i_plan < i_first_start < i_last_done < i_writing < i_first_delta < i_report < i_done
    assert "## Sources" in events[i_report]["data"]["markdown"]
    assert events[i_done]["data"]["source_count"] >= 1


async def test_detail_after_completion(auth_client):
    run_id = await _create_run(auth_client)
    await collect_stream(auth_client, run_id)

    detail = (await auth_client.get(f"/api/v1/runs/{run_id}")).json()
    assert detail["status"] == "done"
    assert detail["report"] and "## Sources" in detail["report"]
    assert detail["title"]
    assert len(detail["sources"]) >= 1
    assert len(detail["sections"]) >= 1
    assert all(s["summary"] for s in detail["sections"])
    assert detail["plan"] is not None
    assert detail["plan"]["sections"]


async def test_list_runs_newest_first(auth_client):
    first = await _create_run(auth_client, query="first topic")
    second = await _create_run(auth_client, query="second topic")
    body = (await auth_client.get("/api/v1/runs")).json()
    ids = [r["run_id"] for r in body["runs"]]
    assert ids.index(second) < ids.index(first)


async def test_stream_unknown_run_404(auth_client):
    resp = await auth_client.get("/api/v1/runs/does-not-exist/stream")
    assert resp.status_code == 404
