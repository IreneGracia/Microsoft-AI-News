"""Personalized ranker tests — no API calls needed."""
from datetime import datetime, timezone

import pytest

from src.models import Article, TechCategory, TonePreference, UserProfile
from src.personalization.ranker import rank_articles, score_article


def _make_user(**kwargs):
    defaults = dict(
        user_id="u1",
        name="Bob",
        email="bob@microsoft.com",
        role="Software Engineer",
        interests=[TechCategory.AI_ML],
        companies_to_track=["OpenAI"],
        tone=TonePreference.TECHNICAL,
    )
    defaults.update(kwargs)
    return UserProfile(**defaults)


def _make_article(title="Test", categories=None, content="", hours_ago=1):
    from datetime import timedelta
    return Article(
        id="x",
        url="https://example.com",
        title=title,
        source="TechCrunch",
        published_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        content=content,
        categories=categories or [TechCategory.AI_ML],
    )


def test_category_match_boosts_score():
    user = _make_user(interests=[TechCategory.AI_ML])
    article_match = _make_article(categories=[TechCategory.AI_ML])
    article_no_match = _make_article(categories=[TechCategory.CLOUD])

    score_match = score_article(article_match, 0.5, user)
    score_no_match = score_article(article_no_match, 0.5, user)
    assert score_match > score_no_match


def test_company_mention_boosts_score():
    user = _make_user(companies_to_track=["OpenAI"])
    article_mention = _make_article(content="OpenAI released a new model today.")
    article_no_mention = _make_article(content="Google released a new model today.")

    score_mention = score_article(article_mention, 0.5, user)
    score_no_mention = score_article(article_no_mention, 0.5, user)
    assert score_mention > score_no_mention


def test_rank_articles_returns_top_n():
    user = _make_user()
    articles = [(_make_article(title=f"Article {i}"), 0.5) for i in range(10)]
    ranked = rank_articles(articles, user, top_n=3)
    assert len(ranked) == 3


def test_recency_matters():
    user = _make_user()
    fresh = _make_article(hours_ago=1)
    stale = _make_article(hours_ago=150)

    score_fresh = score_article(fresh, 0.5, user)
    score_stale = score_article(stale, 0.5, user)
    assert score_fresh > score_stale
