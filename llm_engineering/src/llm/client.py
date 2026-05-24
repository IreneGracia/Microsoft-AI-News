"""
LLM client with pluggable providers: Anthropic (default) and OpenAI.

All callers use LLMClient() — the provider is selected from settings.llm_provider.
Both implementations expose the same interface:
  complete(system, messages, model, max_tokens, use_cache) -> (str, TokenUsage)
  complete_fast(system, messages, max_tokens)              -> (str, TokenUsage)

Token economy notes:
- Anthropic: explicit cache_control breakpoints → 90 % cost reduction on cache hits
- OpenAI: automatic prompt caching on gpt-4o/gpt-4o-mini (prompts >1024 tokens)
  No special markup needed; cache hits appear as cached_tokens in usage.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import anthropic
import openai as openai_sdk

from src.models import TokenUsage
from config.settings import settings


# ---------------------------------------------------------------------------
# Shared interface
# ---------------------------------------------------------------------------

class _BaseLLMClient(ABC):
    @abstractmethod
    def complete(
        self,
        system: str,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 1500,
        use_cache: bool = True,
    ) -> tuple[str, TokenUsage]: ...

    @abstractmethod
    def complete_fast(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 512,
    ) -> tuple[str, TokenUsage]: ...


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------

class _AnthropicClient(_BaseLLMClient):
    # Pricing per million tokens (Sonnet 4.6)
    _INPUT_PRICE = 3.00 / 1_000_000
    _OUTPUT_PRICE = 15.00 / 1_000_000

    def __init__(self):
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def complete(
        self,
        system: str,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 1500,
        use_cache: bool = True,
    ) -> tuple[str, TokenUsage]:
        model = model or settings.llm_model

        if use_cache:
            system_content: list[dict] | str = [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ]
        else:
            system_content = system

        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_content,
            messages=messages,
        )

        u = response.usage
        return response.content[0].text, TokenUsage(
            input_tokens=u.input_tokens,
            output_tokens=u.output_tokens,
            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
        )

    def complete_fast(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 512,
    ) -> tuple[str, TokenUsage]:
        return self.complete(
            system=system,
            messages=messages,
            model=settings.llm_fast_model,
            max_tokens=max_tokens,
            use_cache=False,
        )


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------

class _OpenAIClient(_BaseLLMClient):
    # Pricing per million tokens (gpt-4o / gpt-4o-mini)
    _PRICES = {
        "gpt-4o":      {"input": 2.50, "output": 10.00, "cached": 1.25},
        "gpt-4o-mini": {"input": 0.15, "output":  0.60, "cached": 0.075},
    }

    def __init__(self):
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        self._client = openai_sdk.OpenAI(api_key=settings.openai_api_key)

    def complete(
        self,
        system: str,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 1500,
        use_cache: bool = True,  # OpenAI caching is automatic; flag is accepted but ignored
    ) -> tuple[str, TokenUsage]:
        model = model or settings.openai_model

        # OpenAI uses a "system" role message rather than a separate system param
        full_messages = [{"role": "system", "content": system}, *messages]

        response = self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=full_messages,
        )

        u = response.usage
        # OpenAI reports cached tokens under prompt_tokens_details
        cached = 0
        if u.prompt_tokens_details:
            cached = getattr(u.prompt_tokens_details, "cached_tokens", 0) or 0

        return response.choices[0].message.content, TokenUsage(
            input_tokens=u.prompt_tokens,
            output_tokens=u.completion_tokens,
            cache_read_tokens=cached,
        )

    def complete_fast(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 512,
    ) -> tuple[str, TokenUsage]:
        return self.complete(
            system=system,
            messages=messages,
            model=settings.openai_fast_model,
            max_tokens=max_tokens,
        )


# ---------------------------------------------------------------------------
# Factory — this is what all callers import
# ---------------------------------------------------------------------------

def LLMClient() -> _BaseLLMClient:
    """Return the configured LLM client. Set LLM_PROVIDER=openai to use OpenAI."""
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return _OpenAIClient()
    if provider == "anthropic":
        return _AnthropicClient()
    raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Choose 'anthropic' or 'openai'.")
