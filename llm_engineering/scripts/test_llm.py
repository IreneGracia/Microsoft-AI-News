"""
Quick smoke test for the LLM client.
Run: python3 scripts/test_llm.py
Uses whichever provider is set in .env (LLM_PROVIDER=openai or anthropic).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from src.llm.client import LLMClient


def test_basic_completion():
    print(f"\n--- Provider: {settings.llm_provider.upper()} ---")

    client = LLMClient()

    system = "You are a concise tech news assistant. Answer in 1-2 sentences."
    messages = [{"role": "user", "content": "What is retrieval-augmented generation?"}]

    print("Sending request...")
    text, usage = client.complete(system=system, messages=messages, max_tokens=200)

    print(f"\nResponse:\n{text}")
    print(f"\nToken usage:")
    print(f"  Input:       {usage.input_tokens}")
    print(f"  Output:      {usage.output_tokens}")
    print(f"  Cache read:  {usage.cache_read_tokens}")
    print(f"  Cache write: {usage.cache_write_tokens}")
    print(f"  Est. cost:   ${usage.estimated_cost_usd:.6f}")


def test_fast_model():
    print(f"\n--- Fast model ({settings.openai_fast_model if settings.llm_provider == 'openai' else settings.llm_fast_model}) ---")
    client = LLMClient()

    text, usage = client.complete_fast(
        system="Classify the topic in one word.",
        messages=[{"role": "user", "content": "Apple released a new M4 chip for MacBook Pro."}],
        max_tokens=10,
    )
    print(f"Classification: {text.strip()}")
    print(f"Cost: ${usage.estimated_cost_usd:.6f}")


def test_cache_hit():
    print("\n--- Cache hit test (call same system prompt twice) ---")
    client = LLMClient()

    system = "You summarize tech news in exactly one sentence."
    msgs = [{"role": "user", "content": "OpenAI released GPT-5 with improved reasoning."}]

    _, usage1 = client.complete(system=system, messages=msgs, max_tokens=100)
    _, usage2 = client.complete(system=system, messages=msgs, max_tokens=100)

    print(f"Call 1 — cache_write: {usage1.cache_write_tokens}, cache_read: {usage1.cache_read_tokens}")
    print(f"Call 2 — cache_write: {usage2.cache_write_tokens}, cache_read: {usage2.cache_read_tokens}")

    if settings.llm_provider == "anthropic":
        if usage2.cache_read_tokens > 0:
            print("Cache hit confirmed on call 2.")
        else:
            print("No cache hit yet (system prompt may be too short for caching, min 1024 tokens).")
    else:
        print("OpenAI caches automatically on prompts >1024 tokens. Short test prompts won't cache.")


if __name__ == "__main__":
    test_basic_completion()
    test_fast_model()
    test_cache_hit()
    print("\nAll tests passed.")
