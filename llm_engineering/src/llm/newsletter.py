"""
Newsletter generation orchestrator.

Flow:
  1. Retrieve articles from vector store (or pass pre-fetched list)
  2. Call Claude with the newsletter system prompt + ranked article context
  3. Parse the JSON response into a NewsletterDigest
  4. Track token cost
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from src.models import (
    Article,
    DigestArticle,
    NewsletterDigest,
    TokenUsage,
    UserProfile,
)
from src.llm.client import LLMClient
from src.llm.prompts import build_newsletter_system_prompt, build_newsletter_user_message
from config.settings import settings


class NewsletterGenerator:
    def __init__(self, llm_client: LLMClient | None = None):
        self._llm = llm_client or LLMClient()

    def generate(
        self,
        user: UserProfile,
        articles: list[Article],
        top_n: int = 6,
    ) -> NewsletterDigest:
        """
        Generate a personalized newsletter digest.

        Token economy notes:
        - System prompt is cached (stable across calls for same tone)
        - Article context is variable (goes in user message, not cached)
        - We truncate article content to 800 chars before sending
        """
        system_prompt = build_newsletter_system_prompt(user)
        user_message = build_newsletter_user_message(articles, user, top_n)

        raw_response, token_usage = self._llm.complete(
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=settings.max_tokens_newsletter,
            use_cache=True,
        )

        digest_articles = self._parse_response(raw_response, articles)

        return NewsletterDigest(
            digest_id=str(uuid.uuid4()),
            user_id=user.user_id,
            generated_at=datetime.now(timezone.utc),
            articles=digest_articles,
            intro=self._extract_intro(raw_response),
            token_cost=token_usage,
        )

    def _parse_response(
        self, raw_response: str, source_articles: list[Article]
    ) -> list[DigestArticle]:
        """Parse Claude's JSON response into DigestArticle objects."""
        try:
            # Claude sometimes wraps JSON in markdown code blocks
            text = raw_response.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text)
        except json.JSONDecodeError:
            return []

        url_to_article = {a.url: a for a in source_articles}
        result: list[DigestArticle] = []

        for item in data.get("articles", []):
            url = item.get("url", "")
            article = url_to_article.get(url)

            if article is None:
                # Claude invented a URL — skip it (guards against hallucination)
                continue

            result.append(
                DigestArticle(
                    article=article,
                    rank=item.get("rank", len(result) + 1),
                    reason=item.get("reason", ""),
                    summary=item.get("summary", ""),
                    citation=f"Source: {article.source} — {article.url}",
                )
            )

        return sorted(result, key=lambda d: d.rank)

    @staticmethod
    def _extract_intro(raw_response: str) -> str:
        try:
            text = raw_response.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text)
            return data.get("intro", "")
        except (json.JSONDecodeError, KeyError):
            return ""
