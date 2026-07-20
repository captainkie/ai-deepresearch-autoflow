from __future__ import annotations

import pytest

from app.providers.llm.mock import MockLLMProvider
from app.services.run_service import LlmCallCap

_MSG = [{"role": "user", "content": "hi"}]


async def test_llm_call_cap_allows_up_to_limit():
    cap = LlmCallCap(MockLLMProvider(), max_calls=2)
    assert await cap.complete(_MSG, tag="summarize")
    assert await cap.complete(_MSG, tag="summarize")


async def test_llm_call_cap_raises_past_limit():
    cap = LlmCallCap(MockLLMProvider(), max_calls=2)
    await cap.complete(_MSG, tag="summarize")
    await cap.complete(_MSG, tag="summarize")
    with pytest.raises(RuntimeError, match="LLM call cap"):
        await cap.complete(_MSG, tag="summarize")


async def test_llm_call_cap_counts_stream_calls():
    cap = LlmCallCap(MockLLMProvider(), max_calls=1)
    chunks = [chunk async for chunk in cap.stream(_MSG, tag="report")]
    assert chunks  # first stream call is within the cap
    with pytest.raises(RuntimeError, match="LLM call cap"):
        cap.stream(_MSG, tag="report")  # second call trips the cap immediately
