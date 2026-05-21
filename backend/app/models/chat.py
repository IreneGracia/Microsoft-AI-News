"""
Chat ORM tables — ChatSession, ChatTurn.

A session is a single conversation thread. Each user message and each LLM
reply is one `ChatTurn`; the `role` column distinguishes them.

The streaming POST endpoint persists the user turn synchronously, streams
the LLM reply over SSE, and persists the assistant turn at stream end
(architecture.md §6 sequence diagram).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _new_session_id() -> str:
    return f"sess_{uuid.uuid4().hex}"


def _new_message_id() -> str:
    return f"msg_{uuid.uuid4().hex}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ChatSession(Base):
    """One conversation thread for one user."""

    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_session_id)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # User-supplied or auto-derived from the first message. Optional.
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_utcnow, index=True
    )
    # Updated whenever a new turn is appended — drives the "recent sessions" sort.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_utcnow
    )
    # Soft delete — GDPR-aligned. Hard delete cascade happens on DELETE /me.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    turns: Mapped[list["ChatTurn"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatTurn.created_at",
    )


class ChatTurn(Base):
    """
    One message in a session. `role = "user"` for human input,
    `role = "assistant"` for the LLM reply.
    """

    __tablename__ = "chat_turns"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_message_id)
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String, nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # JSON list of {article_id, index} dicts for assistant turns. Empty for user turns.
    citations_json: Mapped[str] = mapped_column(Text, default="[]")

    # Token telemetry for the cost-per-user report. Null on user turns.
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_utcnow, index=True
    )

    session: Mapped["ChatSession"] = relationship(back_populates="turns")
