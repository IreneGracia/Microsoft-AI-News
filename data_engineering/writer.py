"""
Database writer — the data-engineering service's only path to Postgres.

Rules enforced here:
  - DE owns all INSERT/UPDATE on the `articles` and `sources` tables.
  - The backend and LLM side only read those tables.
  - Watermarks live in `kv_state` under keys `rss_watermark:{source_id}`.
  - Upserts are idempotent: re-running the same articles is safe.

Vectors are passed as Postgres literal strings (`'[f1,f2,…]'::vector`)
so this module has no dependency on the pgvector Python package.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

import psycopg

from models import ArticleRecord


# ── helpers ───────────────────────────────────────────────────────────────────

def _new_article_id() -> str:
    return f"art_{uuid.uuid4().hex}"


def _vec(embedding: Optional[list[float]]) -> Optional[str]:
    """Convert a float list to the Postgres vector literal '[f,f,…]'."""
    if embedding is None:
        return None
    return "[" + ",".join(str(v) for v in embedding) + "]"


# ── sources ───────────────────────────────────────────────────────────────────

def upsert_sources(conn: psycopg.Connection, sources: list[dict]) -> int:
    """
    Upsert source registry rows from sources.json into the `sources` table.

    Articles have a NOT NULL FK to sources.id, so this must run before
    upsert_articles().  Safe to call on every pipeline run — existing rows
    are updated in place, no duplicates created.
    """
    sql = """
        INSERT INTO sources (
            id, name, homepage_url, rss_feed_url,
            category, source_type, content_quality, region_json
        )
        VALUES (
            %(id)s, %(name)s, %(homepage_url)s, %(rss_feed_url)s,
            %(category)s, %(source_type)s, %(content_quality)s, %(region_json)s
        )
        ON CONFLICT (id) DO UPDATE SET
            name            = EXCLUDED.name,
            homepage_url    = EXCLUDED.homepage_url,
            rss_feed_url    = EXCLUDED.rss_feed_url,
            category        = EXCLUDED.category,
            source_type     = EXCLUDED.source_type,
            content_quality = EXCLUDED.content_quality,
            region_json     = EXCLUDED.region_json
    """
    with conn.cursor() as cur:
        for s in sources:
            cur.execute(sql, {
                "id":             s["id"],
                "name":           s.get("name") or s["id"],
                "homepage_url":   s.get("homepage_url"),
                "rss_feed_url":   s.get("rss_url"),
                "category":       s.get("category"),
                "source_type":    s.get("source_type"),
                "content_quality": s.get("content_quality"),
                "region_json":    json.dumps(s.get("region", [])),
            })
    conn.commit()
    return len(sources)


# ── articles ──────────────────────────────────────────────────────────────────

def upsert_articles(conn: psycopg.Connection, articles: list[ArticleRecord]) -> int:
    """
    Upsert a batch of articles.  URL is the natural dedup key.

    Embedding update logic:
      - New article:   embedding written unconditionally.
      - Existing article, content_hash changed: embedding updated.
      - Existing article, content_hash unchanged: embedding kept as-is
        (COALESCE keeps the stored value when EXCLUDED is NULL for this path,
        but since we always compute embeddings at ingestion time, EXCLUDED
        embedding is never NULL).

    Returns the number of rows inserted or updated.
    """
    if not articles:
        return 0

    sql = """
        INSERT INTO articles (
            id, source_id, title, url, author,
            published_at, ingested_at,
            extract, body, rss_feed_url,
            content_hash, original_language, embedding
        ) VALUES (
            %(id)s, %(source_id)s, %(title)s, %(url)s, %(author)s,
            %(published_at)s, NOW(),
            %(extract)s, %(body)s, %(rss_feed_url)s,
            %(content_hash)s, %(original_language)s,
            %(embedding)s::vector
        )
        ON CONFLICT (url) DO UPDATE SET
            title             = EXCLUDED.title,
            author            = EXCLUDED.author,
            published_at      = EXCLUDED.published_at,
            extract           = EXCLUDED.extract,
            body              = EXCLUDED.body,
            content_hash      = EXCLUDED.content_hash,
            original_language = EXCLUDED.original_language,
            embedding         = CASE
                WHEN EXCLUDED.content_hash IS DISTINCT FROM articles.content_hash
                THEN EXCLUDED.embedding
                ELSE COALESCE(articles.embedding, EXCLUDED.embedding)
            END
    """
    written = 0
    with conn.cursor() as cur:
        for art in articles:
            cur.execute(sql, {
                "id":               _new_article_id(),
                "source_id":        art.source_id,
                "title":            art.title,
                "url":              art.url,
                "author":           art.author,
                "published_at":     art.published_at,
                "extract":          art.extract,
                "body":             art.summary or None,
                "rss_feed_url":     art.rss_feed_url,
                "content_hash":     art.hash,
                "original_language": art.original_language,
                "embedding":        _vec(art.embedding),
            })
            written += cur.rowcount
    conn.commit()
    return written


# ── watermarks ────────────────────────────────────────────────────────────────

_WATERMARK_PREFIX = "rss_watermark:"


def read_watermarks(conn: psycopg.Connection, source_ids: list[str]) -> dict[str, Optional[str]]:
    """
    Return {source_id: iso_timestamp | None} for every requested source.
    Sources with no stored watermark get None (fetch from the beginning).
    """
    keys = [f"{_WATERMARK_PREFIX}{sid}" for sid in source_ids]
    with conn.cursor() as cur:
        cur.execute(
            "SELECT key, value FROM kv_state WHERE key = ANY(%s)",
            (keys,),
        )
        stored = {row[0]: row[1] for row in cur.fetchall()}

    return {
        sid: stored.get(f"{_WATERMARK_PREFIX}{sid}")
        for sid in source_ids
    }


def write_watermarks(conn: psycopg.Connection, watermarks: dict[str, str]) -> None:
    """
    Upsert per-source fetch watermarks.
    watermarks: {source_id: iso_timestamp_string}
    """
    sql = """
        INSERT INTO kv_state (key, value)
        VALUES (%s, %s)
        ON CONFLICT (key) DO UPDATE SET
            value      = EXCLUDED.value,
            updated_at = NOW()
    """
    with conn.cursor() as cur:
        for source_id, ts in watermarks.items():
            cur.execute(sql, (f"{_WATERMARK_PREFIX}{source_id}", ts))
    conn.commit()
