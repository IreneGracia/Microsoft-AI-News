"""
/topics — taxonomy chip list (docs/api.md §3.3).

Read-only, bearer-required, cacheable. The taxonomy itself is seeded at
startup by app.seed; this endpoint just hands it back.
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.deps import current_user, get_db
from app.models import Topic, User
from app.schemas.content import TopicOut

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("", response_model=list[TopicOut])
def list_topics(
    response: Response,
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[Topic]:
    """Return the full taxonomy. Cache for 24h per docs/api.md §3.3."""
    response.headers["Cache-Control"] = "private, max-age=86400"
    return db.query(Topic).order_by(Topic.slug).all()
