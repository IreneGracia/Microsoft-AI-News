"""
Pipeline Pydantic models.

The tag taxonomy mirrors the backend's multi-dimensional design — see
docs/personas_and_features.md and backend/app/seed.tag_slug. Every tag is
a (dimension, slug) pair; the pipeline stores slugs grouped by dimension
on Article and UserProfile so a single article can carry a topic tag
*and* a business tag *and* a regulation tag without collapsing them into
a single enum value.

The previous flat `TechCategory` enum has been removed: it forced
information-losing collapses (e.g. M&A → STARTUPS, Cybersecurity Policy →
SECURITY) that broke fidelity between the data team's taxonomy and the
LLM pipeline. The pipeline now passes through slugs verbatim.
"""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums kept on the pipeline side (no equivalent in backend Preferences yet)
# ---------------------------------------------------------------------------

class DigestFrequency(str, Enum):
    DAILY = "daily"
    WEEKDAYS = "weekdays"
    WEEKLY = "weekly"


class TonePreference(str, Enum):
    EXECUTIVE = "executive"
    TECHNICAL = "technical"
    BUSINESS = "business"


# ---------------------------------------------------------------------------
# Article — flat representation of a fetched + tagged article
# ---------------------------------------------------------------------------

class Article(BaseModel):
    """
    One article moving through the pipeline. Tag fields hold backend
    slugs (e.g. "artificial_intelligence_ml", not "Artificial Intelligence & ML").
    """
    id: str
    url: str
    title: str
    source: str                      # human-friendly source name
    published_at: datetime
    content: str
    summary: Optional[str] = None

    # Multi-dimensional tags — mirrors the backend Tag taxonomy.
    topic_tags: list[str] = Field(default_factory=list)
    business_tags: list[str] = Field(default_factory=list)
    regulation_tags: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)

    image_url: Optional[str] = None           # first image extracted from RSS entry
    source_type: str = "secondary"   # "primary" | "secondary" | "aggregator"
    relevance_score: float = 0.0
    original_language: Optional[str] = None  # ISO 639-1 code detected at ingest time


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------

class UserProfile(BaseModel):
    """
    Pipeline's view of a backend user. Tag lists are slug arrays per
    dimension, matching the columns on backend Preferences.
    """
    user_id: str
    name: str
    email: str
    role: Optional[str] = None                    # role-dimension tag slug

    topic_tags: list[str] = Field(default_factory=list)
    business_tags: list[str] = Field(default_factory=list)
    regulation_tags: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)

    companies_to_track: list[str] = Field(default_factory=list)
    tone: TonePreference = TonePreference.TECHNICAL
    digest_frequency: DigestFrequency = DigestFrequency.WEEKLY

    # Implicit-feedback weights for the ranker (F10).
    topic_weights: dict[str, float] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Newsletter digest
# ---------------------------------------------------------------------------

class DigestArticle(BaseModel):
    """One ranked item inside a newsletter."""
    article: Article
    rank: int
    reason: str
    summary: str
    citation: str


class NewsletterDigest(BaseModel):
    digest_id: str
    user_id: str
    generated_at: datetime
    articles: list[DigestArticle]
    intro: str
    token_cost: TokenUsage


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Article]
    token_cost: TokenUsage


# ---------------------------------------------------------------------------
# Token economy tracking
# ---------------------------------------------------------------------------

class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost_usd(self) -> float:
        # Sonnet 4.6 pricing (per million tokens)
        input_price = 3.00 / 1_000_000
        output_price = 15.00 / 1_000_000
        cache_write_price = 3.75 / 1_000_000
        cache_read_price = 0.30 / 1_000_000
        return (
            self.input_tokens * input_price
            + self.output_tokens * output_price
            + self.cache_write_tokens * cache_write_price
            + self.cache_read_tokens * cache_read_price
        )
