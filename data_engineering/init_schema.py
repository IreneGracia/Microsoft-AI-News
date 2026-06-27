"""
Bootstrap the content schema on a fresh Postgres database.

Creates only the tables the data-engineering pipeline owns or reads:
  sources, tags, articles, article_tags, kv_state

The backend (FastAPI) creates the remaining tables (users, chat_sessions,
digests, etc.) on startup via SQLAlchemy create_all().  Run this script
first on a fresh DB so the pipeline can ingest before the backend is
deployed, or to set up a standalone DE environment.

Safe to re-run — all statements use IF NOT EXISTS.

    cd data_engineering
    py -3 init_schema.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import db

DDL: list[tuple[str, str]] = [
    ("pgvector extension", "CREATE EXTENSION IF NOT EXISTS vector"),

    ("sources table", """
        CREATE TABLE IF NOT EXISTS sources (
            id               TEXT        PRIMARY KEY,
            name             TEXT        NOT NULL,
            homepage_url     TEXT,
            rss_feed_url     TEXT,
            category         TEXT,
            source_type      TEXT,
            content_quality  TEXT,
            region_json      TEXT        NOT NULL DEFAULT '[]',
            robots_txt_status TEXT,
            license          TEXT
        )
    """),

    ("tags table", """
        CREATE TABLE IF NOT EXISTS tags (
            dimension  TEXT  NOT NULL,
            slug       TEXT  NOT NULL,
            label      TEXT  NOT NULL,
            PRIMARY KEY (dimension, slug)
        )
    """),

    ("articles table", """
        CREATE TABLE IF NOT EXISTS articles (
            id                TEXT        PRIMARY KEY,
            source_id         TEXT        NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
            title             TEXT        NOT NULL,
            url               TEXT        NOT NULL UNIQUE,
            author            TEXT,
            published_at      TIMESTAMPTZ NOT NULL,
            ingested_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            extract           TEXT,
            body              TEXT,
            rss_feed_url      TEXT,
            content_hash      TEXT,
            original_language TEXT,
            embedding         vector(384)
        )
    """),

    ("articles published_at index", """
        CREATE INDEX IF NOT EXISTS articles_published_at_idx
        ON articles (published_at DESC)
    """),

    ("articles content_hash index", """
        CREATE INDEX IF NOT EXISTS articles_content_hash_idx
        ON articles (content_hash)
    """),

    ("articles embedding ivfflat index", """
        CREATE INDEX IF NOT EXISTS articles_embedding_ivfflat
        ON articles USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """),

    ("article_tags table", """
        CREATE TABLE IF NOT EXISTS article_tags (
            article_id  TEXT  NOT NULL REFERENCES articles(id)  ON DELETE CASCADE,
            dimension   TEXT  NOT NULL,
            slug        TEXT  NOT NULL,
            PRIMARY KEY (article_id, dimension, slug),
            FOREIGN KEY (dimension, slug) REFERENCES tags(dimension, slug) ON DELETE CASCADE
        )
    """),

    ("kv_state table", """
        CREATE TABLE IF NOT EXISTS kv_state (
            key         TEXT        PRIMARY KEY,
            value       TEXT        NOT NULL DEFAULT '{}',
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """),
]


def main() -> int:
    print("Connecting to database ...")
    try:
        conn = db.get_connection()
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    errors = 0
    with conn:
        with conn.cursor() as cur:
            for label, sql in DDL:
                try:
                    cur.execute(sql)
                    print(f"  ok  {label}")
                except Exception as exc:
                    print(f"  FAIL {label}: {exc}")
                    errors += 1
        conn.commit()

    if errors == 0:
        print("\nSchema ready. Run test_connection.py to verify.")
    else:
        print(f"\n{errors} statement(s) failed.")
    return errors


if __name__ == "__main__":
    sys.exit(main())
