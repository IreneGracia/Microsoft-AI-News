"""
Mint + validate our own session JWT.

This is the bearer token the SPA sends back on every authenticated request.
NOT the Entra access token — see docs/auth.md §3 for why we swap them.

Token claims (kept minimal — docs/auth.md §4):

    {
      "iss": "tech-intel-news",
      "sub": "usr_<uuid>",           # our internal user_id
      "aud": "tech-intel-news-api",
      "iat": <unix epoch>,
      "exp": <unix epoch>,
      "ver": 1
    }

No email, no name — those are fetched via GET /me, keeping PII out of any
logs that capture bearer tokens.
"""

from datetime import datetime, timedelta, timezone

import jwt  # the `pyjwt` library, imported as `jwt`

from app.config import settings


# Bumped when claim shape changes. Validator rejects unknown versions.
CURRENT_VERSION = 1


def mint(user_id: str) -> tuple[str, int]:
    """
    Create a new JWT for `user_id`. Returns (token, expires_in_seconds).

    Caller is responsible for setting it in the response — see
    app/routers/auth.py.
    """
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.jwt_ttl_minutes)

    payload = {
        "iss": settings.jwt_issuer,
        "sub": user_id,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "ver": CURRENT_VERSION,
    }

    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    expires_in = settings.jwt_ttl_minutes * 60
    return token, expires_in


def decode(token: str) -> dict:
    """
    Validate a JWT and return its claims.

    Raises `jwt.PyJWTError` (or subclass) on any failure: bad signature,
    expired, wrong issuer/audience, unknown version. The middleware in
    app/deps.py converts those into 401 responses without leaking detail
    (docs/auth.md §5 — avoid token-oracle attacks).
    """
    claims = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
    )

    if claims.get("ver") != CURRENT_VERSION:
        # Treat unsupported versions like any other invalid token.
        raise jwt.InvalidTokenError("unsupported token version")

    return claims
