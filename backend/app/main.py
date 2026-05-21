"""
FastAPI application entry point.

Wires routers under `/api/v1/...` (per docs/api.md §1 versioning decision),
sets up exception handlers, and creates DB tables on startup so the app
boots from scratch with no manual schema step.

Run locally:

    uvicorn app.main:app --reload

OpenAPI docs at http://localhost:8000/docs once running.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Importing `app.models` registers all ORM classes on `Base.metadata`,
# so `create_all` below sees every table. Without this import the tables
# don't get created.
from app import models  # noqa: F401
from app.config import settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.errors import PROBLEM_CONTENT_TYPE, problem_response
from app.routers import articles as articles_router
from app.routers import auth as auth_router
from app.routers import digests as digests_router
from app.routers import health as health_router
from app.routers import internal as internal_router
from app.routers import me as me_router
from app.routers import sessions as sessions_router
from app.routers import topics as topics_router
from app.seed import seed_topics


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs once at app startup (before handling requests) and once at shutdown.

    Today: create tables if they don't exist. Replace with Alembic migrations
    before any prod deploy — auto-create won't catch schema drift.
    """
    Base.metadata.create_all(bind=engine)
    # Topic taxonomy is required by the prefs UI on day one, so seed it
    # at every boot. The seed is idempotent — existing rows are untouched.
    with SessionLocal() as db:
        seed_topics(db)
    yield
    # No shutdown work yet.


app = FastAPI(
    title="Tech Intelligence Newsletter API",
    version="0.1.0",
    lifespan=lifespan,
)


# ─── CORS ─────────────────────────────────────────────────────────────────
# Dev: permit common frontend dev-server origins so FE1 can hit the API
# from `npm run dev` without proxy setup.
# Prod: only the origins in ALLOWED_ORIGINS env var (the Vercel deployment URL).
_DEV_ORIGINS = [
    "http://localhost:3000",   # Next.js default
    "http://localhost:5173",   # Vite default
    "http://localhost:4173",   # Vite preview
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]
_origins = _DEV_ORIGINS if settings.is_dev else settings.allowed_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Idempotency-Key"],
)


# ─── Exception handlers ───────────────────────────────────────────────────
# Make every error a proper RFC 7807 response (docs/api.md §1).


@app.exception_handler(HTTPException)
async def http_exception_handler(_request, exc: HTTPException):
    """
    Convert FastAPI's HTTPException into an RFC 7807 body.

    `app.errors.problem(...)` returns HTTPException with a dict in `detail`;
    we just need to set the right content type and pass it through.
    """
    body = exc.detail if isinstance(exc.detail, dict) else {
        "type": "about:blank",
        "title": str(exc.detail),
        "status": exc.status_code,
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=body,
        media_type=PROBLEM_CONTENT_TYPE,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request, exc: RequestValidationError):
    """
    Pydantic validation failures → 422 problem doc.

    We surface the underlying errors so frontend can target offending fields.
    """
    return problem_response(
        status=422,
        title="Validation failed",
        detail=str(exc.errors()),
    )


# ─── Router wiring ────────────────────────────────────────────────────────
# All routers live under /api/v1 (docs/api.md §1 versioning).

API_PREFIX = "/api/v1"

app.include_router(health_router.router, prefix=API_PREFIX)
app.include_router(auth_router.router, prefix=API_PREFIX)
app.include_router(me_router.router, prefix=API_PREFIX)
app.include_router(topics_router.router, prefix=API_PREFIX)
app.include_router(articles_router.router, prefix=API_PREFIX)
app.include_router(digests_router.router, prefix=API_PREFIX)
app.include_router(sessions_router.router, prefix=API_PREFIX)
app.include_router(internal_router.router, prefix=API_PREFIX)
