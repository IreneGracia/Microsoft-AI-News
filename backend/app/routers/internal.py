"""
Internal endpoints — /api/v1/internal/*.

Invoked by infrastructure (the GitHub Actions cron in
.github/workflows/digest-cron.yml), not by end users. Auth is via a
shared secret in the Authorization header, not user JWTs.

Hidden from the public OpenAPI doc (`include_in_schema=False`) so the
frontend's generated client doesn't surface them.
"""

import secrets

from fastapi import APIRouter, BackgroundTasks, Header
from fastapi.responses import JSONResponse

from app.config import settings
from app.errors import problem
from app.workers import digest_worker, ingest_worker

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
def run_digest_worker(
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
) -> JSONResponse:
    """
    Trigger one run of the digest worker.

    Called daily by .github/workflows/digest-cron.yml. Returns 202 immediately
    and runs the worker in the background — avoids Azure Container Apps' 240s
    HTTP timeout on long-running jobs.
    """
    _require_worker_secret(authorization)
    background_tasks.add_task(digest_worker.run)
    return JSONResponse(status_code=202, content={"status": "accepted"})


@router.post("/backfill-embeddings")
def backfill_embeddings(authorization: str | None = Header(default=None)) -> dict:
    """
    One-shot: embed all articles that currently have no embedding vector.
    Safe to re-run — skips already-embedded articles.
    """
    _require_worker_secret(authorization)
    try:
        from app.pipeline.rag.vector_store import ArticleVectorStore
        from app.pipeline.models import Article as PipelineArticle
        from app.db.session import SessionLocal
        from app.models import Article as ArticleORM
        import uuid

        store = ArticleVectorStore()
        from sqlalchemy.orm import joinedload
        with SessionLocal() as db:
            rows = (
                db.query(ArticleORM)
                .options(joinedload(ArticleORM.source))
                .filter(ArticleORM.embedding.is_(None))
                .all()
            )
            # Detach with data loaded — access source name while session is open
            row_data = [
                {
                    "id": r.id, "url": r.url, "title": r.title,
                    "source_name": r.source.name if r.source else "",
                    "published_at": r.published_at,
                    "body": r.body or r.extract or "",
                    "extract": r.extract,
                }
                for r in rows
            ]

        if not row_data:
            return {"status": "ok", "backfilled": 0, "message": "all articles already have embeddings"}

        # Process in batches of 32 to avoid OOM
        total = 0
        batch_size = 32
        for i in range(0, len(row_data), batch_size):
            batch = row_data[i : i + batch_size]
            articles = [
                PipelineArticle(
                    id=r["id"], url=r["url"], title=r["title"],
                    source=r["source_name"], published_at=r["published_at"],
                    content=r["body"], summary=r["extract"],
                )
                for r in batch
            ]
            texts = [store._embed_text(a) for a in articles]
            embeddings = store._encode(texts)
            with SessionLocal() as db:
                for r, embedding in zip(batch, embeddings):
                    orm_row = db.get(ArticleORM, r["id"])
                    if orm_row and orm_row.embedding is None:
                        orm_row.embedding = embedding
                        total += 1
                db.commit()

        return {"status": "ok", "backfilled": total}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@router.post("/run-ingest")
def run_ingest(
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
) -> JSONResponse:
    """
    Fetch all RSS sources across every scrape tier, deduplicate, embed,
    and index into pgvector. Does NOT generate digests.

    Returns 202 immediately and runs the ingest in the background — avoids
    Azure Container Apps' 240s HTTP timeout on long-running jobs.
    Idempotent — re-indexing an already-embedded article is a cheap upsert.
    """
    _require_worker_secret(authorization)
    background_tasks.add_task(ingest_worker.run)
    return JSONResponse(status_code=202, content={"status": "accepted"})
