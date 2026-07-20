"""LiteLLM-backed LLM provider (Anthropic/OpenAI/Gemini/OpenAI-compatible).

One call surface via ``litellm.acompletion``. The API key is resolved lazily
through an injected ``get_key(provider)`` callable so credential storage (env
now, vault later) stays outside the provider.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import litellm

GetKey = Callable[[str], str | None]


def model_string(provider: str, model: str) -> str:
    """Map ``provider`` + ``model`` to a litellm model string."""
    if provider == "litellm":
        return model
    return f"{provider}/{model}"


class LiteLLMProvider:
    def __init__(self, provider: str, model: str, get_key: GetKey) -> None:
        self._provider = provider
        self._model = model
        self._get_key = get_key

    @property
    def model(self) -> str:
        return model_string(self._provider, self._model)

    def _base_kwargs(
        self, messages: list[dict], temperature: float, max_tokens: int | None
    ) -> dict:
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "api_key": self._get_key(self._provider),
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        return kwargs

    async def complete(
        self,
        messages: list[dict],
        *,
        tag: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        json: bool = False,
    ) -> str:
        kwargs = self._base_kwargs(messages, temperature, max_tokens)
        if json:
            kwargs["response_format"] = {"type": "json_object"}
        response = await litellm.acompletion(**kwargs)
        return response.choices[0].message.content or ""

    async def stream(
        self,
        messages: list[dict],
        *,
        tag: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        kwargs = self._base_kwargs(messages, temperature, max_tokens)
        kwargs["stream"] = True
        response = await litellm.acompletion(**kwargs)
        async for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
