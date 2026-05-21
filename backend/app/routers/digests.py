"""
/me/digests/* — past-digest read API + feedback (docs/api.md §3.4).

Implements F8 (read-in-app) and F10 (feedback) from
docs/personas_and_features.md §3.

This router is read-only on digests themselves — writes happen from the
digest worker (D1) via direct DB access, not the public API.
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.deps import current_user, get_db
from app.errors import problem
from app.models import Article, Digest, DigestItem, Feedback, User
from app.pagination import Page, PageInfo, decode_cursor, encode_cursor
from app.schemas.content import Citation
from app.schemas.digest import (
    Digest as DigestSchema,
    DigestItemOut,
    DigestSummary,
    FeedbackIn,
)

router = APIRouter(prefix="/me/digests", tags=["digests"])


def _resolve_citations(db: Session, article_ids: list[str]) -> list[Citation]:
    """
    Load Article rows for a list of IDs and convert to Citation shape.

    We splice URL + source server-side rather than trusting whatever the
    LLM emitted — see architecture.md §6.
    """
    if not article_ids:
        return []
    rows = (
        db.query(Article)
        .filter(Article.id.in_(article_ids))
        .all()
    )
    by_id = {a.id: a for a in rows}
    out: list[Citation] = []
    # Preserve the order the LLM produced.
    for aid in article_ids:
        a = by_id.get(aid)
        if a is None:
            # Skip missing citations rather than 500 — an article could be
            # purged for compliance reasons after the digest was generated.
            continue
        out.append(
            Citation(
                article_id=a.id,
                title=a.title,
                source=a.source.name if a.source else "",
                url=a.url,
                published_at=a.published_at,
            )
        )
    return out


def _items_to_out(db: Session, items: list[DigestItem]) -> list[DigestItemOut]:
    """Resolve each item's primary article + citation list."""
    article_ids = {i.article_id for i in items}
    for i in items:
        article_ids.update(i.citation_ids())
    articles = {
        a.id: a
        for a in db.query(Article).filter(Article.id.in_(article_ids)).all()
    }
    out: list[DigestItemOut] = []
    for item in items:
        primary = articles.get(item.article_id)
        if primary is None:
            continue  # primary article gone — skip the item rather than 500
        citation_objs = _resolve_citations(db, item.citation_ids())
        out.append(
            DigestItemOut(
                article_id=item.article_id,
                rank=item.rank,
                title=primary.title,
                summary=item.summary,
                tone=item.tone,
                length=item.length,
                citations=citation_objs,
            )
        )
    return out


@router.get("", response_model=Page[DigestSummary])
def list_digests(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> Page[DigestSummary]:
    """
    List past digests for the caller, newest first.

    Cursor pagination: cursor encodes the last seen digest ID; we paginate
    by `(generated_at DESC, id DESC)` but since ULID-ish IDs are roughly
    sortable, the cursor on `id` is good enough at MVP.
    """
    after_id = decode_cursor(cursor)

    q = (
        db.query(
            Digest.id,
            Digest.generated_at,
            func.count(DigestItem.id).label("item_count"),
        )
        .outerjoin(DigestItem, DigestItem.digest_id == Digest.id)
        .filter(Digest.user_id == user.id)
        .group_by(Digest.id)
        .order_by(desc(Digest.generated_at), desc(Digest.id))
    )

    if after_id:
        # Find the cursor row's `generated_at` so we can resume strictly past it.
        anchor = db.query(Digest.generated_at).filter(Digest.id == after_id).first()
        if anchor is not None:
            q = q.filter(
                (Digest.generated_at < anchor[0])
                | ((Digest.generated_at == anchor[0]) & (Digest.id < after_id))
            )

    rows = q.limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    data = [
        DigestSummary(id=r.id, generated_at=r.generated_at, item_count=r.item_count or 0)
        for r in rows
    ]
    next_cursor = encode_cursor(rows[-1].id) if has_more and rows else None
    return Page(data=data, page=PageInfo(next_cursor=next_cursor, limit=limit))


@router.get("/{digest_id}")
def get_digest(
    digest_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    format: Literal["json", "html"] = Query(default="json"),
):
    """
    Full digest payload — JSON by default, HTML when `?format=html`.

    The HTML branch returns a minimal render so frontend has a fallback
    while Backend Dev 2 wires the proper email template into Blob.
    """
    digest = db.get(Digest, digest_id)
    if digest is None or digest.user_id != user.id:
        # 404 (not 403) on cross-user access — don't leak existence.
        raise problem(status=404, title="Digest not found")

    items = _items_to_out(db, list(digest.items))

    if format == "html":
        return HTMLResponse(content=_render_digest_html(digest, items))

    return DigestSchema(id=digest.id, generated_at=digest.generated_at, items=items)


def _render_digest_html(digest: Digest, items: list[DigestItemOut]) -> str:
    """
    Minimal HTML render. Real templating lives with Backend Dev 2's
    email renderer (D2). This is enough for the frontend to test the
    "read-in-app" flow without that dependency.
    """
    item_blocks = []
    for it in items:
        cites = "".join(
            f'<li><a href="/api/v1/articles/{c.article_id}/source">{c.title}</a> — {c.source}</li>'
            for c in it.citations
        )
        item_blocks.append(
            f"<article><h2>{it.rank}. {it.title}</h2>"
            f"<p>{it.summary}</p>"
            f"<ul>{cites}</ul></article>"
        )
    return (
        f"<!doctype html><html><head><meta charset=utf-8>"
        f"<title>Digest {digest.id}</title></head><body>"
        f"<h1>Digest — {digest.generated_at.isoformat()}</h1>"
        f"{''.join(item_blocks)}"
        f"</body></html>"
    )


@router.post("/{digest_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
def post_feedback(
    digest_id: str,
    body: FeedbackIn,
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    """
    Record a thumbs up/down on one item.

    Idempotent on `(user, digest, article)`: a second POST overwrites the
    previous signal. Returns 204 — frontend already has the value it sent.
    """
    digest = db.get(Digest, digest_id)
    if digest is None or digest.user_id != user.id:
        raise problem(status=404, title="Digest not found")

    # Confirm the article appears in this digest, so we can't be tricked
    # into recording feedback against an article from someone else's digest.
    item_match = (
        db.query(DigestItem.id)
        .filter(DigestItem.digest_id == digest_id, DigestItem.article_id == body.article_id)
        .first()
    )
    if item_match is None:
        raise problem(
            status=422,
            title="Article not in digest",
            detail=f"article_id {body.article_id} is not part of digest {digest_id}",
        )

    existing = (
        db.query(Feedback)
        .filter(
            Feedback.user_id == user.id,
            Feedback.digest_id == digest_id,
            Feedback.article_id == body.article_id,
        )
        .first()
    )
    if existing is not None:
        existing.signal = body.signal
        existing.created_at = datetime.utcnow()
    else:
        db.add(
            Feedback(
                user_id=user.id,
                digest_id=digest_id,
                article_id=body.article_id,
                signal=body.signal,
            )
        )
    db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
