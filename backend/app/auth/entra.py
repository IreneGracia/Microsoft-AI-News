"""
Microsoft Entra ID (OAuth 2.0 / OIDC) integration via MSAL.

Flow:
  1. /auth/login generates `state` + PKCE `code_verifier`, persists them in
     HttpOnly cookies, and redirects the browser to Entra's /authorize.
  2. Entra authenticates the user and redirects back to /auth/callback
     with `?code=...&state=...`.
  3. /auth/callback verifies state, exchanges the code (proving possession
     of `code_verifier`), and gets back an ID token containing the user's
     identity. MSAL validates the token signature, issuer, audience, and
     expiry automatically against Entra's published JWKS.

Required environment variables (see .env.example):
  ENTRA_TENANT_ID, ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET, ENTRA_REDIRECT_URI

The tenant can be a free standalone Entra ID tenant created from
entra.microsoft.com — no Azure subscription or credit card needed.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from functools import lru_cache

import msal

from app.config import settings


# OIDC scopes — `openid` triggers the id_token; `email` and `profile`
# add the claims we use to provision the User row.
_SCOPES = ["openid", "email", "profile"]


@dataclass
class EntraIdentity:
    """Fields we care about from a verified Entra ID token."""
    oid: str           # stable per-user object ID
    tid: str           # tenant ID (must match Microsoft tenant)
    email: str         # from preferred_username claim
    display_name: str | None


@lru_cache(maxsize=1)
def _client() -> msal.ConfidentialClientApplication:
    """Build the MSAL client once and reuse — it has internal token caches."""
    if not (settings.entra_tenant_id and settings.entra_client_id and settings.entra_client_secret):
        raise RuntimeError(
            "Entra is not configured. Set ENTRA_TENANT_ID, ENTRA_CLIENT_ID, "
            "and ENTRA_CLIENT_SECRET in your .env, or use /auth/dev-login."
        )
    return msal.ConfidentialClientApplication(
        client_id=settings.entra_client_id,
        client_credential=settings.entra_client_secret,
        authority=f"https://login.microsoftonline.com/{settings.entra_tenant_id}",
    )


def generate_state() -> str:
    """Anti-CSRF random string. Entra echoes it on callback; we verify equality."""
    return secrets.token_urlsafe(32)


def generate_pkce_pair() -> tuple[str, str]:
    """
    Return (verifier, challenge). The verifier stays server-side until the
    code exchange; the challenge is sent in the authorize URL. On callback we
    prove possession by sending the verifier back — defends against
    auth-code interception attacks (RFC 7636).
    """
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def build_authorize_url(state: str, code_challenge: str) -> str:
    """Return the URL to redirect the browser to for Entra login."""
    return _client().get_authorization_request_url(
        scopes=_SCOPES,
        redirect_uri=settings.entra_redirect_uri,
        state=state,
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )


def exchange_code(code: str, code_verifier: str) -> EntraIdentity:
    """
    Exchange the auth code for tokens at Entra's /token endpoint.
    MSAL validates the id_token signature against Entra's JWKS automatically.
    Raises ValueError on any failure — caller maps to a 400 response.
    """
    result = _client().acquire_token_by_authorization_code(
        code=code,
        scopes=_SCOPES,
        redirect_uri=settings.entra_redirect_uri,
        code_verifier=code_verifier,
    )

    if "error" in result:
        raise ValueError(
            f"Entra token exchange failed: {result.get('error')} — "
            f"{result.get('error_description', '')}"
        )

    claims = result.get("id_token_claims") or {}
    oid = claims.get("oid")
    tid = claims.get("tid")
    email = claims.get("preferred_username") or claims.get("email")
    if not (oid and tid and email):
        raise ValueError("Entra ID token missing required claims (oid/tid/email)")

    return EntraIdentity(
        oid=oid,
        tid=tid,
        email=email,
        display_name=claims.get("name"),
    )
