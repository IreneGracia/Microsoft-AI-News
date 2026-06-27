"""
Data-engineering article model.

This dataclass is the in-memory representation used throughout the DE
pipeline (fetcher → deduplicator → embedder → writer).  It mirrors the
backend's `articles` table schema but has no SQLAlchemy or FastAPI
dependency — the DE service is self-contained.

The backend ORM (backend/app/models/content.py) remains the canonical
table definition; only the schema must stay in sync.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


def content_hash(url: str, title: str) -> str:
    """Stable hash of url+title used as the change-detection key."""
    h = hashlib.sha256()
    h.update(url.encode("utf-8"))
    h.update(b"|")
    h.update(title.encode("utf-8"))
    return h.hexdigest()


@dataclass
class ArticleRecord:
    """One article as it flows through the ingestion pipeline."""

    # ── Required ──────────────────────────────────────────────────────────────
    url: str
    title: str
    source_id: str
    rss_feed_url: str
    published_at: datetime

    # ── Populated by fetcher ──────────────────────────────────────────────────
    summary: str = ""          # RSS <description>/<content> snippet
    author: Optional[str] = None
    original_language: str = "en"

    # ── Populated by embedder ─────────────────────────────────────────────────
    # 384-dim float list — null until the embedding step runs.
    embedding: Optional[list[float]] = field(default=None, repr=False)

    @property
    def embed_text(self) -> str:
        """Text passed to the embedding model: title + body snippet."""
        return f"{self.title}\n\n{self.summary}" if self.summary else self.title

    @property
    def extract(self) -> Optional[str]:
        """Short preview (≤ 500 chars) for the frontend article card."""
        return self.summary[:500] if self.summary else None

    @property
    def hash(self) -> str:
        return content_hash(self.url, self.title)
