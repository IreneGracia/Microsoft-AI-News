"""
Email delivery via Azure Communication Services (ACS).

Switched from Resend to keep the whole stack on Azure for the IE student
subscription deploy — one bill, one dashboard, one Bicep file.

Configuration:
  ACS_CONNECTION_STRING — primary connection string from the
      Microsoft.Communication/communicationServices resource. Retrieve
      with `az communication list-key`.
  ACS_SENDER_ADDRESS    — full from-address, e.g.
      DoNotReply@<random>.azurecomm.net for the Azure Managed Domain.
      The "DoNotReply" local-part is required for Azure-managed domains;
      custom domains can use anything.

Failure handling: a missing connection string, a misconfigured sender,
or an ACS API error is logged and returns False — the worker keeps going
for other users instead of crashing the whole run. Don't let email be a
hard dependency for digest generation.
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
    Send one transactional email. Returns True on accepted send, False on any
    failure. Never raises — the caller's only job is to react to True/False.

    `to_email` is the user's primary email; `subject` is the user-facing
    subject line; `html` is the fully rendered digest body.
    """
    if not is_configured():
        log.info(
            "email.send_digest: ACS_CONNECTION_STRING or ACS_SENDER_ADDRESS "
            "missing — skipping send to %s",
            to_email,
        )
        return False

    try:
        # Import lazily so the absence of azure-communication-email only
        # matters when sending, not at every import of the worker.
        from azure.communication.email import EmailClient  # type: ignore[import-not-found]
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
        # begin_send returns a long-running-operation poller. We block on
        # the result so the caller sees True/False per send; ACS sends are
        # fast enough (sub-second typical) that this is fine for the
        # digest worker's serial loop.
        poller = client.begin_send(message)
        result = poller.result()
    except Exception as exc:
        # Catch broad — ACS errors come in several shapes (auth,
        # validation, throttling). We want one uniform failure path.
        log.warning(
            "email.send_digest: ACS send failed for %s: %s", to_email, exc
        )
        return False

    # ACS returns {"id": "...", "status": "Succeeded"} on success.
    status = result.get("status") if isinstance(result, dict) else getattr(result, "status", None)
    msg_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)

    if status != "Succeeded":
        log.warning(
            "email.send_digest: ACS send returned status=%s to=%s", status, to_email
        )
        return False

    log.info("email.send_digest: sent id=%s to=%s", msg_id, to_email)
    return True
