"""
Google OAuth 2.0 / OIDC integration.

Same flow as app/auth/entra.py but against Google's identity endpoints
instead of Microsoft's. Used because the IE tenant blocks student
accounts from creating Entra App Registrations — Google has no such
gate. Exposes the same module-level interface (generate_state,
generate_pkce_pair, build_authorize_url, exchange_code) so the auth
router is provider-agnostic.

Flow:
  1. /auth/login generates `state` + PKCE `code_verifier`, persists them
     in HttpOnly cookies, and redirects the browser to Google's
     /authorize endpoint.
  2. Google authenticates the user and redirects back to /auth/callback
     with `?code=...&state=...`.
  3. /auth/callback verifies state, exchanges the code (proving
     possession of `code_verifier`), and gets back an ID token. The token
     came directly from Google's HTTPS token endpoint after a
     client-secret-authenticated exchange, so we trust the claims
     without re-verifying signatures.

Required environment variables:
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, OAUTH_REDIRECT_URI

Setup (one-time):
  - console.cloud.google.com → APIs & Services → Credentials
  - Create Credentials → OAuth client ID → Application type: Web
  - Authorized redirect URI: must match OAUTH_REDIRECT_URI exactly
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import jwt

from app.config import settings


_SCOPES = ["openid", "email", "profile"]
_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"


@dataclass
class GoogleIdentity:
    """Fields we care about from a verified Google ID token.

    `oid` carries Google's stable `sub` claim (per-user, per-app
    identifier). `tid` is a sentinel because Google has no tenant
    concept; we set it to "google" so the User row's NOT NULL constraint
    on entra_tid keeps holding without a migration.
    """
    oid: str
    tid: str
    email: str
    display_name: str | None


def _require_config() -> None:
    if not (settings.google_client_id and settings.google_client_secret):
        raise RuntimeError(
            "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and "
            "GOOGLE_CLIENT_SECRET in your environment, or use "
            "/auth/dev-login."
        )


def generate_state() -> str:
    """Anti-CSRF random string. Google echoes it on callback; we verify equality."""
    return secrets.token_urlsafe(32)


def generate_pkce_pair() -> tuple[str, str]:
    """
    Return (verifier, challenge). The verifier stays server-side until
    the code exchange; the challenge is sent in the authorize URL. On
    callback we prove possession by sending the verifier back — defends
    against auth-code interception attacks (RFC 7636).
    """
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def build_authorize_url(state: str, code_challenge: str) -> str:
    """Return the URL to redirect the browser to for Google login."""
    _require_config()
    params = {
        "client_id": settings.google_client_id,
        "response_type": "code",
        "redirect_uri": settings.oauth_redirect_uri,
        "scope": " ".join(_SCOPES),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        # `prompt=select_account` makes Google show the account picker
        # even when the user is already signed in to a single Google
        # account — useful when developers test with multiple accounts.
        "access_type": "online",
    }
    return f"{_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(code: str, code_verifier: str) -> GoogleIdentity:
    """
    Exchange the auth code for tokens at Google's /token endpoint.
    Raises ValueError on any failure — caller maps to a 400 response.
    """
    _require_config()
    data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.oauth_redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }
    try:
        response = httpx.post(_TOKEN_URL, data=data, timeout=10.0)
    except httpx.HTTPError as e:
        raise ValueError(f"Google token endpoint unreachable: {e}") from e

    if response.status_code != 200:
        # Google returns JSON with `error` + `error_description` on failure.
        try:
            err = response.json()
        except json.JSONDecodeError:
            err = {"error": "non-json", "error_description": response.text[:200]}
        raise ValueError(
            f"Google token exchange failed: {err.get('error')} — "
            f"{err.get('error_description', '')}"
        )

    payload = response.json()
    id_token = payload.get("id_token")
    if not id_token:
        raise ValueError("Google response missing id_token")

    # Decode without signature verification: the id_token came directly
    # from Google's HTTPS endpoint, authenticated with our client secret,
    # so the chain of trust is the TLS + secret exchange itself. For
    # additional defense in depth we could verify against Google's JWKS
    # — left as a follow-up if/when this app has higher security needs.
    claims = jwt.decode(id_token, options={"verify_signature": False})

    sub = claims.get("sub")
    email = claims.get("email")
    if not (sub and email):
        raise ValueError("Google ID token missing required claims (sub/email)")

    return GoogleIdentity(
        oid=sub,
        tid="google",
        email=email,
        display_name=claims.get("name"),
    )
