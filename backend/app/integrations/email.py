"""
Email delivery via Resend (https://resend.com).

Configuration (backend/.env):
  RESEND_API_KEY  — API key from resend.com dashboard
  RESEND_FROM     — verified sender address, e.g. "MAI News <digest@yourdomain.com>"
                    Without a verified domain you can only send to your own address
                    using the default onboarding@resend.dev sender.

Failure handling: a missing API key or a Resend API error is logged and
returns False — the worker keeps going for other users instead of crashing
the whole run. Email is never a hard dependency for digest generation.
"""

from __future__ import annotations

import logging

import resend

from app.config import settings

log = logging.getLogger(__name__)


def is_configured() -> bool:
    """True if Resend is ready to send. Worker checks this before rendering."""
    return bool(settings.resend_api_key and settings.resend_from)


def send_digest(
    *,
    to_email: str,
    subject: str,
    html: str,
) -> bool:
    """
    Send one transactional email via Resend. Returns True on success,
    False on any failure. Never raises.
    """
    if not is_configured():
        log.info(
            "email.send_digest: RESEND_API_KEY or RESEND_FROM not set"
            " — skipping send to %s",
            to_email,
        )
        return False

    resend.api_key = settings.resend_api_key

    try:
        params: resend.Emails.SendParams = {
            "from": settings.resend_from,
            "to": [to_email],
            "subject": subject,
            "html": html,
        }
        response = resend.Emails.send(params)
    except Exception as exc:
        log.warning("email.send_digest: Resend API error for %s: %s", to_email, exc)
        return False

    msg_id = response.get("id") if isinstance(response, dict) else getattr(response, "id", None)
    if not msg_id:
        log.warning("email.send_digest: Resend returned no id for %s", to_email)
        return False

    log.info("email.send_digest: sent id=%s to=%s", msg_id, to_email)
    return True
