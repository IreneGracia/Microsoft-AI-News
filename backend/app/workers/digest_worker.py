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
       a. Load preferences (topics, sources, regions, role, tone, length).
       b. Pull recent articles matching their tag preferences.
       c. Rank — relevance × recency × tag overlap × source quality.
       d. Summarise top N with the LLM in their tone + length.
       e. Resolve citations to source articles.
       f. Write Digest + DigestItem rows.
       g. Send (or skip — F8 serves the same content via the API).

Currently a scaffold: `run()` is wired up so the webhook can call it,
but the generation steps raise NotImplementedError until the LLM
provider and ranking algorithm are decided.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import User

log = logging.getLogger(__name__)


def run() -> dict:
    """
    Entry point called by the internal webhook.
    Generate today's digests for all eligible users.
    Returns a small summary the webhook echoes back.
    Safe to call repeatedly while the generation steps are stubbed.
    """
    with SessionLocal() as db:
        eligible = _find_eligible_users(db)
        log.info("digest_worker: eligible users today: %d", len(eligible))

        generated = 0
        for user in eligible:
            try:
                _generate_for_user(db, user)
                generated += 1
            except NotImplementedError:
                # Expected while generation is stubbed; log and move on.
                log.info("digest_worker: generation stubbed for user %s", user.id)

    return {"eligible_users": len(eligible), "generated": generated}


def _find_eligible_users(db: Session) -> list[User]:
    """
    Pick users whose preferences make today a delivery day, excluding any
    who already have a Digest row for today (idempotency lock).

    Returns [] today — the scheduling predicate will be implemented when
    timezone handling and the digest-status field land.
    """
    return []


def _generate_for_user(db: Session, user: User) -> None:
    """
    Steps 2a–2g of the flow. Raises NotImplementedError until the LLM
    provider (Phi-3 / Gemini / etc.) and ranking algorithm are chosen.
    """
    raise NotImplementedError(
        "digest generation pending — pick LLM provider and ranking algorithm; "
        "see F3 in docs/feature_endpoints.md."
    )
