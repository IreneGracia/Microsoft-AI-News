"""
Internal endpoints — /api/v1/internal/*.

Invoked by infrastructure (the GitHub Actions cron in
.github/workflows/digest-cron.yml), not by end users. Auth is via a
shared secret in the Authorization header, not user JWTs.

Hidden from the public OpenAPI doc (`include_in_schema=False`) so the
frontend's generated client doesn't surface them.
"""

import secrets

from fastapi import APIRouter, Header

from app.config import settings
from app.errors import problem
from app.workers import digest_worker

router = APIRouter(prefix="/internal", tags=["internal"], include_in_schema=False)


def _require_worker_secret(authorization: str | None) -> None:
    """Verify the Bearer token matches WORKER_SHARED_SECRET (constant-time)."""
    if not settings.worker_shared_secret:
        # Closed by default: if the secret isn't configured, refuse all calls.
        raise problem(status=503, title="Internal endpoints not configured")

    expected = f"Bearer {settings.worker_shared_secret}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise problem(status=403, title="Forbidden")


@router.post("/run-digest-worker")
def run_digest_worker(authorization: str | None = Header(default=None)) -> dict:
    """
    Trigger one run of the digest worker.

    Called daily by .github/workflows/digest-cron.yml. Safe to invoke
    manually too — the worker is idempotent (won't double-generate for
    users who already have a digest for today).
    """
    _require_worker_secret(authorization)
    result = digest_worker.run()
    return {"status": "ok", **result}
