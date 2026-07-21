from __future__ import annotations

from app.__about__ import VERSION


async def test_health_ok(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == VERSION


async def test_about_credits(client):
    resp = await client.get("/api/about")
    assert resp.status_code == 200
    body = resp.json()
    assert body["license"] == "AGPL-3.0"
    assert body["app"]
    assert body["version"] == VERSION
    assert body["org"]["name"] == "Fosivo Labs Co., Ltd."
    assert body["org"]["url"].startswith("http")

    author_names = " ".join(a["name"] for a in body["authors"])
    handles = {a["handle"] for a in body["authors"]}
    assert "Claude" in author_names
    assert "captainkie" in handles

    assert len(body["acknowledgements"]) >= 1
