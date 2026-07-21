"""The demo-only reset endpoint.

A scheduled job (GitHub Actions cron) periodically wipes the ephemeral demo DB so
accumulated test accounts / runs don't pile up. The endpoint is guarded by a shared
secret header, exists only when ``demo_mode`` is on, and re-seeds the demo admin so
the demo isn't left stuck on ``/setup``.
"""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

from app.main import _shutdown, _startup, create_app
from app.settings import AppSettings

RESET_TOKEN = "test-reset-token-xyz"  # noqa: S105 - test-only value


def _demo_settings(**over) -> AppSettings:
    base = dict(
        db_path=":memory:",
        cors_origins=["http://localhost:3000"],
        rate_limit_enabled=False,
        demo_mode=True,
        demo_admin_email="demo@example.com",
        demo_admin_password="DemoPass2026",
        demo_reset_token=RESET_TOKEN,
    )
    base.update(over)
    return AppSettings(**base)


@pytest.fixture
async def demo_reset_app():
    settings = _demo_settings()
    app = create_app()
    await _startup(app, settings)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        yield client
    await _shutdown(app)


async def test_reset_requires_valid_token(demo_reset_app):
    missing = await demo_reset_app.post("/api/v1/demo/reset")
    assert missing.status_code == 401
    wrong = await demo_reset_app.post(
        "/api/v1/demo/reset", headers={"X-Demo-Reset-Token": "not-the-token"}
    )
    assert wrong.status_code == 401


async def test_reset_wipes_data_and_reseeds_admin(demo_reset_app):
    login = await demo_reset_app.post(
        "/api/v1/auth/login", json={"email": "demo@example.com", "password": "DemoPass2026"}
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    await demo_reset_app.post(
        "/api/v1/runs", json={"query": "brand X", "require_plan_approval": False}, headers=headers
    )
    before = (await demo_reset_app.get("/api/v1/runs", headers=headers)).json()["runs"]
    assert before, "expected at least one run before reset"

    reset = await demo_reset_app.post(
        "/api/v1/demo/reset", headers={"X-Demo-Reset-Token": RESET_TOKEN}
    )
    assert reset.status_code == 200

    # The demo admin is re-seeded (can still log in) and prior data is gone.
    relogin = await demo_reset_app.post(
        "/api/v1/auth/login", json={"email": "demo@example.com", "password": "DemoPass2026"}
    )
    assert relogin.status_code == 200
    new_headers = {"Authorization": f"Bearer {relogin.json()['access_token']}"}
    after = (await demo_reset_app.get("/api/v1/runs", headers=new_headers)).json()["runs"]
    assert after == []


async def test_reset_is_404_outside_demo():
    settings = AppSettings(
        db_path=":memory:",
        cors_origins=["http://localhost:3000"],
        rate_limit_enabled=False,
        demo_mode=False,
        demo_reset_token=RESET_TOKEN,
    )
    app = create_app()
    await _startup(app, settings)
    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            # Existence is hidden entirely when not running as a demo.
            resp = await client.post(
                "/api/v1/demo/reset", headers={"X-Demo-Reset-Token": RESET_TOKEN}
            )
            assert resp.status_code == 404
    finally:
        await _shutdown(app)
