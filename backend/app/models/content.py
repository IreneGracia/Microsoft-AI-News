"""
Content ORM tables — Source, Article, Topic, ArticleTopic.

These tables are populated by the data-engineering pipeline (ingestion +
tagging). The backend reads from them to serve `/articles/{id}` and to
resolve citations on digest items and chat turns.

For MVP we keep article *bodies* out of Postgres (those live in Blob); only
metadata and a short extract sit here so citation rendering is cheap.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _new_article_id() -> str:
    return f"art_{uuid.uuid4().hex}"


def _new_source_id() -> str:
    return f"src_{uuid.uuid4().hex}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Topic(Base):
    """
    Fixed taxonomy chip exposed at `/topics`. Slug is the canonical key
    (stored in preferences and on ArticleTopic), label is for UI.
    """

    __tablename__ = "topics"

    slug: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)


class Source(Base):
    """
    A news source (TechCrunch, vendor blog, etc.). DE1 populates this from
    the curated source list. We expose `name` on citations.
    """

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_source_id)
    name: Mapped[str] = mapped_column(String, nullable=False)
    homepage_url: Mapped[str | None] = mapped_column(String, nullable=True)
    # Free-text licensing posture — compliance section in the final report
    # explains the values (e.g. "rss-snippet-only", "press-license", "public").
    license: Mapped[str | None] = mapped_column(String, nullable=True)


class Article(Base):
    """
    One ingested article. Body text lives in Blob (`body_blob_ref`); we only
    keep what we need to render citations and digest items.
    """

    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_article_id)
    source_id: Mapped[str] = mapped_column(
        String, ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    # ISO author byline — optional, depends on source.
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_utcnow
    )
    # Short extract for hover/preview rendering. Full body lives in Blob.
    extract: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_blob_ref: Mapped[str | None] = mapped_column(String, nullable=True)

    source: Mapped["Source"] = relationship()
    topics: Mapped[list["ArticleTopic"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )


class ArticleTopic(Base):
    """Article ↔ Topic join. DE2 writes these from tagging."""

    __tablename__ = "article_topics"

    article_id: Mapped[str] = mapped_column(
        String, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    topic_slug: Mapped[str] = mapped_column(
        String, ForeignKey("topics.slug", ondelete="CASCADE"), primary_key=True
    )

    article: Mapped["Article"] = relationship(back_populates="topics")
