"""
Auth endpoints — /api/v1/auth/*.

OAuth (Google + Microsoft):
  - /login?provider=google|microsoft  → start the OAuth flow (302 to provider).
  - /callback                         → exchange the code, provision the user,
                                        redirect to the frontend with our JWT
                                        in the URL fragment.

Magic link (email-based, any provider):
  - /email/request-login  → POST {email}. Sends a one-time login link via
                            ACS Email. Always returns 200 to avoid
                            disclosing whether the email exists.
  - /email/verify         → GET ?token=... The link the user clicks in
                            their inbox. Verifies, provisions, redirects
                            to the frontend like /callback does.

Shared:
  - /logout    → 204; bearer-token auth is stateless, so logout is the
                 frontend forgetting the token.
  - /dev-login → dev-only shortcut: mints a JWT for a fixed test user.

All three flows produce identical session JWTs and provision identical User
rows, so frontend code doesn't have to care which one was used.
"""

import json
import logging
import secrets

from fastapi import APIRouter, Body, Cookie, Depends, Query, Response, status

log = logging.getLogger(__name__)
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.auth import email_link
from app.auth import google as google_oauth
from app.auth import entra as entra_oauth
from app.auth.jwt import mint as mint_jwt
from app.config import settings
from app.deps import get_db
from app.errors import problem
from app.models import User, Preferences
from app.seed import seed_dev_demo

router = APIRouter(prefix="/auth", tags=["auth"])


def _default_preferences() -> Preferences:
    """
    Sensible defaults for new users — pre-selected topics and role so the
    dashboard shows relevant content from day one instead of everything.
    """
    import json
    p = Preferences()
    # Tier 1 topics most relevant to a Microsoft AI/tech team
    p.topics_json = json.dumps([
        "artificial_intelligence_ml",
        "ai_tools_productivity",
        "software_development",
        "cloud_infrastructure",
    ])
    p.business_tags_json = json.dumps(["big_tech_faang_microsoft"])
    p.regions_json = json.dumps(["europe", "north_america"])
    p.role = "for_engineers_technical_depth"
    p.frequency = "daily"
    p.length = "deep"
    p.tone = "technical"
    return p


# Cookies that carry state + PKCE verifier + chosen provider across the OAuth roundtrip.
# HttpOnly so JS can't read them; SameSite=Lax so they're sent back on the
# top-level redirect from accounts.google.com or login.microsoftonline.com.
_STATE_COOKIE = "oauth_state"
_VERIFIER_COOKIE = "oauth_verifier"
_PROVIDER_COOKIE = "oauth_provider"
_OAUTH_COOKIE_MAX_AGE = 600  # 10 min — user has to finish the dance in this window


def _oauth_cookie_kwargs() -> dict:
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": not settings.is_dev,
        "max_age": _OAUTH_COOKIE_MAX_AGE,
        "path": "/api/v1/auth",
    }


# Fixed users we provision in dev so /dev-login and mock OAuth are reproducible.
_DEV_USER = {
    "entra_oid": "00000000-0000-0000-0000-000000000001",
    "entra_tid": "00000000-0000-0000-0000-000000000002",
    "email": "jfernandezsande@student.ie.edu",
    "display_name": "Joaquin Fernandez Sande",
}

_MOCK_MICROSOFT_USER = {
    "entra_oid": "00000000-0000-0000-0000-000000000003",
    "entra_tid": "common",
    "email": "jfernandezsande@student.ie.edu",
    "display_name": "Joaquin Fernandez Sande",
}


@router.get("/login")
def login(provider: str = Query(default="google"), db: Session = Depends(get_db)) -> RedirectResponse:
    """
    Start an OAuth flow. `provider` selects the identity provider:
      - "google"    → Google OAuth (needs GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET)
      - "microsoft" → Microsoft Entra (needs ENTRA_TENANT_ID + ENTRA_CLIENT_ID + ENTRA_CLIENT_SECRET)
                      In dev mode, falls back to a mock Microsoft user if Entra is not configured.
    """
    # Dev-mode mock for Microsoft: skip the real OAuth dance and mint a JWT directly.
    if provider == "microsoft" and settings.is_dev and not settings.entra_client_id:
        return _mock_microsoft_login(db)

    oauth = entra_oauth if provider == "microsoft" else google_oauth

    state = oauth.generate_state()
    verifier, challenge = oauth.generate_pkce_pair()
    try:
        authorize_url = oauth.build_authorize_url(state=state, code_challenge=challenge)
    except RuntimeError as e:
        raise problem(status=503, title="OAuth provider not configured", detail=str(e))

    response = RedirectResponse(url=authorize_url, status_code=302)
    response.set_cookie(_STATE_COOKIE, state, **_oauth_cookie_kwargs())
    response.set_cookie(_VERIFIER_COOKIE, verifier, **_oauth_cookie_kwargs())
    response.set_cookie(_PROVIDER_COOKIE, provider, **_oauth_cookie_kwargs())
    return response


