"""
End-to-end pipeline: fetch → deduplicate → curate → index → rank → generate.

The vector store is dependency-injected. The default is the pgvector
implementation in `app.pipeline.rag.vector_store.ArticleVectorStore`.
Pass a stub in tests to avoid a Postgres dependency.
"""
from __future__ import annotations

import structlog

from app.pipeline.models import NewsletterDigest, UserProfile
from app.pipeline.ingestion.fetcher import RSSFetcher
from app.pipeline.ingestion.deduplicator import ArticleDeduplicator
from app.pipeline.ingestion.curator import ArticleCurator
from app.pipeline.store import ArticleStore
from app.pipeline.personalization.ranker import rank_articles
from app.pipeline.llm.newsletter import NewsletterGenerator
from app.pipeline.llm.client import LLMClient

log = structlog.get_logger()


class NewsPipeline:
    """
    Orchestrates the full news intelligence pipeline for one user.

    Steps:
      fetch → deduplicate → curate (LLM editorial pass) → index → retrieve → rank → generate
    """

    def __init__(self, store=None):
        self._fetcher = RSSFetcher()
        self._deduplicator = ArticleDeduplicator()
        self._curator = ArticleCurator()
        self._store = store if store is not None else ArticleStore()
        self._llm = LLMClient()
        self._generator = NewsletterGenerator(self._llm)

    async def run_for_user(self, user: UserProfile) -> NewsletterDigest:
        log.info("pipeline.start", user_id=user.user_id)

        # 1. Fetch from RSS feeds relevant to this user's interests
        raw_articles = await self._fetcher.fetch_for_user(user)
        log.info("pipeline.fetched", count=len(raw_articles))

        # 2. URL-hash deduplication
        unique_articles = self._deduplicator.deduplicate(raw_articles)
        log.info("pipeline.deduped", before=len(raw_articles), after=len(unique_articles))

        # 3. LLM editorial curation — selects the 30 most newsworthy articles,
        #    filtering out low-quality posts and thematic duplicates before they
        #    ever reach the vector store.
        curated_articles = self._curator.curate(unique_articles, top_n=30, user=user)
        log.info("pipeline.curated", before=len(unique_articles), after=len(curated_articles))

        # 4. Save curated articles to Postgres
        saved = self._store.save_articles(curated_articles)
        log.info("pipeline.saved", new_articles=saved)

        # 5. Personalized ranking directly on curated articles
        results = [(a, 1.0) for a in curated_articles]
        ranked = rank_articles(results, user, top_n=12)
        log.info("pipeline.ranked", top_n=len(ranked))

        # 7. Generate newsletter with Claude
        digest = self._generator.generate(user=user, articles=ranked, top_n=6)
        log.info(
            "pipeline.done",
            articles_in_digest=len(digest.articles),
            cost_usd=digest.token_cost.estimated_cost_usd,
        )

        return digest

    @staticmethod
    def _build_interest_query(user: UserProfile) -> str:
        parts = [s.replace("_", " ") for s in user.topic_tags[:3]]
        if user.business_tags:
            parts.append(user.business_tags[0].replace("_", " "))
        if user.regulation_tags:
            parts.append(user.regulation_tags[0].replace("_", " "))
        if user.companies_to_track:
            parts += user.companies_to_track[:2]
        return " ".join(parts) + " latest news"
