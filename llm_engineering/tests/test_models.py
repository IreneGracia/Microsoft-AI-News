"""Basic sanity checks on data models — no API calls needed."""
from datetime import datetime, timezone

from src.models import (
    Article,
    DigestFrequency,
    TechCategory,
    TonePreference,
    TokenUsage,
    UserProfile,
)


def test_token_usage_cost():
    usage = TokenUsage(input_tokens=1_000_000, output_tokens=0)
    assert abs(usage.estimated_cost_usd - 3.00) < 0.01

    usage2 = TokenUsage(input_tokens=0, output_tokens=1_000_000)
    assert abs(usage2.estimated_cost_usd - 15.00) < 0.01

    usage3 = TokenUsage(cache_read_tokens=1_000_000)
    assert abs(usage3.estimated_cost_usd - 0.30) < 0.01


def test_user_profile_defaults():
    user = UserProfile(
        user_id="u1",
        name="Alice",
        email="alice@microsoft.com",
        role="Engineering Manager",
        interests=[TechCategory.AI_ML, TechCategory.CLOUD],
    )
    assert user.tone == TonePreference.BALANCED
    assert user.digest_frequency == DigestFrequency.DAILY
    assert user.topic_weights == {}


def test_article_id_is_set():
    a = Article(
        id="abc123",
        url="https://techcrunch.com/article",
        title="Test Article",
        source="TechCrunch",
        published_at=datetime.now(timezone.utc),
        content="Some content here.",
    )
    assert a.id == "abc123"
    assert a.relevance_score == 0.0
