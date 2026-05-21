"""
Wire-format schemas for Topic and Article resources.

These power `/topics`, `/articles/{id}`, and the `Citation` shape that
appears inside digest items and chat events (docs/api.md §3.4, §3.5, §4).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TopicOut(BaseModel):
    """One entry in the taxonomy chip list."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    label: str
    description: str | None = None


class Citation(BaseModel):
    """
    Reusable citation shape — appears in digest items and chat `citation` events.

    Source and URL are spliced server-side from the Article row; the model
    never produces them, so URL hallucination is structurally impossible
    (architecture.md §6).
    """

    article_id: str
    title: str
    source: str
    url: str
    published_at: datetime


class ArticleOut(BaseModel):
    """Returned by GET /articles/{id} — citation hover/expand payload."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    source: str
    url: str
    published_at: datetime
    author: str | None = None
    extract: str | None = None
    topics: list[str] = []
