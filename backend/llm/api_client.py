"""
LLM API client abstraction.
Supports OpenRouter (OpenAI-compatible) with extensible base for future providers.
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Structured response from an LLM API call."""

    content: str
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str = ""
    raw: dict = field(default_factory=dict)


class LLMClientBase(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion from a list of messages."""
        ...

    @abstractmethod
    async def check_connection(self) -> bool:
        """Check if the provider is reachable and the API key is valid."""
        ...


class OpenRouterClient(LLMClientBase):
    """OpenRouter API client (OpenAI-compatible)."""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.llm.openrouter_api_key
        self.base_url = settings.llm.openrouter_base_url
        self.default_model = settings.llm.model
        self.max_response_tokens = settings.llm.max_response_tokens
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/ai-murder-mystery",
                    "X-Title": "AI Murder Mystery Game",
                },
                timeout=60.0,
            )
        return self._client

    async def generate(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate a completion via OpenRouter.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
            **kwargs: Override model, temperature, top_p, top_k,
                      repetition_penalty, max_tokens, etc.
        """
        settings = get_settings()

        payload: dict[str, Any] = {
            "model": kwargs.pop("model", self.default_model),
            "messages": messages,
            "max_tokens": kwargs.pop("max_tokens", self.max_response_tokens),
            "temperature": kwargs.pop("temperature", settings.sampler.temperature),
            "top_p": kwargs.pop("top_p", settings.sampler.top_p),
            "repetition_penalty": kwargs.pop(
                "repetition_penalty", settings.sampler.repetition_penalty
            ),
        }

        # Optional params that OpenRouter supports
        if "top_k" in kwargs:
            payload["top_k"] = kwargs.pop("top_k")
        elif settings.sampler.top_k > 0:
            payload["top_k"] = settings.sampler.top_k

        if "min_p" in kwargs:
            payload["min_p"] = kwargs.pop("min_p")
        elif settings.sampler.min_p > 0:
            payload["min_p"] = settings.sampler.min_p

        # Merge any remaining kwargs
        payload.update(kwargs)

        logger.debug(
            "OpenRouter request: model=%s, messages=%d, max_tokens=%d",
            payload["model"],
            len(messages),
            payload["max_tokens"],
        )

        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error("OpenRouter API error: %s — %s", e.response.status_code, e.response.text)
            raise
        except httpx.RequestError as e:
            logger.error("OpenRouter request failed: %s", e)
            raise

        choice = data["choices"][0]
        usage = data.get("usage", {})

        return LLMResponse(
            content=choice["message"]["content"],
            model=data.get("model", payload["model"]),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            finish_reason=choice.get("finish_reason", ""),
            raw=data,
        )

    async def check_connection(self) -> bool:
        """Verify API key and connectivity with a minimal request."""
        try:
            response = await self.client.get("/models")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def get_client(provider: str | None = None) -> LLMClientBase:
    """
    Factory function to get an LLM client by provider name.

    Args:
        provider: Provider name. Defaults to settings.llm.provider.
    """
    if provider is None:
        provider = get_settings().llm.provider

    match provider:
        case "openrouter":
            return OpenRouterClient()
        case _:
            raise ValueError(
                f"Unknown LLM provider: '{provider}'. "
                f"Available: openrouter"
            )
