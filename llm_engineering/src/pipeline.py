"""
End-to-end pipeline: fetch → deduplicate → index → rank → generate.

This is the entry point for scheduled newsletter runs and can also be
called manually to test the full flow.

The vector store is dependency-injected. In production the backend passes
in its pgvector-backed `ArticleVectorStore`; tests can pass a stub.
"""
from __future__ import annotations

import structlog

from src.models import NewsletterDigest, UserProfile
from src.ingestion.fetcher import RSSFetcher
from src.ingestion.deduplicator import ArticleDeduplicator
from src.rag.vector_store import ArticleVectorStore
from src.personalization.ranker import rank_articles
from src.llm.newsletter import NewsletterGenerator
from src.llm.client import LLMClient

log = structlog.get_logger()


class NewsPipeline:
    """
    Orchestrates the full news intelligence pipeline for one user.

    The vector store interface used here is structural (index_articles +
    retrieve); any object that implements those methods works. The
    backend injects its pgvector implementation; tests can pass a stub.
    """

    def __init__(self, vector_store=None):
        self._fetcher = RSSFetcher()
        self._deduplicator = ArticleDeduplicator()
        self._vector_store = vector_store if vector_store is not None else ArticleVectorStore()
        self._llm = LLMClient()
        self._generator = NewsletterGenerator(self._llm)

    async def run_for_user(self, user: UserProfile) -> NewsletterDigest:
        log.info("pipeline.start", user_id=user.user_id)

        # 1. Fetch from RSS feeds relevant to this user's interests
        raw_articles = await self._fetcher.fetch_for_user(user)
        log.info("pipeline.fetched", count=len(raw_articles))

        # 2. Semantic deduplication
        unique_articles = self._deduplicator.deduplicate(raw_articles)
        log.info("pipeline.deduped", before=len(raw_articles), after=len(unique_articles))

        # 3. Index into vector store (only new articles are embedded)
        indexed = self._vector_store.index_articles(unique_articles)
        log.info("pipeline.indexed", new_articles=indexed)

        # 4. Retrieve most relevant articles for this user via RAG
        query = self._build_interest_query(user)
        results = self._vector_store.retrieve(query=query, top_k=20)

        # 5. Personalized ranking
        ranked = rank_articles(results, user, top_n=12)
        log.info("pipeline.ranked", top_n=len(ranked))

        # 6. Generate newsletter with Claude
        digest = self._generator.generate(user=user, articles=ranked, top_n=6)
        log.info(
            "pipeline.done",
            articles_in_digest=len(digest.articles),
            cost_usd=digest.token_cost.estimated_cost_usd,
        )

        return digest

    @staticmethod
    def _build_interest_query(user: UserProfile) -> str:
        """
        Compose a free-text retrieval query from the user's preferences.
        Topic tags get top billing; we sprinkle in business/regulation tags
        and tracked companies so the embedding picks up adjacent signal.
        """
        parts = [s.replace("_", " ") for s in user.topic_tags[:3]]
        if user.business_tags:
            parts.append(user.business_tags[0].replace("_", " "))
        if user.regulation_tags:
            parts.append(user.regulation_tags[0].replace("_", " "))
        if user.companies_to_track:
            parts += user.companies_to_track[:2]
        return " ".join(parts) + " latest news"
