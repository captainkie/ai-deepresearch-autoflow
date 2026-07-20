"""Crawl provider registry — the only place config maps to a concrete crawler."""

from __future__ import annotations

from collections.abc import Callable

import httpx

from app.models.schemas import RunConfig

GetKey = Callable[[str], str | None]


def _require_client(name: str, client: httpx.AsyncClient | None) -> httpx.AsyncClient:
    if client is None:
        raise ValueError(f"crawl provider {name!r} requires an httpx client")
    return client


def get_crawl_provider(
    config: RunConfig,
    client: httpx.AsyncClient | None = None,
    get_key: GetKey | None = None,
):
    name = config.crawl_provider
    if name == "mock":
        from app.providers.crawl.mock import MockCrawlProvider

        return MockCrawlProvider()
    if name == "jina":
        from app.providers.crawl.jina import JinaCrawlProvider

        return JinaCrawlProvider(_require_client(name, client), get_key)
    if name == "trafilatura":
        from app.providers.crawl.trafilatura_provider import TrafilaturaCrawlProvider

        return TrafilaturaCrawlProvider(_require_client(name, client))
    raise ValueError(f"unknown crawl provider: {name!r}")
