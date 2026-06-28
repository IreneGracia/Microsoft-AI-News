"""
Email delivery via Azure Communication Services (ACS).

Configuration (backend/.env):
  ACS_CONNECTION_STRING — primary connection string from the
      Microsoft.Communication/communicationServices resource.
      Retrieve with `az communication list-key`.
  ACS_SENDER_ADDRESS   — full from-address, e.g.
      DoNotReply@<random>.azurecomm.net for the Azure Managed Domain.

Failure handling: a missing connection string, a misconfigured sender,
or an ACS API error is logged and returns False — the worker keeps going
for other users instead of crashing the whole run. Email is never a hard
dependency for digest generation.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings

log = logging.getLogger(__name__)


def is_configured() -> bool:
    """True if ACS will accept a send. Worker checks this before rendering."""
    return bool(settings.acs_connection_string and settings.acs_sender_address)


def send_digest(
    *,
    to_email: str,
    subject: str,
    html: str,
) -> bool:
    """
    Send one transactional email via ACS. Returns True on success,
    False on any failure. Never raises.
    """
    if not is_configured():
        log.info(
            "email.send_digest: ACS_CONNECTION_STRING or ACS_SENDER_ADDRESS "
            "missing — skipping send to %s",
            to_email,
        )
        return False

    try:
        from azure.communication.email import EmailClient
    except ImportError:
        log.error(
            "email.send_digest: `azure-communication-email` not installed; "
            "add it to requirements.txt",
        )
        return False

    try:
        client = EmailClient.from_connection_string(settings.acs_connection_string)
    except Exception as exc:
        log.warning("email.send_digest: ACS client init failed: %s", exc)
        return False

    message: dict[str, Any] = {
        "senderAddress": settings.acs_sender_address,
        "recipients": {
            "to": [{"address": to_email}],
        },
        "content": {
            "subject": subject,
            "html": html,
        },
    }

    try:
        poller = client.begin_send(message)
        result = poller.result()
    except Exception as exc:
        log.warning("email.send_digest: ACS send failed for %s: %s", to_email, exc)
        return False

    status = result.get("status") if isinstance(result, dict) else getattr(result, "status", None)
    msg_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)

    if status != "Succeeded":
        log.warning(
            "email.send_digest: ACS send returned status=%s to=%s", status, to_email
        )
        return False

    log.info("email.send_digest: sent id=%s to=%s", msg_id, to_email)
    return True
