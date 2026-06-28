"""
Digest worker — generates and persists daily digests (F3).

Triggered by the /api/v1/internal/run-digest-worker webhook, which is
itself fired on a schedule by .github/workflows/digest-cron.yml (GitHub
Actions cron — free, no card needed). The webhook authenticates with
WORKER_SHARED_SECRET; this module assumes the caller is trusted.

Flow (see docs/feature_endpoints.md F3):
  1. Find users whose frequency × delivery_day × delivery_hour_local
     makes today a delivery day, and who don't already have a digest
     for today (idempotency).
  2. For each eligible user:
       a. Build a pipeline UserProfile from their backend preferences.
       b. Run the LLM pipeline end-to-end (fetch → dedupe → rank → generate).
       c. Persist the resulting NewsletterDigest as Digest + DigestItem
          + Article rows via the integrations.llm_bridge adapter.

The LLM pipeline lives in the sibling `llm_engineering/` tree; we put it
on sys.path via integrations.bootstrap so backend code can import from
`src.*` without packaging it as a wheel.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.integrations import bootstrap, email
from app.integrations.digest_renderer import render_html, render_subject
from app.integrations.fetch_state import persisted_fetch_state
from app.models import Article, Digest, DigestItem, Preferences, Source, User

log = logging.getLogger(__name__)

# Source row used for pipeline-fetched articles when we can't match a
# specific publisher in the backend `sources` table. Created once on first
# run.
_PIPELINE_SOURCE_ID = "src_pipeline"
_PIPELINE_SOURCE_NAME = "Pipeline (uncategorized)"


def run() -> dict:
    """
    Entry point called by the internal webhook.

    Returns a summary the webhook echoes back. Always returns; per-user
    failures are logged and counted but don't crash the run.
    """
    with SessionLocal() as db:
        _ensure_pipeline_source(db)
        eligible = _find_eligible_users(db)
        log.info("digest_worker: eligible users today: %d", len(eligible))

        if not eligible:
            return {"eligible_users": 0, "generated": 0, "failed": 0}

        built = _build_pipeline()
        if built is None:
            log.warning("digest_worker: pipeline unavailable; skipping run")
            return {"eligible_users": len(eligible), "generated": 0, "failed": 0, "skipped_reason": "pipeline_unavailable"}
        pipeline, vector_store = built

        generated = 0
        failed = 0
        emailed = 0
        # Bracket the per-user loop with restore/save of the RSS fetcher's
        # watermarks (L4). The fetcher reads/writes a JSON file under the
        # hood; we just keep that file in sync with Postgres so Container
        # Apps cold starts don't lose state.
        with persisted_fetch_state(db):
            for user in eligible:
                try:
                    digest = _generate_for_user(db, pipeline, vector_store, user)
                    db.commit()
                    generated += 1
                    # Email is best-effort: an ACS outage shouldn't fail the
                    # generation we just committed. _deliver_email opens its own
                    # session to update sent_at.
                    if digest is not None and _deliver_email(user, digest):
                        emailed += 1
                except Exception:
                    log.exception("digest_worker: generation failed for user %s", user.id)
                    db.rollback()
                    failed += 1

        return {
            "eligible_users": len(eligible),
            "generated": generated,
            "emailed": emailed,
            "failed": failed,
        }


# ----------------------------------------------------------------------
# Eligibility
# ----------------------------------------------------------------------


_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

# Window after the last successful generation in which we refuse to
# generate again for the same user. 22h is enough to swallow per-user TZ
# jitter (DST transitions, near-midnight runs) without blocking the next
# scheduled cycle 24h later. Keep this strictly below the shortest
# delivery cadence (daily = 24h).
_IDEMPOTENCY_WINDOW = timedelta(hours=22)


def _find_eligible_users(db: Session) -> list[User]:
    """
    Per-user, timezone-aware eligibility predicate.

    A user is eligible right now if, evaluated in their own IANA timezone:
      1. today's weekday is a delivery day for their `frequency`
            daily     -> every day
            weekdays  -> Monday through Friday
            weekly    -> only on `delivery_day`
      2. the current local hour has reached `delivery_hour_local`
      3. they have not received a digest within `_IDEMPOTENCY_WINDOW`

    The worker is expected to run hourly (see digest-cron.yml); the hour
    check ensures we don't fire before 08:00 local, and the idempotency
    check ensures we don't fire repeatedly within the same local day.

    Soft-deleted users are excluded. Users with bad/missing timezone strings
    fall back to UTC rather than being skipped.
    """
    now_utc = datetime.now(timezone.utc)
    recent_cutoff = now_utc - _IDEMPOTENCY_WINDOW

    candidates = (
        db.query(User)
        .join(Preferences, Preferences.user_id == User.id)
        .filter(User.deleted_at.is_(None))
        .all()
    )

    recent_user_ids = {
        uid
        for (uid,) in db.query(Digest.user_id)
        .filter(Digest.generated_at >= recent_cutoff)
        .all()
    }

    eligible: list[User] = []
    for user in candidates:
        prefs = user.preferences
        if prefs is None:
            continue
        if user.id in recent_user_ids:
            continue

        local_now = _to_user_local(now_utc, prefs.timezone)

        if not _is_delivery_day(prefs.frequency, prefs.delivery_day, local_now):
            continue
        if local_now.hour < prefs.delivery_hour_local:
            continue

        eligible.append(user)

    return eligible


def _to_user_local(now_utc: datetime, tz_name: str | None) -> datetime:
    """Convert UTC to the user's local time, falling back to UTC on bad input."""
    try:
        zone = ZoneInfo(tz_name) if tz_name else ZoneInfo("UTC")
    except ZoneInfoNotFoundError:
        log.warning("digest_worker: unknown timezone %r, falling back to UTC", tz_name)
        zone = ZoneInfo("UTC")
    return now_utc.astimezone(zone)


