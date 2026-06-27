"""
Database connection for the data-engineering service.

Reads DATABASE_URL from data_engineering/.env (gitignored).
Uses psycopg3 directly — no SQLAlchemy — so the DE service has no
dependency on the backend's ORM layer.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# Load .env from the data_engineering/ directory, not the repo root.
_ENV_FILE = Path(__file__).parent / ".env"
load_dotenv(_ENV_FILE, override=False)


def get_connection() -> psycopg.Connection:
    """
    Open a new psycopg3 connection.

    Callers are responsible for closing it (use as a context manager):

        with db.get_connection() as conn:
            ...
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. "
            "Copy data_engineering/.env.example to data_engineering/.env "
            "and fill in the connection string."
        )
    # psycopg3 accepts both `postgresql://` and `postgresql+psycopg://` prefixes.
    url = url.replace("postgresql+psycopg://", "postgresql://")
    return psycopg.connect(url)
