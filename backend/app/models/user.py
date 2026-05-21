"""
User + Preferences ORM tables.

Shape comes from docs/auth.md §6 (users) and docs/api.md §3.2
(preferences). Kept deliberately small — chat/digest/article tables get
added as those features are built out.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _new_user_id() -> str:
    """
    Generate a new user ID with the `usr_` prefix.

    We use uuid4 hex for now; docs/api.md §5 specifies ULID-style IDs (sortable),
    but uuid4 is a fine MVP placeholder. Swap to python-ulid before we care
    about insertion-order on the index.
    """
    return f"usr_{uuid.uuid4().hex}"


def _utcnow() -> datetime:
    """Timezone-aware UTC `now()`. Always store timestamps in UTC."""
    return datetime.now(timezone.utc)


class User(Base):
    """
    A registered Microsoft employee.

    The real identity join key is `entra_oid` (the stable per-user-per-tenant
    object ID from Microsoft Entra). `email` is display-only and can change;
    `id` is our own internal identifier we expose in URLs.
    """

    __tablename__ = "users"

    # Our internal ID — what gets put into JWTs and used internally as FK target.
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_user_id)

    # Entra Object ID — stable per-user. This is the real identity key.
    # `unique=True` so two different Entra users can't share an account row.
    entra_oid: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)

    # Entra Tenant ID — must match Microsoft's tenant at insert time.
    # Stored so we can audit if anything ever bypasses single-tenant enforcement.
    entra_tid: Mapped[str] = mapped_column(String, nullable=False)

    # Display-only fields populated from Entra `preferred_username` and `name`.
    # We never authenticate against `email`.
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # Audit columns. `server_default=func.now()` so the DB stamps them even
    # if the app forgets to set them.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_utcnow
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Soft-delete marker. Hard delete happens 24h later — see docs/auth.md §9.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # One-to-one to preferences. `uselist=False` makes it a scalar, not a list.
    # `cascade="all, delete-orphan"` means deleting the user deletes preferences.
    preferences: Mapped["Preferences"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Preferences(Base):
    """
    Per-user newsletter preferences. Shape mirrors the JSON in docs/api.md §3.2.

    All fields are scalars — lists (topics, muted_sources) are stored as JSON
    text so we don't need a separate join table. Fine at MVP scale; revisit
    if we ever need to query "all users interested in topic X" cheaply.
    """

    __tablename__ = "preferences"

    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),  # GDPR cascade (docs/auth.md §9)
        primary_key=True,
    )

    # Stored as JSON text for now — list[str] in Pydantic, str in DB.
    # E.g. '["ai_ml", "cloud"]'
    topics_json: Mapped[str] = mapped_column(Text, default="[]")
    muted_sources_json: Mapped[str] = mapped_column(Text, default="[]")

    # Plain enums-as-strings. Validation happens in Pydantic schemas.
    frequency: Mapped[str] = mapped_column(String, default="weekly")
    delivery_day: Mapped[str] = mapped_column(String, default="monday")
    delivery_hour_local: Mapped[int] = mapped_column(default=8)
    length: Mapped[str] = mapped_column(String, default="standard")
    tone: Mapped[str] = mapped_column(String, default="technical")
    language: Mapped[str] = mapped_column(String, default="en")

    user: Mapped["User"] = relationship(back_populates="preferences")
