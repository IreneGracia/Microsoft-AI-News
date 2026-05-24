from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------

class TechCategory(str, Enum):
    AI_ML = "ai_ml"
    CLOUD = "cloud"
    SECURITY = "security"
    DEVELOPER_TOOLS = "developer_tools"
    HARDWARE = "hardware"
    ENTERPRISE_SOFTWARE = "enterprise_software"
    STARTUPS = "startups"
    POLICY_REGULATION = "policy_regulation"
    OPEN_SOURCE = "open_source"
    OTHER = "other"


class DigestFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


class TonePreference(str, Enum):
    EXECUTIVE = "executive"    # high-level, strategic, no jargon
    TECHNICAL = "technical"    # deep dives, implementation details
    BALANCED = "balanced"      # mix of both


# ---------------------------------------------------------------------------
# Article (the atomic unit of news)
# ---------------------------------------------------------------------------

class Article(BaseModel):
    id: str                          # sha256 of url, used as chroma doc id
    url: str
    title: str
    source: str                      # e.g. "TechCrunch", "The Verge"
    published_at: datetime
    content: str                     # cleaned full text or best excerpt
    summary: Optional[str] = None    # LLM-generated, filled later
    categories: list[TechCategory] = []
    source_type: str = "secondary"   # "primary" | "secondary" | "aggregator"
    relevance_score: float = 0.0     # set during retrieval
    embedding_id: Optional[str] = None  # chroma doc id after indexing


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------

class UserProfile(BaseModel):
    user_id: str
    name: str
    email: str
    role: str                          # e.g. "Sales Engineer", "PM", "CTO"
    interests: list[TechCategory]
    companies_to_track: list[str] = [] # e.g. ["OpenAI", "Google", "AWS"]
    tone: TonePreference = TonePreference.BALANCED
    digest_frequency: DigestFrequency = DigestFrequency.DAILY
    # Used to personalize ranking weights — updated from implicit feedback
    topic_weights: dict[str, float] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Newsletter digest
# ---------------------------------------------------------------------------

class DigestArticle(BaseModel):
    """One ranked item inside a newsletter."""
    article: Article
    rank: int
    reason: str      # why it was ranked here (for explainability)
    summary: str     # personalized 2-3 sentence summary
    citation: str    # "Source: {source} — {url}"


class NewsletterDigest(BaseModel):
    digest_id: str
    user_id: str
    generated_at: datetime
    articles: list[DigestArticle]
    intro: str          # personalized opening paragraph
    token_cost: TokenUsage


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str   # "user" or "assistant"
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
