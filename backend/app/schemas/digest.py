"""
Wire-format schemas for digest resources — docs/api.md §3.4.

`DigestSummary` is what the list endpoint returns (lightweight); `Digest`
is the full payload with items + citations.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.content import Citation


class DigestItemOut(BaseModel):
    """One ranked article inside a digest payload."""

    article_id: str
    rank: int
    title: str
    summary: str
    tone: str
    length: str
    citations: list[Citation] = []


class DigestSummary(BaseModel):
    """List item — no full payload, just enough for the dashboard."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    generated_at: datetime
    item_count: int


class Digest(BaseModel):
    """Full payload returned by GET /me/digests/{id}."""

    id: str
    generated_at: datetime
    items: list[DigestItemOut]


class FeedbackIn(BaseModel):
    """Body for POST /me/digests/{id}/feedback — F10."""

    article_id: str
    signal: Literal["up", "down"]
