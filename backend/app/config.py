"""RunConfig loading: merge environment (AUTOFLOW_*) with explicit overrides."""

from __future__ import annotations

import os

from app.models.schemas import RunConfig

_PREFIX = "AUTOFLOW_"
_STR_FIELDS = {
    "llm_provider": "LLM_PROVIDER",
    "llm_model": "LLM_MODEL",
    "search_provider": "SEARCH_PROVIDER",
    "crawl_provider": "CRAWL_PROVIDER",
    "template": "TEMPLATE",
    "language": "LANGUAGE",
}
_TRUTHY = {"1", "true", "yes", "on"}


def load_run_config(**overrides: object) -> RunConfig:
    """Build a :class:`RunConfig` from ``AUTOFLOW_*`` env vars + overrides.

    Overrides win over env; ``None`` overrides are ignored so callers can pass
    optional CLI flags straight through.
    """
    values: dict[str, object] = {}
    for field, env_name in _STR_FIELDS.items():
        raw = os.environ.get(_PREFIX + env_name)
        if raw is not None:
            values[field] = raw

    approval = os.environ.get(_PREFIX + "REQUIRE_PLAN_APPROVAL")
    if approval is not None:
        values["require_plan_approval"] = approval.strip().lower() in _TRUTHY

    values.update({k: v for k, v in overrides.items() if v is not None})
    return RunConfig(**values)
