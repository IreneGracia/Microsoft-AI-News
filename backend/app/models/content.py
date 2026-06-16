"""
Content ORM tables — Source, Article, Tag, ArticleTag.

These tables are populated by the data-engineering pipeline (ingestion +
tagging). The backend reads from them to serve `/articles/{id}` and to
resolve citations on digest items and chat turns.

Article body text is stored inline (`body`) along with its pgvector
embedding, so RAG retrieval and citation rendering both read straight
from Postgres with no separate blob store.

Tagging is multi-dimensional: the controlled vocabulary in `Tag` spans every
taxonomy dimension (topic, business, regulation_policy, regional, role,
seniority), and `ArticleTag` lets one article carry any number of tags in any
number of dimensions. Both are seeded/validated against sources.json — see
app.seed.seed_tags.
"""

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.db.base import Base


def _new_article_id() -> str:
    return f"art_{uuid.uuid4().hex}"


def _new_source_id() -> str:
    return f"src_{uuid.uuid4().hex}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tag(Base):
    """
    One entry in the controlled tag vocabulary.

    `(dimension, slug)` is the composite primary key — the same slug can
    legitimately appear in two dimensions, so neither column is unique alone.
    Seeded at startup from sources.json `metadata.tags_taxonomy`
    (app.seed.seed_tags), so all six dimensions live in this one table and
    adding a seventh dimension is zero schema change.

    `dimension` is one of: topic, business, regulation_policy, regional,
    role, seniority.
    """

    __tablename__ = "tags"

    dimension: Mapped[str] = mapped_column(String, primary_key=True)
    slug: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(String, nullable=False)


class Source(Base):
    """
    A news source (TechCrunch, vendor blog, etc.). DE1 populates this from
    the curated source registry in sources.json. We expose `name` on
    citations, and the registry fields below power the `/sources` endpoint
    and the digest worker's source-quality ranking factor.
    """

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_source_id)
    name: Mapped[str] = mapped_column(String, nullable=False)
    homepage_url: Mapped[str | None] = mapped_column(String, nullable=True)
    # Free-text licensing posture — compliance section in the final report
    # explains the values (e.g. "rss-snippet-only", "press-license", "public").
    license: Mapped[str | None] = mapped_column(String, nullable=True)
    # ─── Compliance fields (data-engineering pipeline writes these) ─────
    rss_feed_url: Mapped[str | None] = mapped_column(String, nullable=True)
    # "allowed" | "disallowed" | "unknown" — captured at ingestion time.
    robots_txt_status: Mapped[str | None] = mapped_column(String, nullable=True)

    # Registry metadata from sources.json. `category` (e.g. "Tech",
    # "Aggregator"), `source_type` (e.g. "primary", "secondary",
    # "aggregator"), `content_quality` (e.g. "full", "partial").
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String, nullable=True)
    content_quality: Mapped[str | None] = mapped_column(String, nullable=True)
    # A source can span multiple regions — stored as a JSON list of region
    # labels, e.g. '["Europe", "Global"]'.
    region_json: Mapped[str] = mapped_column(Text, default="[]")


class Article(Base):
    """
    One ingested article. Body text is stored inline in `body`; the vector
    store keeps the embedding under `embedding_id` for RAG retrieval.
    """

    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_article_id)
    source_id: Mapped[str] = mapped_column(
        String, ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    # URL is the natural dedup key. Unique-constrained so concurrent
    # workers can't both insert the same article — the loser hits an
    # IntegrityError on commit and falls back to the upsert path.
    url: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    # ISO author byline — optional, depends on source.
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_utcnow
    )
    # Short extract for hover/preview rendering.
    extract: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Full cleaned article text — used for embedding + LLM summarisation.
    body: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Compliance + traceability
    rss_feed_url: Mapped[str | None] = mapped_column(String, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    original_language: Mapped[str | None] = mapped_column(String, nullable=True)

    # Article embedding for RAG retrieval. Dimensionality is governed by
    # `settings.embedding_dim` (must match the encoder model). Null until
    # the data pipeline embeds the article. Cosine similarity search uses
    # the `<=>` operator (see backend/app/rag/vector_store.py).
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dim), nullable=True
    )

    source: Mapped["Source"] = relationship()
    tags: Mapped[list["ArticleTag"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )


class ArticleTag(Base):
    """
    Article ↔ Tag join, across every taxonomy dimension. DE2 writes these
    from tagging.

    An article can carry any number of tags in any number of dimensions
    (multi-label) — e.g. three `topic` tags plus one `regional` tag plus one
    `role` tag. Each row is one (article, dimension, slug) triple.

    The composite foreign key into `tags` means an article can only be
    tagged with a value that exists in the seeded taxonomy — an invalid
    `(dimension, slug)` pair is rejected by the database itself. (SQLite
    enforces this only with `PRAGMA foreign_keys=ON`, which app.db.session
    sets; Postgres enforces it unconditionally.)
    """

    __tablename__ = "article_tags"
    __table_args__ = (
        ForeignKeyConstraint(
            ["dimension", "slug"],
            ["tags.dimension", "tags.slug"],
            ondelete="CASCADE",
        ),
    )

    article_id: Mapped[str] = mapped_column(
        String, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    dimension: Mapped[str] = mapped_column(String, primary_key=True)
    slug: Mapped[str] = mapped_column(String, primary_key=True)

    article: Mapped["Article"] = relationship(back_populates="tags")
