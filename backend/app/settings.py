"""Application-level settings for the HTTP API (distinct from per-run ``RunConfig``).

``AppSettings`` covers process-wide concerns: where the SQLite DB lives, which
CORS origins the browser frontend is served from, and the defaults applied when
a new run omits them. Secrets/provider keys are *not* here — they come from the
environment via ``services.provider_keys`` (the encrypted vault replaces that in
M3). Env vars use the ``AUTOFLOW_`` prefix, e.g. ``AUTOFLOW_DB_PATH``.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUTOFLOW_", extra="ignore")

    db_path: str = "./data/autoflow.db"
    cors_origins: list[str] = ["http://localhost:3000"]
    default_language: str = "en"
    default_require_plan_approval: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string (e.g. from ``AUTOFLOW_CORS_ORIGINS``)."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