def _is_delivery_day(frequency: str, delivery_day: str, local_now: datetime) -> bool:
    """Today (in user-local TZ) a delivery day for this frequency?"""
    if frequency == "daily":
        return True
    weekday = local_now.weekday()  # Monday = 0
    if frequency == "weekdays":
        return weekday < 5
    if frequency == "weekly":
        try:
            return _WEEKDAYS[weekday] == delivery_day
        except IndexError:
            return False
    return False


# ----------------------------------------------------------------------
# Generation
# ----------------------------------------------------------------------


def _generate_for_user(
    db: Session,
    pipeline,
    vector_store,
    user: User,
) -> Digest | None:
    """
    Run the pipeline for one user, persist the result, and return the
    newly-created Digest row (or None if the user has no preferences).

    Imports from `app.integrations.llm_bridge` are deferred to the call
    site so a failure to import the pipeline (e.g. missing dependency)
    doesn't break the rest of the backend on app boot.

    Defensive embedding (L3 audit): we explicitly call
    `vector_store.index_articles` before `persist_digest`. The pipeline
    may or may not call it internally depending on its execution path;
    calling it here is idempotent and guarantees the `articles.embedding`
    column is populated so chat retrieval finds these articles later.
    """
    from app.integrations.llm_bridge import persist_digest, user_to_profile

    if user.preferences is None:
        log.info("digest_worker: user %s has no preferences; skipping", user.id)
        return None

    profile = user_to_profile(user, user.preferences)
    newsletter = asyncio.run(pipeline.run_for_user(profile))

    # Ensure articles have embeddings before persisting digest items that
    # reference them. Index by URL match — re-indexing existing articles
    # is a cheap no-op (upsert with same value).
    pipeline_articles = [entry.article for entry in newsletter.articles]
    if pipeline_articles:
        try:
            vector_store.index_articles(pipeline_articles)
        except Exception:
            # Don't kill digest generation if embedding fails — the digest
            # still works, chat retrieval just won't find these articles.
            log.exception("digest_worker: embedding pass failed for user %s", user.id)

    return persist_digest(db, user, newsletter, fallback_source_id=_PIPELINE_SOURCE_ID)


def _deliver_email(user: User, digest: Digest) -> bool:
    """
    Render the digest as HTML and send via ACS. Returns True on
    accepted send; stamps `digest.sent_at` so it's not retried.

    Opens its own DB session because the worker's session has already
    been committed and closed for this iteration.
    """
    if not email.is_configured():
        return False

    with SessionLocal() as send_db:
        # Reload the digest within this session so we can mutate it.
        fresh = send_db.get(Digest, digest.id)
        if fresh is None or fresh.sent_at is not None:
            return False

        items_with_articles: list[tuple[DigestItem, Article]] = []
        for item in fresh.items:
            article = send_db.get(Article, item.article_id)
            if article is not None:
                items_with_articles.append((item, article))

        html = render_html(fresh, items_with_articles)
        subject = render_subject(fresh, len(items_with_articles))

        ok = email.send_digest(to_email=user.email, subject=subject, html=html)
        if ok:
            fresh.sent_at = datetime.now(timezone.utc)
            send_db.commit()
        return ok


# ----------------------------------------------------------------------
# Pipeline lifecycle
# ----------------------------------------------------------------------


def _build_pipeline():
    """
    Instantiate the LLM pipeline + the vector store it shares with the
    backend, both once per worker run. Returns (pipeline, vector_store)
    or None if imports / construction fail.

    The vector store is returned alongside the pipeline so _generate_for_user
    can call `index_articles` defensively after generation — see L3 note
    in that function.
    """
    try:
        bootstrap.ensure_pipeline_importable()
        from src.pipeline import NewsPipeline
        from app.rag.vector_store import ArticleVectorStore
    except ImportError as exc:
        log.warning("digest_worker: pipeline import failed (%s)", exc)
        return None

    try:
        vector_store = ArticleVectorStore(fallback_source_id=_PIPELINE_SOURCE_ID)
        return NewsPipeline(vector_store=vector_store), vector_store
    except Exception:
        log.exception("digest_worker: pipeline construction failed")
        return None


def _ensure_pipeline_source(db: Session) -> None:
    """Idempotently insert the fallback Source row used when we can't match a publisher."""
    if db.get(Source, _PIPELINE_SOURCE_ID) is not None:
        return
    db.add(
        Source(
            id=_PIPELINE_SOURCE_ID,
            name=_PIPELINE_SOURCE_NAME,
            license="rss-snippet-only",
            source_type="aggregator",
        )
    )
    db.commit()


