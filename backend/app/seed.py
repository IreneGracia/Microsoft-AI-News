"""
Database seeding — taxonomy + dev demo data.

Two entry points:

  - `seed_tags(db)` — idempotent insert of the controlled tag vocabulary,
    read from sources.json `metadata.tags_taxonomy`. Called at startup in
    every environment because `/topics` and `/tags` must return something
    for the prefs UI from day one.

  - `seed_dev_demo(db, user)` — idempotent demo data for the dev user:
    a source, a handful of articles, and one past digest with items.
    Called from `/auth/dev-login` so the demo flow has something to show.
    Never called in prod (real data flows in via ingestion).

The taxonomy has no canonical slugs of its own — sources.json stores human
labels only — so slugs are derived deterministically from labels by
`tag_slug()`. The data-engineering tagger must use the same function when it
writes ArticleTag rows, or the slugs won't match.
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import (
    Article,
    ArticleTag,
    Digest,
    DigestItem,
    Source,
    Tag,
    User,
)

log = logging.getLogger(__name__)


def tag_slug(label: str) -> str:
    """
    Derive a stable, machine-friendly slug from a taxonomy label.

      "Artificial Intelligence & ML"      -> "artificial_intelligence_ml"
      "M&A & Funding"                     -> "ma_funding"
      "Data Protection (GDPR, DPDP, LGPD)" -> "data_protection_gdpr_dpdp_lgpd"

    Deterministic: same label always yields the same slug, so the tagger and
    the seeder agree without sharing state.
    """
    s = label.lower().replace("&", "")
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def _taxonomy_path() -> Path:
    """
    Locate sources.json. Override with the SOURCES_JSON_PATH env var; otherwise
    try each layout's expected location and use the first one that exists.

    Local dev: backend/app/seed.py -> repo root is 2 levels up.
    Container (backend/Dockerfile COPYs backend/app/ to /app/app/ and
    sources.json to /app/sources.json): the equivalent root is 1 level up.
    """
    override = os.environ.get("SOURCES_JSON_PATH")
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    for levels_up in (2, 1):
        candidate = here.parents[levels_up] / "sources.json"
        if candidate.exists():
            return candidate
    return here.parents[2] / "sources.json"


def _load_sources_doc() -> dict:
    """
    Parse sources.json once. Returns `{}` (logged) if the file is
    missing/malformed — the app still boots, just with an empty taxonomy
    and source registry.
    """
    path = _taxonomy_path()
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("seed: could not read sources.json from %s (%s)", path, exc)
        return {}


def _load_taxonomy() -> dict[str, list[str]]:
    """Return `{dimension: [label, ...]}` from sources.json metadata."""
    taxonomy = _load_sources_doc().get("metadata", {}).get("tags_taxonomy", {})
    if not isinstance(taxonomy, dict):
        log.warning("seed_tags: metadata.tags_taxonomy missing or not an object")
        return {}
    return taxonomy


def seed_tags(db: Session) -> None:
    """
    Insert any missing (dimension, slug) entries from the sources.json
    taxonomy. Existing rows are left alone — idempotent across boots.
    """
    taxonomy = _load_taxonomy()
    existing = {(t.dimension, t.slug) for t in db.query(Tag.dimension, Tag.slug).all()}

    new: list[Tag] = []
    for dimension, labels in taxonomy.items():
        if not isinstance(labels, list):
            continue
        for label in labels:
            slug = tag_slug(label)
            if (dimension, slug) not in existing:
                new.append(Tag(dimension=dimension, slug=slug, label=label))
                existing.add((dimension, slug))

    if not new:
        return
    db.add_all(new)
    db.commit()
    log.info("seed_tags: inserted %d tag(s)", len(new))


def seed_sources(db: Session) -> None:
    """
    Insert any missing sources from the sources.json registry. Existing rows
    are left alone — idempotent across boots. Populates the `sources` table
    that backs the `/sources` endpoint.
    """
    sources = _load_sources_doc().get("sources", [])
    if not isinstance(sources, list):
        log.warning("seed_sources: `sources` missing or not a list")
        return

    existing = {s_id for (s_id,) in db.query(Source.id).all()}

    new: list[Source] = []
    for entry in sources:
        if not isinstance(entry, dict):
            continue
        sid = entry.get("id")
        if not sid or sid in existing:
            continue
        region = entry.get("region", [])
        new.append(
            Source(
                id=sid,
                name=entry.get("name", sid),
                homepage_url=entry.get("homepage"),
                category=entry.get("category"),
                source_type=entry.get("source_type"),
                content_quality=entry.get("content_quality"),
                region_json=json.dumps(region if isinstance(region, list) else []),
            )
        )
        existing.add(sid)

    if not new:
        return
    db.add_all(new)
    db.commit()
    log.info("seed_sources: inserted %d source(s)", len(new))


# Marker on demo rows so we don't reseed on every dev-login.
_DEMO_SOURCE_ID = "src_demo_techpress"
_DEMO_ARTICLE_IDS = ["art_demo_001", "art_demo_002", "art_demo_003"]


def seed_dev_demo(db: Session, user: User) -> None:
    """
    Insert a small demo dataset tied to `user`. Safe to call repeatedly:
    skips work if the demo source already exists, and skips creating a
    digest if the user already has one.

    Demo article tags span multiple dimensions to exercise the multi-label
    ArticleTag join. Tag slugs are derived with `tag_slug()` from real
    taxonomy labels, so they line up with whatever `seed_tags` inserted —
    any tag whose dimension isn't in the seeded taxonomy is skipped rather
    than violating the foreign key.
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

    # Set of (dimension, slug) actually present, so demo tagging can't
    # violate the ArticleTag -> Tag foreign key if the taxonomy changes.
    valid_tags = {(t.dimension, t.slug) for t in db.query(Tag.dimension, Tag.slug).all()}

    base_time = datetime.now(timezone.utc) - timedelta(days=1)
    # (id, title, url, [(dimension, label), ...], extract)
    demo_articles_spec = [
        (
            _DEMO_ARTICLE_IDS[0],
            "Microsoft announces Phi-3 at Build 2024",
            "https://example.com/phi-3-build",
            [
                ("topic", "Artificial Intelligence & ML"),
                ("business", "Big Tech (FAANG+Microsoft)"),
                ("role", "For engineers (technical depth)"),
            ],
            "Microsoft introduced Phi-3 family with strong small-model performance.",
        ),
        (
            _DEMO_ARTICLE_IDS[1],
            "Azure AI Foundry pricing changes",
            "https://example.com/foundry-pricing",
            [
                ("topic", "Cloud & Infrastructure"),
                ("business", "Earnings & Revenue"),
                ("role", "For business & sales"),
            ],
            "Azure AI Foundry adjusts per-token pricing across new model tiers.",
        ),
        (
            _DEMO_ARTICLE_IDS[2],
            "AWS Bedrock adds new evaluation primitives",
            "https://example.com/bedrock-eval",
            [
                ("topic", "Cloud & Infrastructure"),
                ("topic", "Artificial Intelligence & ML"),
                ("role", "For researchers"),
            ],
            "Bedrock now exposes side-by-side evaluation flows for model selection.",
        ),
    ]
    for idx, (art_id, title, url, tag_specs, extract) in enumerate(demo_articles_spec):
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
        for dimension, label in tag_specs:
            slug = tag_slug(label)
            if (dimension, slug) not in valid_tags:
                # Taxonomy doesn't have this tag (e.g. sources.json missing) —
                # skip rather than fail the whole dev-login.
                log.info(
                    "seed_dev_demo: skipping unseeded tag (%s, %s)", dimension, slug
                )
                continue
            db.add(ArticleTag(article_id=art_id, dimension=dimension, slug=slug))

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
