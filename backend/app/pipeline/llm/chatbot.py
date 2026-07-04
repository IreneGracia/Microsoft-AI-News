"""
Chatbot — answers questions using today's curated news as context.
Articles are loaded from Postgres by ingestion date. When the query is a
"Tell me more about: <title>" (sent from the dashboard), we locate that
specific article and inject it at the top of the context with full content.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.models import Article as ArticleORM
from app.pipeline.models import Article, ChatMessage, ChatResponse, UserProfile
from app.pipeline.llm.client import LLMClient
from app.pipeline.llm.prompts import CHATBOT_SYSTEM_PROMPT, build_chat_messages
from app.config import settings

log = logging.getLogger(__name__)

_TELL_ME_MORE_PREFIX = "Tell me more about: "


class Chatbot:
    def __init__(self, llm_client: LLMClient | None = None):
        self._llm = llm_client or LLMClient()

    def chat(
        self,
        query: str,
        user: UserProfile,
        history: list[ChatMessage] | None = None,
    ) -> ChatResponse:
        history = history or []
        pinned, effective_query = _resolve_pinned(query)
        articles = _get_context_articles(query=effective_query, pinned_article=pinned, user=user)
        trimmed_history = _trim_history(history, max_turns=6)
        messages = build_chat_messages(effective_query, articles, trimmed_history, pinned=pinned, user=user)

        answer, token_usage = self._llm.complete(
            system=CHATBOT_SYSTEM_PROMPT,
            messages=messages,
            max_tokens=settings.max_tokens_chat,
            use_cache=True,
        )
        return ChatResponse(answer=answer, sources=articles, token_cost=token_usage)

    def stream_chat(
        self,
        query: str,
        user: UserProfile,
        history: list[ChatMessage] | None = None,
    ):
        """
        Yields:
          ('sources', list[Article])  — once, before first token
          ('token',   str)            — one per streamed chunk
          ('done',    TokenUsage)     — once, at end
        """
        history = history or []
        pinned, effective_query = _resolve_pinned(query)
        articles = _get_context_articles(query=effective_query, pinned_article=pinned, user=user)
        yield "sources", articles

        trimmed_history = _trim_history(history, max_turns=6)
        messages = build_chat_messages(effective_query, articles, trimmed_history, pinned=pinned, user=user)

        for text, usage in self._llm.stream_complete(
            system=CHATBOT_SYSTEM_PROMPT,
            messages=messages,
            max_tokens=settings.max_tokens_chat,
        ):
            if text:
                yield "token", text
            if usage is not None:
                yield "done", usage


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _resolve_pinned(query: str) -> tuple[Article | None, str]:
    """
    Detect "Tell me more about: <title>" queries from the dashboard.
    Returns (pinned_article_or_None, effective_query_for_llm).
    """
    if not query.startswith(_TELL_ME_MORE_PREFIX):
        return None, query

    title_fragment = query[len(_TELL_ME_MORE_PREFIX):]
    pinned = _find_article_by_title(title_fragment)
    if pinned:
        # Rewrite into a cleaner instruction so the LLM doesn't just repeat the prefix
        effective_query = (
            f"Explain this article in depth and discuss its implications for "
            f"our team: «{pinned.title}»"
        )
        return pinned, effective_query

    # Article not found in DB — fall back to the raw query
    return None, query


def _find_article_by_title(title_fragment: str) -> Article | None:
    """Find the best-matching article in the DB by partial title."""
    with SessionLocal() as db:
        row = (
            db.query(ArticleORM)
            .filter(ArticleORM.title.ilike(f"%{title_fragment[:120]}%"))
            .order_by(ArticleORM.ingested_at.desc())
            .limit(1)
            .first()
        )
        return _orm_to_pipeline(row) if row else None


# Cosine-similarity floor for chat context. Below this, an article is not
# actually about the question — returning it just decorates off-topic answers
# with mismatched "sources". Empirically, related query/article pairs score
# well above 0.4 with all-MiniLM-L6-v2; unrelated pairs sit under ~0.25.
_MIN_CONTEXT_SIMILARITY = 0.30


def _get_context_articles(
    query: str = "",
    limit: int = 20,
    pinned_article: Article | None = None,
    user: UserProfile | None = None,
) -> list[Article]:
    """
    Retrieve context articles for a chat query.
    Uses vector similarity search when embeddings are populated; falls back
    to recency-based retrieval only when search itself is unavailable (no
    embeddings / store error). When search ran but nothing clears the
    similarity floor, this returns [] — the question is off-corpus and the
    prompt is expected to say so rather than cite irrelevant articles.
    When a user profile is given, candidates are re-ranked with the
    personalization ranker so the user's topic/business/regulation/region
    preferences bias which articles reach the prompt — a soft boost, not a
    hard filter, so off-interest questions still find relevant articles.
    Source diversity is capped at 3 per publisher in both paths.
    """
    from app.pipeline.personalization.ranker import rank_articles

    articles: list[Article] = []
    search_ran = False

    # Try vector search first — much better relevance than recency alone.
    if query:
        try:
            from app.pipeline.rag.vector_store import ArticleVectorStore
            store = ArticleVectorStore()
            # Over-fetch when personalizing so the ranker has candidates to prefer.
            pairs = store.retrieve(query, top_k=limit * 2 if user else limit)
            # Empty result = no embeddings indexed yet → treat as unavailable.
            search_ran = bool(pairs)
            relevant = [(a, s) for a, s in pairs if s >= _MIN_CONTEXT_SIMILARITY]
            if user and relevant:
                articles = rank_articles(relevant, user, top_n=limit)
            else:
                articles = [a for a, _ in relevant]
        except Exception:
            log.debug("Vector search unavailable; falling back to recency retrieval")

    # Recency fallback ONLY when search couldn't run — not when it ran and
    # found nothing relevant (that would resurrect off-topic citations).
    if not articles and not search_ran:
        articles = _recency_articles(limit)
        if user and articles:
            # No similarity signal here — constant 1.0 lets tag overlap,
            # recency and source quality drive the ordering.
            articles = rank_articles([(a, 1.0) for a in articles], user, top_n=limit)

    if pinned_article:
        pinned_id = pinned_article.id
        articles = [pinned_article] + [a for a in articles if a.id != pinned_id][: limit - 1]

    return articles


def _recency_articles(limit: int) -> list[Article]:
    """Load recent articles with source diversity — fallback when embeddings unavailable."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    with SessionLocal() as db:
        rows = (
            db.query(ArticleORM)
            .filter(ArticleORM.ingested_at >= today_start)
            .order_by(ArticleORM.ingested_at.desc())
            .limit(limit * 4)
            .all()
        )
        if len(rows) < 5:
            rows = (
                db.query(ArticleORM)
                .order_by(ArticleORM.ingested_at.desc())
                .limit(limit * 4)
                .all()
            )
        return _diversify(rows, limit=limit)


