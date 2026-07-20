from __future__ import annotations

import httpx
import pytest

from app.models.schemas import PageContent, RunConfig, SearchResult
from app.providers.crawl.jina import JinaCrawlProvider
from app.providers.crawl.mock import MockCrawlProvider
from app.providers.crawl.registry import get_crawl_provider
from app.providers.crawl.trafilatura_provider import TrafilaturaCrawlProvider
from app.providers.llm.litellm_provider import LiteLLMProvider, model_string
from app.providers.llm.mock import MockLLMProvider
from app.providers.llm.registry import get_llm_provider
from app.providers.search.exa import ExaSearchProvider
from app.providers.search.mock import MockSearchProvider
from app.providers.search.registry import get_search_provider
from app.providers.search.serper import SerperSearchProvider
from app.providers.search.tavily import TavilySearchProvider


def _handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    if host == "api.tavily.com":
        return httpx.Response(
            200,
            json={"results": [{"title": "T", "url": "https://t", "content": "snip", "score": 0.9}]},
        )
    if host == "google.serper.dev":
        return httpx.Response(
            200, json={"organic": [{"title": "S", "link": "https://s", "snippet": "snip"}]}
        )
    if host == "api.exa.ai":
        return httpx.Response(
            200,
            json={"results": [{"title": "E", "url": "https://e", "text": "snip", "score": 0.8}]},
        )
    if host == "r.jina.ai":
        return httpx.Response(200, text="# Page\n\nmarkdown body")
    return httpx.Response(404)


def _key(_provider: str) -> str:
    return "test-key"


# --- registries: mock ---------------------------------------------------------


def test_registries_return_mock_types():
    cfg = RunConfig()  # all defaults are mock
    assert isinstance(get_llm_provider(cfg, _key), MockLLMProvider)
    assert isinstance(get_search_provider(cfg), MockSearchProvider)
    assert isinstance(get_crawl_provider(cfg), MockCrawlProvider)


def test_registry_unknown_names_raise():
    with pytest.raises(ValueError):
        get_llm_provider(RunConfig(llm_provider="nope"), _key)
    with pytest.raises(ValueError):
        get_search_provider(RunConfig(search_provider="nope"))
    with pytest.raises(ValueError):
        get_crawl_provider(RunConfig(crawl_provider="nope"))


def test_search_registry_requires_client_for_real_provider():
    with pytest.raises(ValueError):
        get_search_provider(RunConfig(search_provider="tavily"), client=None, get_key=_key)


def test_llm_registry_returns_litellm_and_maps_model():
    cfg = RunConfig(llm_provider="anthropic", llm_model="claude-x")
    provider = get_llm_provider(cfg, _key)
    assert isinstance(provider, LiteLLMProvider)
    assert provider.model == "anthropic/claude-x"
    assert model_string("litellm", "gpt-4o") == "gpt-4o"


async def test_registry_returns_named_adapters():
    async with httpx.AsyncClient(transport=httpx.MockTransport(_handler)) as client:
        assert isinstance(
            get_search_provider(RunConfig(search_provider="tavily"), client, _key),
            TavilySearchProvider,
        )
        assert isinstance(
            get_crawl_provider(RunConfig(crawl_provider="jina"), client, _key),
            JinaCrawlProvider,
        )
        assert isinstance(
            get_crawl_provider(RunConfig(crawl_provider="trafilatura"), client, _key),
            TrafilaturaCrawlProvider,
        )


# --- adapters: canned payload -> SearchResult (no live network) ---------------


async def test_tavily_maps_payload():
    async with httpx.AsyncClient(transport=httpx.MockTransport(_handler)) as client:
        results = await TavilySearchProvider(client, _key).search("q", 3)
    assert results and isinstance(results[0], SearchResult)
    assert results[0].url == "https://t"
    assert results[0].snippet == "snip"


async def test_serper_maps_payload():
    async with httpx.AsyncClient(transport=httpx.MockTransport(_handler)) as client:
        results = await SerperSearchProvider(client, _key).search("q", 3)
    assert results[0].url == "https://s"
    assert results[0].title == "S"


async def test_exa_maps_payload():
    async with httpx.AsyncClient(transport=httpx.MockTransport(_handler)) as client:
        results = await ExaSearchProvider(client, _key).search("q", 3)
    assert results[0].url == "https://e"
    assert results[0].snippet == "snip"


async def test_jina_maps_text():
    async with httpx.AsyncClient(transport=httpx.MockTransport(_handler)) as client:
        page = await JinaCrawlProvider(client).fetch("https://example.com/a")
    assert isinstance(page, PageContent)
    assert page.ok
    assert "markdown body" in page.text
