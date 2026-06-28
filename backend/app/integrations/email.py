"""
Email delivery via Gmail SMTP + App Password.

Configuration (in backend/.env):
  GMAIL_SENDER       — your full Gmail address, e.g. you@gmail.com
  GMAIL_APP_PASSWORD — 16-char App Password from
                       myaccount.google.com → Security → App Passwords
                       (requires 2-Step Verification to be enabled)

Failure handling: missing credentials or SMTP errors are logged and
return False — the worker keeps going for other users instead of
crashing the whole run.
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

log = logging.getLogger(__name__)

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 465


def is_configured() -> bool:
    """True if Gmail credentials are present and the worker can send."""
    return bool(settings.gmail_sender and settings.gmail_app_password)


def send_digest(
    *,
    to_email: str,
    subject: str,
    html: str,
) -> bool:
    """
    Send one transactional email via Gmail SMTP SSL.
    Returns True on success, False on any failure. Never raises.
    """
    if not is_configured():
        log.info(
            "email.send_digest: GMAIL_SENDER or GMAIL_APP_PASSWORD missing "
            "— skipping send to %s",
            to_email,
        )
        return False

    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = f"MAI News <{settings.gmail_sender}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT) as server:
            server.login(settings.gmail_sender, settings.gmail_app_password)
            server.send_message(msg)
        log.info("email.send_digest: sent to %s", to_email)
        return True
    except smtplib.SMTPAuthenticationError:
        log.error(
            "email.send_digest: Gmail auth failed — check GMAIL_APP_PASSWORD "
            "(must be a 16-char App Password, not your account password)"
        )
        return False
    except Exception as exc:
        log.warning("email.send_digest: SMTP error sending to %s: %s", to_email, exc)
        return False
