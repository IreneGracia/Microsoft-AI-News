"""
Personalized article ranker.

Scoring formula:
  score = (semantic_similarity * 0.4)
        + (category_match * 0.3)
        + (company_mention * 0.2)
        + (recency * 0.1)

Weights can be overridden per user via topic_weights in UserProfile,
which are updated over time based on implicit feedback (clicks, reads).
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.models import Article, UserProfile, TechCategory


_DEFAULT_WEIGHTS = {
    "semantic": 0.35,
    "category": 0.25,
    "company": 0.20,
    "recency": 0.10,
    "source_quality": 0.10,  # primary sources (company blogs, gov) rank higher
}


def _recency_score(published_at: datetime) -> float:
    """Score from 0–1. Articles published within 24h score 1.0; decay over 7 days."""
    now = datetime.now(timezone.utc)
    age_hours = (now - published_at.replace(tzinfo=timezone.utc if published_at.tzinfo is None else published_at.tzinfo)).total_seconds() / 3600
    # Linear decay: 24h = 1.0, 168h (7 days) = 0.0
    return max(0.0, 1.0 - (age_hours / 168.0))


def _category_score(article: Article, user: UserProfile) -> float:
    """1.0 if any article category is in user interests, else 0.0."""
    user_cats = set(user.interests)
    article_cats = set(article.categories)
    return 1.0 if user_cats & article_cats else 0.0


def _company_score(article: Article, user: UserProfile) -> float:
    """1.0 if any tracked company is mentioned in title or content."""
    if not user.companies_to_track:
        return 0.0
    text = f"{article.title} {article.content}".lower()
    for company in user.companies_to_track:
        if company.lower() in text:
            return 1.0
    return 0.0


def _source_quality_score(article: Article) -> float:
    """Primary sources score 1.0, secondary 0.5, aggregators 0.2."""
    return {"primary": 1.0, "secondary": 0.5, "aggregator": 0.2}.get(article.source_type, 0.5)


def score_article(
    article: Article,
    semantic_similarity: float,
    user: UserProfile,
) -> float:
    """Compute the personalized relevance score for a single article."""
    weights = {**_DEFAULT_WEIGHTS, **user.topic_weights}

    # Normalize weights (user overrides may not sum to 1)
    total = sum(weights.values())
    w = {k: v / total for k, v in weights.items()}

    return (
        w["semantic"] * semantic_similarity
        + w["category"] * _category_score(article, user)
        + w["company"] * _company_score(article, user)
        + w["recency"] * _recency_score(article.published_at)
        + w["source_quality"] * _source_quality_score(article)
    )


def rank_articles(
    articles_with_similarity: list[tuple[Article, float]],
    user: UserProfile,
    top_n: int = 10,
) -> list[Article]:
    """
    Rank articles by personalized score and return the top_n.
    Sets article.relevance_score so downstream code can see the ranking signal.
    """
    scored: list[tuple[Article, float]] = []
    for article, similarity in articles_with_similarity:
        ps = score_article(article, similarity, user)
        article.relevance_score = round(ps, 4)
        scored.append((article, ps))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [article for article, _ in scored[:top_n]]
