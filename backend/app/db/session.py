"""
Database engine + session factory.

`engine` is the connection pool — created once per process.
`SessionLocal` is the factory used to mint per-request sessions; see
app/deps.py for the FastAPI dependency that hands them out.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings


# SQLite needs `check_same_thread=False` because FastAPI may share the
# connection across threads. Real Postgres doesn't need this flag.
_engine_kwargs: dict = {}
if settings.database_url.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

# The engine owns the connection pool. One per process is enough.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # checks a connection is alive before handing it out
    **_engine_kwargs,
)

# A session represents a unit of work / a transaction. We don't autoflush
# (we control when SQL goes out) and don't expire instances after commit
# (so attribute access after commit doesn't trigger a re-fetch).
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)
