"""
Digest ORM tables — Digest, DigestItem, Feedback.

A `Digest` is one rendered email a user received (or would receive). Its
`items` are the ranked articles, each with its LLM-written summary and a
list of cited article IDs.

Owned conceptually by the digest worker (D1 in architecture.md §3); the
API reads these tables to surface F8 (read-in-app) and F10 (feedback).
"""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _new_digest_id() -> str:
    return f"dgst_{uuid.uuid4().hex}"


def _new_item_id() -> str:
    return f"dgsti_{uuid.uuid4().hex}"


def _new_feedback_id() -> str:
    return f"fb_{uuid.uuid4().hex}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Digest(Base):
    """One digest delivery (or planned delivery) for one user."""

    __tablename__ = "digests"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_digest_id)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # When the worker produced this digest. We sort the user's list by this.
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, index=True
    )
    # When ACS/SendGrid actually accepted the send. Null = not delivered yet.
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Rendered HTML lives in Blob for cheap re-serving. Null until D2 renders.
    html_blob_ref: Mapped[str | None] = mapped_column(String, nullable=True)

    items: Mapped[list["DigestItem"]] = relationship(
        back_populates="digest",
        cascade="all, delete-orphan",
        order_by="DigestItem.rank",
    )


class DigestItem(Base):
    """One ranked article within a digest, with its LLM summary."""

    __tablename__ = "digest_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_item_id)
    digest_id: Mapped[str] = mapped_column(
        String, ForeignKey("digests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The "primary" article this item is about. Citations may include others.
    article_id: Mapped[str] = mapped_column(
        String, ForeignKey("articles.id", ondelete="RESTRICT"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    # Tone/length the summary was generated for — pinned per-item so we can
    # later re-render the same digest if the user changes preferences mid-history.
    tone: Mapped[str] = mapped_column(String, nullable=False)
    length: Mapped[str] = mapped_column(String, nullable=False)

    # JSON array of article_ids cited within `summary` beyond the primary.
    # Resolved to full citation objects at read time so we don't denormalize.
    citations_json: Mapped[str] = mapped_column(Text, default="[]")

    digest: Mapped["Digest"] = relationship(back_populates="items")

    def citation_ids(self) -> list[str]:
        try:
            return list(json.loads(self.citations_json) or [])
        except (TypeError, ValueError):
            return []


class Feedback(Base):
    """
    F10 — thumbs up/down per item per user. Composite uniqueness enforces
    one signal per (user, digest_item); a second POST overwrites.
    """

    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_feedback_id)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    digest_id: Mapped[str] = mapped_column(
        String, ForeignKey("digests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The article the user thumbed — we look up the corresponding item server-side.
    article_id: Mapped[str] = mapped_column(String, nullable=False)
    signal: Mapped[str] = mapped_column(String, nullable=False)  # "up" | "down"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("user_id", "digest_id", "article_id", name="uq_feedback_user_digest_article"),
    )
