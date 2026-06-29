"""
Wire-format schemas for Tag, Source, and Article resources.

These power `/tags`, `/sources`, `/articles/{id}`, and the `Citation` shape
that appears inside digest items and chat events (docs/api.md §3.4, §3.5, §4).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TagOut(BaseModel):
    """One tag in the taxonomy — `slug` is stored, `label` is displayed."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    label: str


class SourceOut(BaseModel):
    """One source in the `/sources` registry listing."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    category: str | None = None
    source_type: str | None = None
    region: list[str] = []
    content_quality: str | None = None


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
    image_url: str | None = None
    # Convenience: the `topic` dimension only (kept for existing callers).
    topics: list[str] = []
    # Full multi-dimensional tagging: {dimension: [slug, ...]}. Dimensions
    # are topic, business, regulation_policy, regional, role, seniority.
    tags: dict[str, list[str]] = {}
