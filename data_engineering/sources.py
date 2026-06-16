"""
sources.py — loader for the canonical source registry.

The actual data lives in /sources.json at the repo root, which is the single
source of truth shared with backend (seeding) and llm_engineering (retrieval).
This module exposes the same RSS_FEEDS list the data engineering pipeline
expects, built from that JSON file at import time.

If you need to add or remove a source, edit /sources.json — not this file.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path


def _sources_json_path() -> Path:
    """Locate /sources.json — env override or repo root."""
    override = os.environ.get("SOURCES_JSON_PATH")
    if override:
        return Path(override)
    # data_engineering/sources.py -> repo root is one level up
    return Path(__file__).resolve().parent.parent / "sources.json"


@lru_cache(maxsize=1)
def _load() -> list[dict]:
    """Parse sources.json once and cache."""
    path = _sources_json_path()
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("sources", [])


def _to_legacy_shape(s: dict) -> dict:
    """
    Convert a sources.json entry into the shape the data engineering pipeline
    historically used: {id, url, category, region}.
    Keeps rss_fetcher.py and tag_discovery.py working without changes.
    """
    return {
        "id": s["id"],
        "url": s["rss_url"],
        "category": s.get("category", "").lower() or "tech",
        "region": s.get("region", ["Global"])[0] if s.get("region") else "global",
    }


# The list the pipeline imports. Built once at module load.
RSS_FEEDS: list[dict] = [_to_legacy_shape(s) for s in _load()]


# ── Helper accessors (use these in new code) ─────────────────────────
def get_all_sources() -> list[dict]:
    """Return raw source records from sources.json (full schema)."""
    return list(_load())


def get_sources_by_tier(tier: str) -> list[dict]:
    """Filter by scrape_tier: 'breaking', 'standard', or 'daily'."""
    return [s for s in _load() if s.get("scrape_tier") == tier]


def get_sources_by_region(region: str) -> list[dict]:
    """Filter by region (matches the 'region' array in sources.json)."""
    return [s for s in _load() if region in s.get("region", [])]


if __name__ == "__main__":
    # Quick sanity check — run `python data_engineering/sources.py` to verify
    sources = _load()
    print(f"Loaded {len(sources)} sources from {_sources_json_path()}")
    from collections import Counter
    tiers = Counter(s.get("scrape_tier", "?") for s in sources)
    print("By scrape tier:", dict(tiers))