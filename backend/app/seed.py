"""
Database seeding — taxonomy + dev demo data.

Two entry points:

  - `seed_topics(db)` — idempotent insert of the fixed taxonomy. Called at
    startup in every environment because `/topics` must return something
    for the prefs UI from day one.

  - `seed_dev_demo(db, user)` — idempotent demo data for the dev user:
    a source, a handful of articles, and one past digest with items.
    Called from `/auth/dev-login` so the demo flow has something to show.
    Never called in prod (real data flows in via ingestion).
"""

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import (
    Article,
    ArticleTopic,
    Digest,
    DigestItem,
    Source,
    Topic,
    User,
)


# Fixed taxonomy from docs/personas_and_features.md §3. The slug is the
# canonical key stored in preferences; the label is for the UI.
_TOPIC_TAXONOMY: list[tuple[str, str]] = [
    ("ai_ml", "AI / ML"),
    ("cloud", "Cloud"),
    ("security", "Security"),
    ("devtools", "DevTools"),
    ("data", "Data"),
    ("hardware", "Hardware"),
    ("regulation", "Regulation / Policy"),
    ("mna", "M&A"),
    ("open_source", "Open Source"),
    ("research", "Research"),
    ("mobile", "Mobile"),
    ("enterprise", "Enterprise"),
]


def seed_topics(db: Session) -> None:
    """Insert any missing taxonomy entries. Existing rows are left alone."""
    existing = {t.slug for t in db.query(Topic.slug).all()}
    new = [
        Topic(slug=slug, label=label)
        for slug, label in _TOPIC_TAXONOMY
        if slug not in existing
    ]
    if not new:
        return
    db.add_all(new)
    db.commit()


# Marker on demo rows so we don't reseed on every dev-login.
_DEMO_SOURCE_ID = "src_demo_techpress"
_DEMO_ARTICLE_IDS = ["art_demo_001", "art_demo_002", "art_demo_003"]


def seed_dev_demo(db: Session, user: User) -> None:
    """
    Insert a small demo dataset tied to `user`. Safe to call repeatedly:
    skips work if the demo source already exists, and skips creating a
    digest if the user already has one.
    """
    source = db.get(Source, _DEMO_SOURCE_ID)
    if source is None:
        source = Source(
            id=_DEMO_SOURCE_ID,
            name="TechPress (demo)",
            homepage_url="https://example.com",
            license="public",
        )
        db.add(source)

    base_time = datetime.now(timezone.utc) - timedelta(days=1)
    demo_articles_spec = [
        (
            _DEMO_ARTICLE_IDS[0],
            "Microsoft announces Phi-3 at Build 2024",
            "https://example.com/phi-3-build",
            ["ai_ml", "research"],
            "Microsoft introduced Phi-3 family with strong small-model performance.",
        ),
        (
            _DEMO_ARTICLE_IDS[1],
            "Azure AI Foundry pricing changes",
            "https://example.com/foundry-pricing",
            ["cloud", "enterprise"],
            "Azure AI Foundry adjusts per-token pricing across new model tiers.",
        ),
        (
            _DEMO_ARTICLE_IDS[2],
            "AWS Bedrock adds new evaluation primitives",
            "https://example.com/bedrock-eval",
            ["cloud", "ai_ml"],
            "Bedrock now exposes side-by-side evaluation flows for model selection.",
        ),
    ]
    for idx, (art_id, title, url, topic_slugs, extract) in enumerate(demo_articles_spec):
        if db.get(Article, art_id) is not None:
            continue
        article = Article(
            id=art_id,
            source_id=_DEMO_SOURCE_ID,
            title=title,
            url=url,
            author="Demo Author",
            published_at=base_time - timedelta(hours=idx),
            extract=extract,
        )
        db.add(article)
        db.flush()
        for slug in topic_slugs:
            db.add(ArticleTopic(article_id=art_id, topic_slug=slug))

    db.commit()

    # Only create a demo digest if this user doesn't have one yet.
    has_digest = (
        db.query(Digest.id).filter(Digest.user_id == user.id).first() is not None
    )
    if has_digest:
        return

    digest = Digest(user_id=user.id, generated_at=base_time)
    db.add(digest)
    db.flush()
    for rank, art_id in enumerate(_DEMO_ARTICLE_IDS, start=1):
        # Each item cites the *other* two demo articles, so the citation
        # resolution + ordering logic is exercised.
        cited = [a for a in _DEMO_ARTICLE_IDS if a != art_id]
        db.add(
            DigestItem(
                digest_id=digest.id,
                article_id=art_id,
                rank=rank,
                summary=(
                    "Demo summary: this is a deterministic placeholder rendered "
                    "in technical tone at standard length. Real summaries come "
                    "from the LLM Engineer's summarizer."
                ),
                tone="technical",
                length="standard",
                citations_json=json.dumps(cited),
            )
        )
    db.commit()
