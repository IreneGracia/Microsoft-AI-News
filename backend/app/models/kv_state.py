"""
Tiny generic key-value table for things that don't deserve their own
schema — first use is the RSS fetcher's per-source watermarks, which
otherwise live in a JSON file on disk and get wiped by Container Apps
scale-to-zero restarts (L4).

The value column is plain TEXT (we store JSON-serialized strings).
Postgres has a `JSONB` type that would be nicer, but keeping it as TEXT
means SQLite (used in dev for the smoke tests) doesn't need a special
adapter. We control both sides of the read/write.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KvState(Base):
    """One row per named key. Caller owns the JSON shape inside `value`."""

    __tablename__ = "kv_state"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=_utcnow,
        onupdate=_utcnow,
    )
