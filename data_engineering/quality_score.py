"""
quality_score.py — per-article importance score for surfacing top news.

Computes a 0-1 score from signals available at ingestion time, with no
external calls and no cost:

  • source_tier   — primary/official sources rank above aggregators
  • recency       — newer articles score higher (exponential decay)
  • title_signal  — presence of high-salience terms (funding, launch,
                    acquisition, regulation, breach…) that mark a story as
                    consequential rather than routine
  • content_depth — articles with real body text beat headline-only stubs

The score is stored on the article and used by the digest ranker to put the
most important news at the top. Deterministic and explainable — every term
is inspectable, which matters for a compliance-conscious product.
"""
from __future__ import annotations

import math
import os
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path


# ── source-type weights (from sources.json source_type) ──────────────────────

_SOURCE_TYPE_WEIGHT = {
    "primary": 1.0,      # official gov / regulator / company blog
    "secondary": 0.8,    # journalism
    "aggregator": 0.6,   # GDELT etc.
}


def _sources_json_path() -> Path:
    override = os.environ.get("SOURCES_JSON_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "sources.json"


@lru_cache(maxsize=1)
def _source_type_by_id() -> dict[str, str]:
    with _sources_json_path().open(encoding="utf-8") as f:
        data = json.load(f)
    return {s["id"]: s.get("source_type", "secondary") for s in data.get("sources", [])}


# ── salience terms ───────────────────────────────────────────────────────────

_HIGH_SALIENCE = {
    "acqui", "merger", "acquire", "buyout",          # M&A
    "raises", "funding", "series ", "ipo", "valuation",
    "launch", "unveil", "releases", "announces",
    "ban", "regulation", "fine", "lawsuit", "antitrust", "ruling",
    "breach", "hack", "vulnerability", "outage",
    "layoff", "cuts", "earnings", "record",
}


def _title_salience(title: str) -> float:
    """Fraction-ish bump for consequential keywords (capped)."""
    t = title.lower()
    hits = sum(1 for kw in _HIGH_SALIENCE if kw in t)
    return min(hits * 0.25, 1.0)  # 0, 0.25, 0.5, 0.75, 1.0


# ── recency ──────────────────────────────────────────────────────────────────

def _recency_factor(published_at: datetime, half_life_hours: float = 36.0) -> float:
    """Exponential decay: 1.0 now, 0.5 at one half-life, → 0 as it ages."""
    now = datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_h = max((now - published_at).total_seconds() / 3600.0, 0.0)
    return math.exp(-age_h * math.log(2) / half_life_hours)


# ── content depth ────────────────────────────────────────────────────────────

def _depth_factor(summary: str) -> float:
    """Headline-only stubs score low; full bodies score high."""
    n = len(summary or "")
    if n >= 800:
        return 1.0
    if n >= 300:
        return 0.8
    if n >= 100:
        return 0.5
    return 0.3


# ── main ─────────────────────────────────────────────────────────────────────

# Weights sum to 1.0; tune as you see real data.
_W_SOURCE = 0.30
_W_RECENCY = 0.30
_W_SALIENCE = 0.25
_W_DEPTH = 0.15


def importance_score(
    source_id: str,
    title: str,
    summary: str,
    published_at: datetime,
) -> float:
    """Return a 0-1 importance score. Higher = surface nearer the top."""
    source_type = _source_type_by_id().get(source_id, "secondary")
    source_w = _SOURCE_TYPE_WEIGHT.get(source_type, 0.8)

    score = (
        _W_SOURCE * source_w
        + _W_RECENCY * _recency_factor(published_at)
        + _W_SALIENCE * _title_salience(title)
        + _W_DEPTH * _depth_factor(summary)
    )
    return round(min(max(score, 0.0), 1.0), 4)


def score_articles_batch(records: list) -> None:
    """Attach `.importance` to each ArticleRecord in place."""
    for r in records:
        r.importance = importance_score(
            source_id=getattr(r, "source_id", ""),
            title=getattr(r, "title", ""),
            summary=getattr(r, "summary", ""),
            published_at=getattr(r, "published_at", datetime.now(timezone.utc)),
        )


if __name__ == "__main__":
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    tests = [
        ("eu_press_corner", "EU announces sweeping AI Act enforcement fines", "x" * 900, now),
        ("techcrunch", "Startup raises $50M Series B for AI chips", "x" * 400, now - timedelta(hours=10)),
        ("gdelt", "Local tech meetup held in Nairobi", "short", now - timedelta(hours=70)),
    ]
    print("Importance score smoke test:\n")
    for sid, title, summary, pub in tests:
        s = importance_score(sid, title, summary, pub)
        print(f"  {s:.3f}  [{sid}] {title}")