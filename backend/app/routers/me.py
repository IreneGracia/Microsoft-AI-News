"""
/me endpoints — profile + preferences.

Implements docs/api.md §3.2. Everything here requires a valid bearer token;
that's enforced via the `current_user` dependency injected on each route.
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.deps import current_user, get_db
from app.models import Preferences, User
from app.schemas.user import PreferencesIn, PreferencesOut, UserOut

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserOut)
def get_me(user: User = Depends(current_user)) -> User:
    """Return the caller's profile. The bearer-token middleware loaded `user`."""
    # FastAPI converts the SQLAlchemy `User` to `UserOut` via `from_attributes`.
    return user


@router.get("/preferences", response_model=PreferencesOut)
def get_preferences(user: User = Depends(current_user)) -> PreferencesOut:
    """Return the caller's newsletter preferences."""
    p = user.preferences
    return PreferencesOut(
        topics=json.loads(p.topics_json),
        muted_sources=json.loads(p.muted_sources_json),
        frequency=p.frequency,
        delivery_day=p.delivery_day,
        delivery_hour_local=p.delivery_hour_local,
        length=p.length,
        tone=p.tone,
        language=p.language,
    )


@router.put("/preferences", response_model=PreferencesOut)
def put_preferences(
    body: PreferencesIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> PreferencesOut:
    """
    Replace the caller's preferences.

    PUT (not PATCH) — body is the full new state. Enum values are validated
    by Pydantic before this handler runs, so we can trust the input.
    """
    p: Preferences = user.preferences
    p.topics_json = json.dumps(body.topics)
    p.muted_sources_json = json.dumps(body.muted_sources)
    p.frequency = body.frequency
    p.delivery_day = body.delivery_day
    p.delivery_hour_local = body.delivery_hour_local
    p.length = body.length
    p.tone = body.tone
    p.language = body.language
    db.commit()
    return body  # the same shape — echo back


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_me(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    """
    GDPR account delete.

    Soft-delete only — sets `deleted_at = NOW`. A scheduled job hard-deletes
    the row 24h later, at which point the DB-level CASCADEs on
    preferences/chat_sessions/digests/feedback fire. See docs/auth.md §9 for
    the full lifecycle and the rationale for the 24h reversal window.

    `current_user` rejects soft-deleted users on the next request, so the
    bearer token is effectively dead immediately.
    """
    if user.deleted_at is None:
        user.deleted_at = datetime.now(timezone.utc)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
