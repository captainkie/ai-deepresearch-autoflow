"""Regression tests for ``AppSettings`` env-driven parsing.

The CORS allow-list is provided as a human-friendly comma-separated string via
``AUTOFLOW_CORS_ORIGINS`` (env or ``.env``). pydantic-settings treats
``list[str]`` as a complex field and JSON-decodes env values *before* field
validators run, so a plain comma string used to raise ``SettingsError`` at
startup. ``NoDecode`` on the field disables that JSON step so ``_split_origins``
can split the string. These tests exercise that exact path (which the app-level
fixtures, passing a ready-made list, never do).
"""

from __future__ import annotations

import pytest

from app.settings import AppSettings


def test_cors_origins_parses_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOFLOW_CORS_ORIGINS", "http://localhost:3000,http://localhost:3001")
    settings = AppSettings()
    assert settings.cors_origins == [
        "http://localhost:3000",
        "http://localhost:3001",
    ]


def test_cors_origins_single_value_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOFLOW_CORS_ORIGINS", "https://app.example.com")
    assert AppSettings().cors_origins == ["https://app.example.com"]


def test_cors_origins_strips_and_drops_blanks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOFLOW_CORS_ORIGINS", " http://a , , http://b ")
    assert AppSettings().cors_origins == ["http://a", "http://b"]


def test_cors_origins_default_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTOFLOW_CORS_ORIGINS", raising=False)
    # ``_env_file=None`` ignores any local ``.env`` so the default is deterministic.
    assert AppSettings(_env_file=None).cors_origins == ["http://localhost:3000"]
