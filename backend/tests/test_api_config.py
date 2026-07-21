"""Runtime config API — the verifier-model round-trip.

Settings exposes an optional separate verifier provider/model (a cheap/fast model
to check claims). Empty ⇒ the verifier reuses the main language model.
"""

from __future__ import annotations


async def test_config_defaults_to_no_separate_verifier(auth_client):
    cfg = (await auth_client.get("/api/v1/config")).json()
    assert cfg["verifier"] == {"provider": "", "model": ""}


async def test_config_updates_and_persists_verifier(auth_client):
    updated = await auth_client.post(
        "/api/v1/config",
        json={"verifier_provider": "openai", "verifier_model": "gpt-4o-mini"},
    )
    assert updated.status_code == 200
    assert updated.json()["verifier"] == {"provider": "openai", "model": "gpt-4o-mini"}

    # Persisted across a fresh read.
    again = (await auth_client.get("/api/v1/config")).json()
    assert again["verifier"] == {"provider": "openai", "model": "gpt-4o-mini"}

    # Other config is untouched by a verifier-only update.
    assert again["llm"]["provider"]  # still present
    assert again["verification_level"] in ("off", "light", "strict")
