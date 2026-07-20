"""Application-level settings for the HTTP API (distinct from per-run ``RunConfig``).

``AppSettings`` covers process-wide concerns: where the SQLite DB lives, which
CORS origins the browser frontend is served from, and the defaults applied when
a new run omits them. Secrets/provider keys are *not* here — they come from the
environment via ``services.provider_keys`` (the encrypted vault replaces that in
M3). Env vars use the ``AUTOFLOW_`` prefix, e.g. ``AUTOFLOW_DB_PATH``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUTOFLOW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_path: str = "./data/autoflow.db"
    # ``NoDecode`` stops pydantic-settings from JSON-decoding the env value so the
    # ``_split_origins`` validator can accept a plain comma-separated string.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    default_language: str = "en"
    default_require_plan_approval: bool = True

    # --- security (M3) ---
    # ``APP_ENV`` is intentionally un-prefixed (shared convention); the vault KEK
    # comes from ``AUTOFLOW_MASTER_KEY`` (base64, 32 bytes) — required in prod.
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    master_key: str | None = None
    jwt_secret: str | None = None

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