def _diversify(rows: list, limit: int, max_per_source: int = 3) -> list[Article]:
    """Round-robin across sources to ensure variety in the context window."""
    by_source: dict[str, list] = {}
    for row in rows:
        sid = row.source_id or "unknown"
        by_source.setdefault(sid, []).append(row)

    result: list = []
    buckets = list(by_source.values())
    i = 0
    per_source: dict[str, int] = {}
    while len(result) < limit and any(buckets):
        bucket = buckets[i % len(buckets)]
        if bucket:
            row = bucket.pop(0)
            sid = row.source_id or "unknown"
            if per_source.get(sid, 0) < max_per_source:
                result.append(_orm_to_pipeline(row))
                per_source[sid] = per_source.get(sid, 0) + 1
        i += 1
        # Remove empty buckets
        buckets = [b for b in buckets if b]

    return result


def _trim_history(history: list[ChatMessage], max_turns: int) -> list[dict]:
    api_messages = [{"role": m.role, "content": m.content} for m in history]
    max_messages = max_turns * 2
    return api_messages[-max_messages:] if len(api_messages) > max_messages else api_messages


def _orm_to_pipeline(row: ArticleORM) -> Article:
    by_dim: dict[str, list[str]] = {}
    for t in (row.tags or []):
        by_dim.setdefault(t.dimension, []).append(t.slug)
    return Article(
        id=row.id,
        url=row.url,
        title=row.title,
        source=row.source.name if row.source else "",
        published_at=row.published_at,
        content=row.body or row.extract or "",
        summary=row.extract,
        topic_tags=by_dim.get("topic", []),
        business_tags=by_dim.get("business", []),
        regulation_tags=by_dim.get("regulation_policy", []),
        regions=by_dim.get("regional", []),
        source_type=(row.source.source_type if row.source and row.source.source_type else None) or "secondary",
    )
