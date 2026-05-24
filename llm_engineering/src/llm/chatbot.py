"""
Chatbot orchestrator.

Flow:
  1. Embed user query
  2. Retrieve top-k relevant articles from vector store
  3. Call Claude with retrieved context + conversation history
  4. Return answer + source articles + token cost
"""
from __future__ import annotations

from src.models import Article, ChatMessage, ChatResponse, TokenUsage, UserProfile
from src.llm.client import LLMClient
from src.llm.prompts import CHATBOT_SYSTEM_PROMPT, build_chat_messages
from src.rag.vector_store import ArticleVectorStore
from config.settings import settings


class Chatbot:
    def __init__(
        self,
        vector_store: ArticleVectorStore | None = None,
        llm_client: LLMClient | None = None,
    ):
        self._store = vector_store or ArticleVectorStore()
        self._llm = llm_client or LLMClient()

    def chat(
        self,
        query: str,
        user: UserProfile,
        history: list[ChatMessage] | None = None,
    ) -> ChatResponse:
        """
        Answer a user question grounded in retrieved news.

        Token economy:
        - System prompt is cached (same for all users)
        - Retrieved context is injected in the user turn (variable, not cached)
        - Conversation history is kept short (last 6 turns max)
        """
        history = history or []

        # 1. Retrieve relevant articles
        results = self._store.retrieve(
            query=query,
            top_k=settings.retrieval_top_k,
            category_filter=user.interests if user.interests else None,
        )
        retrieved_articles = [article for article, _score in results]

        # 2. Build messages (history + new user message with context injected)
        # Trim history to last 6 turns to keep context window manageable
        trimmed_history = self._trim_history(history, max_turns=6)
        messages = build_chat_messages(query, retrieved_articles, trimmed_history)

        # 3. Call LLM
        answer, token_usage = self._llm.complete(
            system=CHATBOT_SYSTEM_PROMPT,
            messages=messages,
            max_tokens=settings.max_tokens_chat,
            use_cache=True,  # system prompt cached across all chat sessions
        )

        return ChatResponse(
            answer=answer,
            sources=retrieved_articles,
            token_cost=token_usage,
        )

    @staticmethod
    def _trim_history(history: list[ChatMessage], max_turns: int) -> list[dict]:
        """Convert ChatMessage list to API format, keeping only the last N turns."""
        api_messages = [{"role": m.role, "content": m.content} for m in history]
        # Each turn = 1 user + 1 assistant message
        max_messages = max_turns * 2
        return api_messages[-max_messages:] if len(api_messages) > max_messages else api_messages
