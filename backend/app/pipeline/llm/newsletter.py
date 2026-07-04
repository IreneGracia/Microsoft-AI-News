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

from app.pipeline.models import (
    Article,
    DigestArticle,
    NewsletterDigest,
    TokenUsage,
    UserProfile,
)
from app.pipeline.llm.client import LLMClient
from app.pipeline.llm.prompts import build_newsletter_system_prompt, build_newsletter_user_message
from app.config import settings


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

        digest_articles = self._parse_response(raw_response, articles, top_n)

        return NewsletterDigest(
            digest_id=str(uuid.uuid4()),
            user_id=user.user_id,
            generated_at=datetime.now(timezone.utc),
            articles=digest_articles,
            intro=self._extract_intro(raw_response),
            token_cost=token_usage,
        )

    def _parse_response(
        self, raw_response: str, source_articles: list[Article], top_n: int = 6
    ) -> list[DigestArticle]:
        """
        Parse Claude's JSON response into DigestArticle objects.

        Guards:
        - hallucinated URLs are skipped (not in the ranked input);
        - DUPLICATE URLs are skipped — the model sometimes pads its selection
          by listing the same article at two ranks, which shipped digests
          with repeated stories;
        - if dedup leaves fewer than `top_n`, the gap is backfilled from the
          remaining ranked articles (best-first) using the article's own
          extract as the summary, so the digest still carries `top_n`
          distinct stories.
        """
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
        seen_urls: set[str] = set()

        for item in data.get("articles", []):
            url = item.get("url", "")
            article = url_to_article.get(url)

            if article is None or url in seen_urls:
                # Invented or repeated URL — skip.
                continue
            seen_urls.add(url)

            result.append(
                DigestArticle(
                    article=article,
                    rank=item.get("rank", len(result) + 1),
                    reason=item.get("reason", ""),
                    summary=item.get("summary", ""),
                    citation=f"Source: {article.source} — {article.url}",
                )
            )

        result = sorted(result, key=lambda d: d.rank)[:top_n]

        # Backfill with the next-best ranked articles the model skipped.
        for article in source_articles:
            if len(result) >= top_n:
                break
            if article.url in seen_urls:
                continue
            seen_urls.add(article.url)
            result.append(
                DigestArticle(
                    article=article,
                    rank=len(result) + 1,
                    reason="Ranked highly for your interests.",
                    summary=article.summary or (article.content or "")[:220],
                    citation=f"Source: {article.source} — {article.url}",
                )
            )

        # Renumber sequentially so persisted ranks are clean.
        for i, entry in enumerate(result, start=1):
            entry.rank = i
        return result

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
