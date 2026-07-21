"""Public-demo hardening: AUTOFLOW_DEMO_MODE forces mock providers and refuses
credential entry / provider switching so a shared demo can't run up cost or
capture a real API key.
"""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

from app.main import _shutdown, _startup, create_app
from app.settings import AppSettings


@pytest.fixture
async def demo_client():
    settings = AppSettings(
        db_path=":memory:",
        cors_origins=["http://localhost:3000"],
        rate_limit_enabled=False,
        demo_mode=True,
    )
    app = create_app()
    await _startup(app, settings)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post(
            "/api/v1/setup",
            json={"email": "root@example.com", "name": "Root", "password": "supersecret1"},
        )
        client.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
        yield client
    await _shutdown(app)


async def test_demo_flag_is_exposed(demo_client):
    assert (await demo_client.get("/api/v1/health")).json()["demo_mode"] is True
    assert (await demo_client.get("/api/v1/config")).json()["demo_mode"] is True


async def test_demo_forbids_credential_entry_and_provider_switch(demo_client):
    cred = await demo_client.post(
        "/api/v1/admin/credentials",
        json={"provider": "anthropic", "label": "x", "secret": "sk-real"},
    )
    assert cred.status_code == 403

    rotate = await demo_client.post(
        "/api/v1/admin/credentials/rotate", json={"new_master_key": "x" * 44}
    )
    assert rotate.status_code == 403

    cfg = await demo_client.post("/api/v1/config", json={"llm_provider": "anthropic"})
    assert cfg.status_code == 403


async def test_demo_forces_mock_providers_on_a_run(demo_client):
    # Even if the caller asks for a real provider, the run is pinned to mock.
    resp = await demo_client.post(
        "/api/v1/runs",
        json={
            "query": "brand X",
            "config": {"llm_provider": "anthropic", "search_provider": "tavily"},
            "require_plan_approval": False,
        },
    )
    run_id = resp.json()["run_id"]
    detail = (await demo_client.get(f"/api/v1/runs/{run_id}")).json()
    assert detail["config"]["llm_provider"] == "mock"
    assert detail["config"]["search_provider"] == "mock"
