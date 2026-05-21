"""
FastAPI dependencies — reusable building blocks injected into route handlers.

Use these in route signatures, like:

    @router.get("/me")
    def get_me(user: User = Depends(current_user)) -> UserOut:
        ...

FastAPI resolves the dependency for each request, handling DB session lifecycle
and auth checks automatically.
"""

from collections.abc import Iterator

import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth.jwt import decode as decode_jwt
from app.db.session import SessionLocal
from app.errors import problem
from app.models import User


def get_db() -> Iterator[Session]:
    """
    Yield a SQLAlchemy session for the duration of a request.

    The `try/finally` guarantees the connection is returned to the pool
    even if the handler raises.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """
    Resolve the calling user from `Authorization: Bearer <jwt>`.

    Returns the loaded User row. Raises 401 (RFC 7807) on any failure
    without leaking detail — docs/auth.md §5.
    """
    auth_header = request.headers.get("Authorization", "")

    # Expect exactly "Bearer <token>". Anything else → 401.
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise problem(status=401, title="Missing or malformed Authorization header")

    token = parts[1]

    try:
        claims = decode_jwt(token)
    except jwt.PyJWTError:
        # Any JWT error → generic 401. Don't say "expired" vs "bad signature".
        raise problem(status=401, title="Invalid token")

    user_id = claims.get("sub")
    if not user_id:
        raise problem(status=401, title="Invalid token")

    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise problem(status=401, title="Invalid token")

    return user
