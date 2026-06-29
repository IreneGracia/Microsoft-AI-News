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
from app.errors import problem
from app.models import Preferences, Source, Tag, User
from app.schemas.user import PreferencesIn, PreferencesOut, UserOut

router = APIRouter(prefix="/me", tags=["me"])


def _validate_preferences(db: Session, body: PreferencesIn) -> None:
    """
    Reject any tag slug not in the taxonomy or source id not in the registry.

    Each preference list is checked against the matching `Tag` dimension;
    `muted_sources` is checked against the `Source` registry. Raises a 422
    listing the offending values — nothing is written if validation fails.
    """
    # Preference field -> taxonomy dimension.
    by_dimension = {
        "topic": body.topics,
        "business": body.business_tags,
        "regulation_policy": body.regulation_tags,
        "regional": body.regions,
    }
    for dimension, slugs in by_dimension.items():
        if not slugs:
            continue
        valid = {
            s for (s,) in db.query(Tag.slug).filter(Tag.dimension == dimension).all()
        }
        unknown = [s for s in slugs if s not in valid]
        if unknown:
            raise problem(
                status=422,
                title="Unknown tag",
                detail=f"{dimension} tags not in taxonomy: {', '.join(unknown)}",
            )

    if body.role is not None:
        valid_roles = {
            s for (s,) in db.query(Tag.slug).filter(Tag.dimension == "role").all()
        }
        if body.role not in valid_roles:
            raise problem(
                status=422,
                title="Unknown role",
                detail=f"role '{body.role}' is not in the taxonomy",
            )

    if body.muted_sources:
        valid_sources = {s for (s,) in db.query(Source.id).all()}
        unknown = [s for s in body.muted_sources if s not in valid_sources]
        if unknown:
            raise problem(
                status=422,
                title="Unknown source",
                detail=f"source ids not in registry: {', '.join(unknown)}",
            )


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
        business_tags=json.loads(p.business_tags_json),
        regulation_tags=json.loads(p.regulation_tags_json),
        regions=json.loads(p.regions_json),
        role=p.role,
        muted_sources=json.loads(p.muted_sources_json),
        frequency=p.frequency,
        delivery_day=p.delivery_day,
        delivery_hour_local=p.delivery_hour_local,
        length=p.length,
        tone=p.tone,
        language=p.language,
        timezone=p.timezone,
        newsletter_consent=bool(p.newsletter_consent),
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
    by Pydantic before this handler runs; tag slugs and source ids are
    validated against the taxonomy/registry here before anything is written.
    """
    _validate_preferences(db, body)

    p: Preferences = user.preferences
    p.topics_json = json.dumps(body.topics)
    p.business_tags_json = json.dumps(body.business_tags)
    p.regulation_tags_json = json.dumps(body.regulation_tags)
    p.regions_json = json.dumps(body.regions)
    p.role = body.role
    p.muted_sources_json = json.dumps(body.muted_sources)
    p.frequency = body.frequency
    p.delivery_day = body.delivery_day
    p.delivery_hour_local = body.delivery_hour_local
    p.length = body.length
    p.tone = body.tone
    p.language = body.language
    p.timezone = body.timezone
    p.newsletter_consent = body.newsletter_consent
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
