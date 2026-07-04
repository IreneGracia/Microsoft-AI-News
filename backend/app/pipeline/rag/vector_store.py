"""
pgvector-backed article store.

Writes embeddings into the shared `articles` table so the API, pipeline,
and workers all read from one source of truth.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sentence_transformers import SentenceTransformer
from sqlalchemy import select

from app.config import settings
from app.db.session import SessionLocal
from app.models import Article as ArticleORM
from app.models import ArticleTag, Source, Tag
from app.pipeline.models import Article as PipelineArticle

log = logging.getLogger(__name__)


class ArticleVectorStore:

    def __init__(self, fallback_source_id: str = "src_pipeline"):
        self._encoder: SentenceTransformer | None = None
        self._fallback_source_id = fallback_source_id

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def save_articles(self, articles: list[PipelineArticle]) -> int:
        """Alias for index_articles — matches the ArticleStore interface."""
        return self.index_articles(articles)

    def index_articles(self, articles: list[PipelineArticle]) -> int:
        if not articles:
            return 0

        texts = [self._embed_text(a) for a in articles]
        embeddings = self._encode(texts)

        touched = 0
        with SessionLocal() as db:
            self._ensure_fallback_source(db)
            valid_tags = self._load_valid_tag_set(db)
            for article, embedding in zip(articles, embeddings):
                if self._upsert(db, article, embedding, valid_tags):
                    touched += 1
            db.commit()
        return touched

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: int = 8,
        topic_filter: list[str] | None = None,
        tag_filter: list[tuple[str, str]] | None = None,
        max_per_source: int = 3,
    ) -> list[tuple[PipelineArticle, float]]:
        """
        Return (article, cosine_similarity) pairs, reranked for recency and
        source diversity, highest-relevance first.

        Pure cosine similarity tends to surface several near-duplicate
        articles from whichever source published the most that day, and can
        rank a semantically-close but stale article above a fresher one. So
        we pull a wider candidate pool from pgvector, blend in a recency
        boost, then cap how many articles any single source contributes
        before truncating to top_k.
        """
        query_embedding = self._encode([query])[0]
        candidate_pool = max(top_k * 4, 40)

        pairs: list[tuple[str, str]] = list(tag_filter or [])
        if topic_filter:
            pairs.extend(("topic", slug) for slug in topic_filter)

        with SessionLocal() as db:
            stmt = (
                select(
                    ArticleORM,
                    ArticleORM.embedding.cosine_distance(query_embedding).label("distance"),
                )
                .where(ArticleORM.embedding.is_not(None))
            )

            if pairs:
                from collections import defaultdict
                from sqlalchemy import union
                grouped: dict[str, list[str]] = defaultdict(list)
                for dim, slug in pairs:
                    grouped[dim].append(slug)
                clauses = [
                    select(ArticleTag.article_id).where(
                        ArticleTag.dimension == dim,
                        ArticleTag.slug.in_(slugs),
                    )
                    for dim, slugs in grouped.items()
                ]
                stmt = stmt.where(ArticleORM.id.in_(union(*clauses)))

            stmt = stmt.order_by("distance").limit(candidate_pool)

            candidates: list[tuple[ArticleORM, float, str]] = []
            for row, distance in db.execute(stmt).all():
                similarity = round(1.0 - float(distance), 4)
                source_key = row.source.name if row.source else (row.source_id or "unknown")
                candidates.append((row, similarity, source_key))

            ranked = _rerank_by_recency(candidates)
            diversified = _diversify_by_source(ranked, max_per_source=max_per_source)[:top_k]

            return [(_orm_to_pipeline(row), similarity) for row, similarity in diversified]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if settings.embedding_provider.lower() == "gemini":
            return self._encode_gemini(texts)
        return self._encode_local(texts)

    def _encode_local(self, texts: list[str]) -> list[list[float]]:
        if self._encoder is None:
            self._encoder = SentenceTransformer(settings.embedding_model)
        return self._encoder.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        ).tolist()

    def _encode_gemini(self, texts: list[str]) -> list[list[float]]:
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        result = genai.embed_content(
            model=f"models/{settings.gemini_embedding_model}",
            content=texts,
            task_type="retrieval_document",
        )
        return result["embedding"] if len(texts) == 1 else list(result["embedding"])

    @staticmethod
    def _embed_text(article: PipelineArticle) -> str:
        return f"{article.title}\n\n{(article.content or '')[:1500]}"

    def _upsert(
        self,
        db,
        article: PipelineArticle,
        embedding: list[float],
        valid_tags: set[tuple[str, str]],
    ) -> bool:
        existing = db.query(ArticleORM).filter(ArticleORM.url == article.url).first()
        if existing is not None:
            changed = False
            if existing.embedding is None:
                existing.embedding = embedding
                changed = True
            if article.content and not existing.body:
                existing.body = article.content
                changed = True
            if article.image_url and not existing.image_url:
                existing.image_url = article.image_url
                changed = True
            return changed

        source_id = self._resolve_source_id(db, article.source)
        row = ArticleORM(
            id=f"art_{uuid.uuid4().hex}",
            source_id=source_id,
            title=article.title,
            url=article.url,
            author=None,
            published_at=_to_aware_utc(article.published_at),
            extract=article.summary or (article.content[:280] if article.content else None),
            body=article.content,
            image_url=article.image_url,
            embedding=embedding,
            original_language=article.original_language,
        )
        db.add(row)
        db.flush()

        for dimension, slugs in (
            ("topic", article.topic_tags),
            ("business", article.business_tags),
            ("regulation_policy", article.regulation_tags),
            ("regional", article.regions),
        ):
            for slug in slugs:
                if (dimension, slug) not in valid_tags:
                    continue
                db.add(ArticleTag(article_id=row.id, dimension=dimension, slug=slug))

        return True

    def _resolve_source_id(self, db, source_name: str) -> str:
        if not source_name:
            return self._fallback_source_id
        row = db.query(Source).filter(Source.name == source_name).first()
        return row.id if row else self._fallback_source_id

    def _ensure_fallback_source(self, db) -> None:
        if db.get(Source, self._fallback_source_id) is not None:
            return
        db.add(Source(
            id=self._fallback_source_id,
            name="Pipeline (uncategorized)",
            license="rss-snippet-only",
            source_type="aggregator",
        ))
        db.flush()

    @staticmethod
    def _load_valid_tag_set(db) -> set[tuple[str, str]]:
        return {(t.dimension, t.slug) for t in db.query(Tag.dimension, Tag.slug).all()}


def _recency_boost(published_at: datetime | None) -> float:
    """0..1 — full boost within the last 24h, decayed to 0 by 7 days out."""
    if published_at is None:
        return 0.0
    now = datetime.now(timezone.utc)
    pub = published_at if published_at.tzinfo else published_at.replace(tzinfo=timezone.utc)
    age_hours = (now - pub).total_seconds() / 3600
    return max(0.0, 1.0 - (age_hours / 168.0))


def _rerank_by_recency(
    candidates: list[tuple[ArticleORM, float, str]],
) -> list[tuple[ArticleORM, float, str]]:
    """Blend cosine similarity with a recency boost; similarity stays the
    dominant signal so relevance never loses to freshness."""
    def blended(item: tuple[ArticleORM, float, str]) -> float:
        row, similarity, _ = item
        return 0.8 * similarity + 0.2 * _recency_boost(row.published_at)

    return sorted(candidates, key=blended, reverse=True)


def _diversify_by_source(
    candidates: list[tuple[ArticleORM, float, str]],
    max_per_source: int,
) -> list[tuple[ArticleORM, float]]:
    """Drop candidates once a source has already contributed max_per_source
    articles, preserving the blended-score order otherwise."""
    per_source: dict[str, int] = {}
    result: list[tuple[ArticleORM, float]] = []
    for row, similarity, source_key in candidates:
        if per_source.get(source_key, 0) >= max_per_source:
            continue
        per_source[source_key] = per_source.get(source_key, 0) + 1
        result.append((row, similarity))
    return result


def _to_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _orm_to_pipeline(row: ArticleORM) -> PipelineArticle:
    by_dim: dict[str, list[str]] = {}
    for t in row.tags:
        by_dim.setdefault(t.dimension, []).append(t.slug)
    return PipelineArticle(
        id=row.id,
        url=row.url,
        title=row.title,
        source=row.source.name if row.source else "",
        published_at=row.published_at,
        content=row.body or row.extract or "",
        summary=row.extract,
        image_url=row.image_url,
        topic_tags=by_dim.get("topic", []),
        business_tags=by_dim.get("business", []),
        regulation_tags=by_dim.get("regulation_policy", []),
        regions=by_dim.get("regional", []),
        # Coalesce NULL source_type (e.g. demo/fallback sources) — the
        # pipeline model requires a string, and a None here crashes
        # retrieve(), silently degrading chat to the recency fallback.
        source_type=(row.source.source_type if row.source else None) or "secondary",
    )
