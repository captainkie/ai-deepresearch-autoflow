from __future__ import annotations

from app.models.schemas import PageContent, SearchResult
from app.providers.crawl.mock import MockCrawlProvider
from app.providers.json_utils import extract_json
from app.providers.llm.mock import MockLLMProvider
from app.providers.search.mock import MockSearchProvider


async def test_mock_search_deterministic():
    provider = MockSearchProvider()
    first = await provider.search("brand X", 5)
    second = await provider.search("brand X", 5)
    assert len(first) == 5
    assert all(isinstance(r, SearchResult) for r in first)
    assert [r.url for r in first] == [r.url for r in second]
    assert all("example.com" in r.url for r in first)


async def test_mock_crawl_contains_url():
    page = await MockCrawlProvider().fetch("https://example.com/a")
    assert isinstance(page, PageContent)
    assert page.ok
    assert page.text
    assert "https://example.com/a" in page.text


async def test_mock_llm_plan_is_valid_json():
    out = await MockLLMProvider().complete(
        [{"role": "user", "content": "QUERY: brand X"}], tag="plan", json=True
    )
    data = extract_json(out)
    assert "brief" in data
    assert "sections" in data
    assert len(data["sections"]) >= 1


async def test_mock_llm_report_stream_has_heading_and_sources():
    chunks = [
        c
        async for c in MockLLMProvider().stream(
            [{"role": "user", "content": "OBJECTIVE: brand X"}], tag="report"
        )
    ]
    assert len(chunks) >= 1
    text = "".join(chunks)
    assert "# " in text
    assert "## Sources" in text


async def test_mock_llm_reflect_stops():
    out = await MockLLMProvider().complete(
        [{"role": "user", "content": "notes so far"}], tag="reflect"
    )
    data = extract_json(out)
    assert data["need_more"] is False
    assert data["queries"] == []


async def test_mock_llm_report_is_english_by_default():
    text = "".join(
        [
            c
            async for c in MockLLMProvider().stream(
                [{"role": "user", "content": "OBJECTIVE: brand X"}], tag="report"
            )
        ]
    )
    assert "Executive Summary" in text
    assert "บทสรุป" not in text


async def test_mock_llm_report_renders_thai_when_directive_present():
    # The Thai language_directive ("Write the report in Thai.") makes the mock
    # provider render Thai — so the offline demo actually reflects the chosen
    # language instead of always returning English.
    messages = [
        {"role": "system", "content": "You are a writer. Write the report in Thai."},
        {"role": "user", "content": "OBJECTIVE: brand X"},
    ]
    text = "".join([c async for c in MockLLMProvider().stream(messages, tag="report")])
    assert "บทสรุปผู้บริหาร" in text  # Thai "Executive Summary"
    assert "Executive Summary" not in text