def _mock_microsoft_login(db: Session) -> RedirectResponse:
    """Dev-only: provision a mock Microsoft/Entra user and redirect with a real JWT."""
    user = db.query(User).filter(User.entra_oid == _MOCK_MICROSOFT_USER["entra_oid"]).first()
    if user is None:
        user = User(
            entra_oid=_MOCK_MICROSOFT_USER["entra_oid"],
            entra_tid=_MOCK_MICROSOFT_USER["entra_tid"],
            email=_MOCK_MICROSOFT_USER["email"],
            display_name=_MOCK_MICROSOFT_USER["display_name"],
            preferences=_default_preferences(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        seed_dev_demo(db, user)

    token, _ = mint_jwt(user.id)
    return RedirectResponse(
        url=f"{settings.frontend_url}/#access_token={token}",
        status_code=302,
    )


@router.get("/callback")
def callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    oauth_state: str | None = Cookie(default=None),
    oauth_verifier: str | None = Cookie(default=None),
    oauth_provider: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """
    Shared OAuth redirect target for both Google and Microsoft.
    Reads the `oauth_provider` cookie set by /login to dispatch to the
    correct exchange_code implementation. Verifies state, exchanges code,
    provisions user, mints our JWT, and redirects to the frontend with
    the JWT in the URL fragment (fragments aren't sent to servers, so the
    token stays out of access logs).
    """
    if error:
        raise problem(
            status=400,
            title="OAuth error",
            detail=f"{error}: {error_description or ''}",
        )

    if not code or not state:
        raise problem(status=400, title="Missing code or state")

    if not oauth_state or not oauth_verifier:
        raise problem(
            status=400,
            title="OAuth cookies missing — flow expired or third-party cookies blocked",
        )

    # Constant-time comparison so we don't leak timing on state-mismatch attacks.
    if not secrets.compare_digest(state, oauth_state):
        raise problem(status=400, title="State mismatch — possible CSRF")

    provider = oauth_provider or "google"
    oauth = entra_oauth if provider == "microsoft" else google_oauth

    try:
        identity = oauth.exchange_code(code=code, code_verifier=oauth_verifier)
    except ValueError as e:
        raise problem(status=400, title="Token exchange failed", detail=str(e))

    user = db.query(User).filter(User.entra_oid == identity.oid).first()
    if user is None:
        user = User(
            entra_oid=identity.oid,
            entra_tid=identity.tid,
            email=identity.email,
            display_name=identity.display_name,
            preferences=_default_preferences(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token, _ = mint_jwt(user.id)

    response = RedirectResponse(
        url=f"{settings.frontend_url}/#access_token={token}",
        status_code=302,
    )
    response.delete_cookie(_STATE_COOKIE, path="/api/v1/auth")
    response.delete_cookie(_VERIFIER_COOKIE, path="/api/v1/auth")
    response.delete_cookie(_PROVIDER_COOKIE, path="/api/v1/auth")
    return response


# ─── Magic-link (email) flow ─────────────────────────────────────────


class _EmailRequestIn(BaseModel):
    email: EmailStr


@router.post("/email/request-login", status_code=status.HTTP_200_OK)
def request_login_email(body: _EmailRequestIn) -> dict:
    """
    Send a one-time login link to `email` via ACS.

    Always returns 200 with a generic message — even if the email is
    malformed, ACS is misconfigured, or the send fails. This prevents
    attackers from probing which email addresses are users by timing or
    error-code differences. Send failures are logged server-side.

    In dev mode, the response also contains `dev_link` so the team can
    log in without email delivery configured.
    """
    email = body.email.strip().lower()
    response: dict = {
        "status": "ok",
        "message": (
            "If an account is associated with this address, a sign-in link "
            "has been sent. Check your inbox."
        ),
    }

    if email_link.is_valid_email(email):
        token = email_link.generate_login_token(email)
        login_url = email_link.build_login_url(token)
        email_link.send_login_email(to_email=email, login_url=login_url)

        if settings.is_dev:
            response["dev_link"] = login_url
            log.info("dev magic link for %s → %s", email, login_url)

    return response


@router.get("/email/verify")
def verify_login_email(
    token: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """
    Validate the token from the email, provision the user if new, mint
    a session JWT, and redirect to the frontend — mirrors the OAuth
    /callback contract.
    """
    if not token:
        raise problem(status=400, title="Missing token")

    try:
        identity = email_link.verify_login_token(token)
    except ValueError as e:
        raise problem(status=400, title="Invalid login link", detail=str(e))

    user = db.query(User).filter(User.entra_oid == identity.oid).first()
    if user is None:
        user = User(
            entra_oid=identity.oid,
            entra_tid=identity.tid,
            email=identity.email,
            display_name=identity.display_name,
            preferences=_default_preferences(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    session_token, _ = mint_jwt(user.id)
    return RedirectResponse(
        url=f"{settings.frontend_url}/#access_token={session_token}",
        status_code=302,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> Response:
    """
    Stateless logout: with bearer tokens, logging out is the frontend
    forgetting the token. We return 204 and defensively clear any
    leftover oauth cookies. (A JWT denylist would go here if true
    server-side revocation becomes a requirement.)
    """
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(_STATE_COOKIE, path="/api/v1/auth")
    response.delete_cookie(_VERIFIER_COOKIE, path="/api/v1/auth")
    return response


@router.post("/dev-login")
def dev_login(db: Session = Depends(get_db)) -> dict:
    """
    DEV ONLY. Mints a JWT for a fixed test user. Disabled in production.

    Returns the same shape /callback will return once implemented, so
    frontend code written against this works unchanged later.
    """
    if not settings.is_dev:
        raise problem(status=404, title="Not Found")

    # Find-or-create the dev user.
    user = db.query(User).filter(User.entra_oid == _DEV_USER["entra_oid"]).first()
    if user is None:
        user = User(
            entra_oid=_DEV_USER["entra_oid"],
            entra_tid=_DEV_USER["entra_tid"],
            email=_DEV_USER["email"],
            display_name=_DEV_USER["display_name"],
            preferences=_default_preferences(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Seed demo articles/digest for this dev user so endpoints return
    # something useful out of the box. Idempotent — no-op on repeat calls.
    seed_dev_demo(db, user)

    token, expires_in = mint_jwt(user.id)
    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": expires_in,
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
        },
    }
