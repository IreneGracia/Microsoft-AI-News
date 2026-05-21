"""
Cursor pagination helper.

docs/api.md §5 specifies opaque base64 cursors for unbounded lists. We keep
the implementation deliberately simple: cursor = base64(JSON({"after": <id>})).
That makes it trivial to decode in tests and impossible to invent client-side
unless you know the schema.

Usage in a router:

    from app.pagination import decode_cursor, encode_cursor, Page

    after_id = decode_cursor(cursor)
    q = db.query(Model).order_by(Model.id)
    if after_id:
        q = q.filter(Model.id > after_id)
    rows = q.limit(limit + 1).all()
    next_cursor = encode_cursor(rows[-1].id) if len(rows) > limit else None
    return Page(data=rows[:limit], next_cursor=next_cursor, limit=limit)
"""

import base64
import json
from typing import Generic, TypeVar

from pydantic import BaseModel


T = TypeVar("T")


class PageInfo(BaseModel):
    """`page` field on every paginated response — RFC-like envelope."""

    next_cursor: str | None
    limit: int


class Page(BaseModel, Generic[T]):
    """Standard list response: `{data: [...], page: {...}}`."""

    data: list[T]
    page: PageInfo


def encode_cursor(after_id: str) -> str:
    """Pack an opaque cursor pointing *past* the given row ID."""
    raw = json.dumps({"after": after_id}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> str | None:
    """
    Unpack a cursor back into the `after_id` it represents.

    Returns None for a missing/malformed cursor (callers treat that as
    "start from the beginning"). We deliberately don't 400 on a bad cursor
    — it can happen on a stale tab and shouldn't show the user an error.
    """
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        after = payload.get("after")
        return after if isinstance(after, str) else None
    except (ValueError, TypeError):
        return None
