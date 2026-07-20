"""Search provider registry — the only place config maps to a concrete search."""

from __future__ import annotations

from collections.abc import Callable

import httpx

from app.models.schemas import RunConfig

GetKey = Callable[[str], str | None]


def _require_client(name: str, client: httpx.AsyncClient | None) -> httpx.AsyncClient:
    if client is None:
        raise ValueError(f"search provider {name!r} requires an httpx client")
    return client


def get_search_provider(
    config: RunConfig,
    client: httpx.AsyncClient | None = None,
    get_key: GetKey | None = None,
):
    name = config.search_provider
    key_fn: GetKey = get_key or (lambda _provider: None)

    if name == "mock":
        from app.providers.search.mock import MockSearchProvider

        return MockSearchProvider()
    if name == "tavily":
        from app.providers.search.tavily import TavilySearchProvider

        return TavilySearchProvider(_require_client(name, client), key_fn)
    if name == "serper":
        from app.providers.search.serper import SerperSearchProvider

        return SerperSearchProvider(_require_client(name, client), key_fn)
    if name == "exa":
        from app.providers.search.exa import ExaSearchProvider

        return ExaSearchProvider(_require_client(name, client), key_fn)
    if name == "duckduckgo":
        from app.providers.search.duckduckgo import DuckDuckGoSearchProvider

        return DuckDuckGoSearchProvider()
    raise ValueError(f"unknown search provider: {name!r}")
