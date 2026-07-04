"""
Personalized article ranker.

Scoring formula:
  score = (semantic_similarity   * 0.4375)
        + (tag_overlap           * 0.3125)
        + (recency               * 0.125)
        + (source_quality        * 0.125)

`tag_overlap` is the union match across all four content dimensions
(topic / business / regulation / regional). Weights can be overridden
per user via UserProfile.topic_weights, updated over time from implicit
feedback (clicks, reads).

`company_mention` is not in the default weights — backend preferences
don't yet collect which companies a user wants tracked
(UserProfile.companies_to_track is always [] from user_to_profile()), so
giving it a default weight would silently score every article 0 on that
dimension. It stays available as an opt-in: set `topic_weights={"company": ...}`
on a UserProfile and _company_score will contribute to the total again.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.pipeline.models import Article, UserProfile


_DEFAULT_WEIGHTS = {
    "semantic": 0.35,
    "tags": 0.25,
    "recency": 0.10,
    "source_quality": 0.10,
}


def _recency_score(published_at: datetime) -> float:
    """Score from 0–1. Articles published within 24h score 1.0; decay over 7 days."""
    now = datetime.now(timezone.utc)
    age_hours = (now - published_at.replace(tzinfo=timezone.utc if published_at.tzinfo is None else published_at.tzinfo)).total_seconds() / 3600
    return max(0.0, 1.0 - (age_hours / 168.0))


def _tag_overlap_score(article: Article, user: UserProfile) -> float:
    """
    1.0 if any tag overlaps between the user and the article across any of
    the four content dimensions. Multi-dimensional by design — a user who
    only cares about a regulation tag still matches an article tagged only
    in that dimension.
    """
    if (
        (set(article.topic_tags) & set(user.topic_tags))
        or (set(article.business_tags) & set(user.business_tags))
        or (set(article.regulation_tags) & set(user.regulation_tags))
        or (set(article.regions) & set(user.regions))
    ):
        return 1.0
    return 0.0


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
        + w["tags"] * _tag_overlap_score(article, user)
        + w.get("company", 0) * _company_score(article, user)
        + w["recency"] * _recency_score(article.published_at)
        + w["source_quality"] * _source_quality_score(article)
    )


def rank_articles(
    articles_with_similarity: list[tuple[Article, float]],
    user: UserProfile,
    top_n: int = 10,
    max_per_source: int = 3,
) -> list[Article]:
    """
    Rank articles by personalized score and return the top_n.
    Sets article.relevance_score so downstream code can see the ranking signal.

    Caps any single source at `max_per_source` articles so one publisher
    can't fill the whole digest just because it happens to tag-match the
    user's preferences well (mirrors the same cap in
    app.pipeline.rag.vector_store._diversify_by_source).
    """
    scored: list[tuple[Article, float]] = []
    for article, similarity in articles_with_similarity:
        ps = score_article(article, similarity, user)
        article.relevance_score = round(ps, 4)
        scored.append((article, ps))

    scored.sort(key=lambda x: x[1], reverse=True)

    per_source: dict[str, int] = {}
    result: list[Article] = []
    for article, _ in scored:
        if len(result) >= top_n:
            break
        source_key = article.source or "unknown"
        if per_source.get(source_key, 0) >= max_per_source:
            continue
        per_source[source_key] = per_source.get(source_key, 0) + 1
        result.append(article)

    return result
