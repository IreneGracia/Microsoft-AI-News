"""
Health endpoints.

Two probes (docs/api.md §3.7):
  - /health/live  — liveness: the process is up. Always 200 if the app responds.
  - /health/ready — readiness: deps reachable (DB at MVP; add Redis + AI Search later).

Both are unauthenticated — Azure Container Apps needs to hit them without a token.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.deps import get_db
from app.errors import problem

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict:
    """Process-is-alive probe. Returns immediately."""
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict:
    """
    Dependency probe. Reports unhealthy (503) if DB isn't reachable.
    Expand this as services are added (Redis, AI Search, Azure OpenAI).
    """
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        # Don't leak the error message — just signal "not ready".
        raise problem(status=503, title="Database unavailable")
    return {"status": "ok", "checks": {"db": "ok"}}
