from __future__ import annotations

from tests.sse_util import collect_stream

_MOCK_CONFIG = {"llm_provider": "mock", "search_provider": "mock", "crawl_provider": "mock"}


async def _create_run(client):
    resp = await client.post(
        "/api/runs",
        json={"query": "replay me", "config": _MOCK_CONFIG, "require_plan_approval": False},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["run_id"]


async def test_reconnect_replays_full_history(client):
    run_id = await _create_run(client)

    # First connection runs the job to completion.
    live = await collect_stream(client, run_id)
    assert live[-1]["type"] == "done"
    live_seqs = [e["seq"] for e in live]
    assert live_seqs == sorted(live_seqs)
    assert len(set(live_seqs)) == len(live_seqs)

    # A fresh connection AFTER completion replays the entire history from SQLite.
    replay = await collect_stream(client, run_id)
    replay_seqs = [e["seq"] for e in replay]
    # Monotonic, contiguous 0..N ending in `done`.
    assert replay_seqs == list(range(len(replay)))
    assert replay[-1]["type"] == "done"
    assert [e["type"] for e in replay] == [e["type"] for e in live]
    assert len(replay) == live[-1]["seq"] + 1


async def test_repeated_reconnect_is_stable(client):
    run_id = await _create_run(client)
    await collect_stream(client, run_id)

    first = await collect_stream(client, run_id)
    second = await collect_stream(client, run_id)
    assert [e["seq"] for e in first] == [e["seq"] for e in second]
    assert [e["type"] for e in first] == [e["type"] for e in second]
    assert first[-1]["type"] == "done"
