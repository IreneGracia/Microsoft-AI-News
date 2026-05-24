"""
Interactive CLI chat with the configured LLM.
Run: python3 scripts/chat.py
Type 'exit' or Ctrl+C to quit, 'clear' to reset conversation history.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from src.llm.client import LLMClient

SYSTEM = "You are MAI, a tech intelligence assistant. Answer questions about technology clearly and concisely, citing sources when you have them."

def main():
    client = LLMClient()
    history = []
    total_cost = 0.0

    print(f"\nMAI Chat — provider: {settings.llm_provider.upper()}")
    print("Type 'exit' to quit, 'clear' to reset history.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n\nTotal session cost: ${total_cost:.6f}")
            break

        if not user_input:
            continue
        if user_input.lower() == "exit":
            print(f"\nTotal session cost: ${total_cost:.6f}")
            break
        if user_input.lower() == "clear":
            history = []
            total_cost = 0.0
            print("History cleared.\n")
            continue

        history.append({"role": "user", "content": user_input})

        try:
            response, usage = client.complete(
                system=SYSTEM,
                messages=history,
                max_tokens=1000,
            )
        except Exception as e:
            print(f"Error: {e}\n")
            history.pop()
            continue

        history.append({"role": "assistant", "content": response})
        total_cost += usage.estimated_cost_usd

        print(f"\nMAI: {response}")
        print(f"     [tokens: {usage.input_tokens}in / {usage.output_tokens}out | cost: ${usage.estimated_cost_usd:.6f}]\n")


if __name__ == "__main__":
    main()
