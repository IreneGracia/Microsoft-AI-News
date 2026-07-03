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

from app.pipeline.models import TokenUsage
from app.config import settings


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

    @abstractmethod
    def stream_complete(
        self,
        system: str,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 1500,
    ):
        """
        Yields (text_chunk, token_usage) pairs.
        token_usage is None for every yield except the last, where text_chunk is "".
        """
        ...


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

    def stream_complete(self, system, messages, model=None, max_tokens=1500):
        model = model or settings.llm_model
        system_content = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        with self._client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system_content,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text, None
            msg = stream.get_final_message()
            u = msg.usage
            yield "", TokenUsage(
                input_tokens=u.input_tokens,
                output_tokens=u.output_tokens,
                cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
                cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
            )


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------

class _OpenAIClient(_BaseLLMClient):
    # Pricing per million tokens
    _PRICES = {
        "gpt-5.4-nano": {"input": 0.20, "output": 1.25, "cached": 0.02},
        "gpt-5.4-mini": {"input": 0.75, "output": 4.50, "cached": 0.075},
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
            max_completion_tokens=max_tokens,
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

    def stream_complete(self, system, messages, model=None, max_tokens=1500):
        model = model or settings.openai_model
        full_messages = [{"role": "system", "content": system}, *messages]
        stream = self._client.chat.completions.create(
            model=model,
            max_completion_tokens=max_tokens,
            messages=full_messages,
            stream=True,
            stream_options={"include_usage": True},
        )
        final_usage = TokenUsage()
        for chunk in stream:
            if getattr(chunk, "usage", None):
                u = chunk.usage
                cached = 0
                if getattr(u, "prompt_tokens_details", None):
                    cached = getattr(u.prompt_tokens_details, "cached_tokens", 0) or 0
                final_usage = TokenUsage(
                    input_tokens=u.prompt_tokens,
                    output_tokens=u.completion_tokens,
                    cache_read_tokens=cached,
                )
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content, None
        yield "", final_usage


# ---------------------------------------------------------------------------
# Gemini provider
# ---------------------------------------------------------------------------

class _GeminiClient(_BaseLLMClient):
    # Gemini 2.0 Flash is free-tier with generous limits.
    # Prompt caching is automatic (context cache API available but not needed for MVP).
    _INPUT_PRICE = 0.075 / 1_000_000   # $0.075 per 1M input tokens (≤128k)
    _OUTPUT_PRICE = 0.30 / 1_000_000   # $0.30 per 1M output tokens

    def __init__(self):
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        self._genai = genai

    def complete(
        self,
        system: str,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 1500,
        use_cache: bool = True,
    ) -> tuple[str, TokenUsage]:
        import google.generativeai as genai
        model_name = model or settings.gemini_model
        m = genai.GenerativeModel(model_name, system_instruction=system)
        # Convert OpenAI-style messages to Gemini format
        history = []
        for msg in messages[:-1]:
            role = "model" if msg["role"] == "assistant" else "user"
            history.append({"role": role, "parts": [msg["content"]]})
        last = messages[-1]["content"] if messages else ""
        chat = m.start_chat(history=history)
        response = chat.send_message(
            last,
            generation_config=genai.GenerationConfig(max_output_tokens=max_tokens),
        )
        usage = response.usage_metadata
        return response.text, TokenUsage(
            input_tokens=usage.prompt_token_count,
            output_tokens=usage.candidates_token_count,
        )

    def complete_fast(self, system, messages, max_tokens=512):
        return self.complete(system, messages, model=settings.gemini_fast_model, max_tokens=max_tokens)

    def stream_complete(self, system, messages, model=None, max_tokens=1500):
        import google.generativeai as genai
        model_name = model or settings.gemini_model
        m = genai.GenerativeModel(model_name, system_instruction=system)
        history = []
        for msg in messages[:-1]:
            role = "model" if msg["role"] == "assistant" else "user"
            history.append({"role": role, "parts": [msg["content"]]})
        last = messages[-1]["content"] if messages else ""
        chat = m.start_chat(history=history)
        response = chat.send_message(
            last,
            generation_config=genai.GenerationConfig(max_output_tokens=max_tokens),
            stream=True,
        )
        for chunk in response:
            if chunk.text:
                yield chunk.text, None
        # Emit final usage
        try:
            final = response.resolve()
            u = final.usage_metadata
            yield "", TokenUsage(
                input_tokens=u.prompt_token_count,
                output_tokens=u.candidates_token_count,
            )
        except Exception:
            yield "", TokenUsage()


# ---------------------------------------------------------------------------
# Factory — this is what all callers import
# ---------------------------------------------------------------------------

def LLMClient() -> _BaseLLMClient:
    """Return the configured LLM client based on LLM_PROVIDER env var."""
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return _OpenAIClient()
    if provider == "anthropic":
        return _AnthropicClient()
    if provider == "gemini":
        return _GeminiClient()
    raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Choose 'openai', 'anthropic', or 'gemini'.")
