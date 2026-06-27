"""
Ingestion pipeline — daily entry point.

Responsibilities (in order):
  1. Upsert sources from sources.json into the DB.
  2. Read per-source fetch watermarks from kv_state.
  3. Fetch new RSS articles (incremental, watermark-filtered).
  4. Deduplicate by URL (fast) then skip articles already in the DB.
  5. Embed all new articles in one batch (all-MiniLM-L6-v2, 384-dim).
  6. Upsert articles + embeddings into the `articles` table.
  7. Write updated watermarks back to kv_state.

The data-engineering service owns all writes to `articles` and `sources`.
The backend and LLM side read those tables but never write embeddings.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running as `python data_engineering/pipeline.py` from repo root.
sys.path.insert(0, str(Path(__file__).parent))

import db as _db
import embedder as _embedder
import writer as _writer
from models import ArticleRecord
from rss_fetcher import fetch_with_state
from sources import RSS_FEEDS, get_all_sources


def _build_record(raw: dict) -> ArticleRecord | None:
    """Convert a raw fetcher dict to an ArticleRecord.  Returns None on bad data."""
    url = (raw.get("url") or "").strip()
    title = (raw.get("title") or "").strip()
    if not url or not title:
        return None
    try:
        pub_dt = datetime.fromisoformat(raw["pub_date"])
    except (KeyError, ValueError):
        pub_dt = datetime.now(timezone.utc)
    return ArticleRecord(
        url=url,
        title=title,
        source_id=raw["source_id"],
        rss_feed_url=raw.get("rss_feed_url", ""),
        published_at=pub_dt,
        summary=raw.get("summary", ""),
    )


def run() -> dict:
    """
    Execute one full ingestion run.

    Returns a summary dict:
        { fetched, embedded, written, sources_upserted }
    """
    conn = _db.get_connection()
    try:
        return _run(conn)
    finally:
        conn.close()


def _run(conn) -> dict:
    # 1. Sync source registry to DB.
    all_sources = get_all_sources()
    sources_written = _writer.upsert_sources(conn, all_sources)
    print(f"[pipeline] sources upserted: {sources_written}")

    # 2. Read watermarks.
    source_ids = [s["id"] for s in RSS_FEEDS]
    watermarks = _writer.read_watermarks(conn, source_ids)

    # 3. Fetch new RSS entries.
    raw_articles, updated_watermarks = fetch_with_state(RSS_FEEDS, watermarks)
    print(f"[pipeline] fetched: {len(raw_articles)} raw entries")

    # 4. Build ArticleRecords, drop malformed entries.
    records = [r for raw in raw_articles if (r := _build_record(raw)) is not None]
    if not records:
        print("[pipeline] no new articles to process")
        _writer.write_watermarks(conn, {
            k: v for k, v in updated_watermarks.items() if v is not None
        })
        return {"fetched": 0, "embedded": 0, "written": 0, "sources_upserted": sources_written}

    # 5. Embed in one batch (title + summary → 384-dim).
    texts = [r.embed_text for r in records]
    embeddings = _embedder.embed(texts)
    for record, emb in zip(records, embeddings):
        record.embedding = emb
    print(f"[pipeline] embedded: {len(records)} articles")

    # 6. Upsert into articles table.
    written = _writer.upsert_articles(conn, records)
    print(f"[pipeline] written (new + updated): {written}")

    # 7. Persist updated watermarks.
    _writer.write_watermarks(conn, {
        k: v for k, v in updated_watermarks.items() if v is not None
    })

    return {
        "fetched":           len(raw_articles),
        "embedded":          len(records),
        "written":           written,
        "sources_upserted":  sources_written,
    }


if __name__ == "__main__":
    import json
    result = run()
    print("\n" + "=" * 60)
    print("Pipeline complete:")
    print(json.dumps(result, indent=2))
