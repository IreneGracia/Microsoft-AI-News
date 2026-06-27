"""
Live DB connection test — run before committing.

    cd data_engineering
    python test_connection.py

Checks:
  1. DATABASE_URL is set and psycopg3 can connect.
  2. pgvector extension is enabled.
  3. Required tables exist (articles, sources, kv_state).
  4. articles.embedding column is the right dimension (384).
  5. Inserts one test article record (with a real embedding), reads it
     back, then deletes it — leaving the DB unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import db
import embedder
from models import ArticleRecord
from writer import upsert_articles, upsert_sources, read_watermarks, write_watermarks


PASS = "\033[32m PASS\033[0m"
FAIL = "\033[31m FAIL\033[0m"


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = PASS if ok else FAIL
    line = f"{status}  {label}"
    if detail:
        line += f"  ({detail})"
    print(line)
    return ok


def main() -> int:
    errors = 0

    # ── 1. Connect ────────────────────────────────────────────────────────────
    try:
        conn = db.get_connection()
        errors += 0 if check("psycopg3 connect", True) else 1
    except Exception as exc:
        check("psycopg3 connect", False, str(exc))
        print("\nFix: create data_engineering/.env with DATABASE_URL=postgresql+psycopg://...")
        return 1

    with conn:
        # ── 2. pgvector extension ─────────────────────────────────────────────
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'"
            )
            has_vector = cur.fetchone()[0] == 1
        errors += 0 if check("pgvector extension enabled", has_vector) else 1

        # ── 3. Required tables ────────────────────────────────────────────────
        required_tables = ["articles", "sources", "kv_state", "tags", "article_tags"]
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
            existing = {row[0] for row in cur.fetchall()}
        for table in required_tables:
            ok = table in existing
            errors += 0 if check(f"table '{table}' exists", ok) else 1

        # ── 4. Embedding column dimension ─────────────────────────────────────
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT atttypmod
                FROM pg_attribute
                JOIN pg_class ON pg_attribute.attrelid = pg_class.oid
                WHERE pg_class.relname = 'articles'
                  AND pg_attribute.attname = 'embedding'
                """
            )
            row = cur.fetchone()
        if row:
            dim = row[0]
            errors += 0 if check(f"articles.embedding dim = 384", dim == 384, f"got {dim}") else 1
        else:
            check("articles.embedding column exists", False, "column not found")
            errors += 1

        # ── 5. Embed one text to validate model ───────────────────────────────
        try:
            vecs = embedder.embed(["test connectivity"])
            ok = len(vecs) == 1 and len(vecs[0]) == 384
            errors += 0 if check("embedder produces 384-dim vector", ok) else 1
        except Exception as exc:
            check("embedder produces 384-dim vector", False, str(exc))
            errors += 1
            vecs = None

        # ── 6. Round-trip: insert test article, read back, delete ─────────────
        if vecs:
            test_url = "https://test.mai-news.internal/connection-test"
            test_source_id = "src_test_connection"

            # ensure dummy source exists for FK
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sources (id, name)
                    VALUES (%s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (test_source_id, "__test_connection__"),
                )
            conn.commit()

            art = ArticleRecord(
                url=test_url,
                title="Connection test article",
                source_id=test_source_id,
                rss_feed_url="https://test.mai-news.internal/rss",
                published_at=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ),
                summary="This article was inserted by test_connection.py and will be deleted.",
                embedding=vecs[0],
            )

            try:
                written = upsert_articles(conn, [art])
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, title FROM articles WHERE url = %s",
                        (test_url,),
                    )
                    fetched = cur.fetchone()
                ok = fetched is not None and fetched[1] == "Connection test article"
                errors += 0 if check("article round-trip (insert + read)", ok) else 1
            except Exception as exc:
                check("article round-trip (insert + read)", False, str(exc))
                errors += 1
                fetched = None

            # clean up
            with conn.cursor() as cur:
                cur.execute("DELETE FROM articles WHERE url = %s", (test_url,))
                cur.execute(
                    "DELETE FROM sources WHERE id = %s", (test_source_id,)
                )
            conn.commit()
            check("test data cleaned up", True)

        # ── 7. Watermark round-trip ───────────────────────────────────────────
        test_wm = {"_test_source_": "2026-01-01T00:00:00+00:00"}
        try:
            write_watermarks(conn, test_wm)
            read_back = read_watermarks(conn, ["_test_source_"])
            ok = read_back.get("_test_source_") == "2026-01-01T00:00:00+00:00"
            errors += 0 if check("watermark round-trip (kv_state)", ok) else 1
            # clean up
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM kv_state WHERE key = 'rss_watermark:_test_source_'"
                )
            conn.commit()
        except Exception as exc:
            check("watermark round-trip (kv_state)", False, str(exc))
            errors += 1

    print()
    if errors == 0:
        print("All checks passed. DB is ready for the ingestion pipeline.")
    else:
        print(f"{errors} check(s) failed. Fix the issues above before running pipeline.py.")
    return errors


if __name__ == "__main__":
    sys.exit(main())
