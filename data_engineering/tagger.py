"""
tagger.py — free, self-hosted multi-dimensional article tagger.

Assigns topic / business / regulation tags to each article by cosine
similarity between the article's embedding and each tag label's embedding.
Reuses all-MiniLM-L6-v2 (the same model embedder.py uses) — no API key,
no extra model download, no per-article cost.

The tag taxonomy is read from sources.json (metadata.tags_taxonomy), so it
stays in sync with the single source of truth.

This is a stand-in for a paid LLM tagger: same interface, swappable later.
When the team has API credits, replace `tag_article` internals with an LLM
call and keep the signature identical — nothing downstream changes.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import numpy as np


# ── taxonomy loading ─────────────────────────────────────────────────────────

def _sources_json_path() -> Path:
    override = os.environ.get("SOURCES_JSON_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "sources.json"


@lru_cache(maxsize=1)
def _taxonomy() -> dict[str, list[str]]:
    """Read the tag taxonomy dimensions from sources.json."""
    with _sources_json_path().open(encoding="utf-8") as f:
        data = json.load(f)
    tax = data.get("metadata", {}).get("tags_taxonomy", {})
    # We tag on the content dimensions only; regional/role/seniority are
    # assigned elsewhere (region from source, role/seniority at digest time).
    return {
        "topic": tax.get("topic", []),
        "business": tax.get("business", []),
        "regulation_policy": tax.get("regulation_policy", []),
    }


# ── model (lazy, shared) ─────────────────────────────────────────────────────

_MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
_model = None
_tag_embeddings: dict[str, dict[str, np.ndarray]] | None = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def _get_tag_embeddings() -> dict[str, dict[str, np.ndarray]]:
    """Embed every tag label once and cache (per dimension)."""
    global _tag_embeddings
    if _tag_embeddings is None:
        model = _get_model()
        _tag_embeddings = {}
        for dimension, tags in _taxonomy().items():
            _tag_embeddings[dimension] = {
                tag: np.asarray(model.encode(tag)) for tag in tags
            }
    return _tag_embeddings


# ── tagging ──────────────────────────────────────────────────────────────────

def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
    return float(np.dot(a, b) / denom)


# Per-dimension thresholds + caps. Topic is the richest dimension so we allow
# more tags; regulation is sparse so a higher bar avoids false positives.
_DIMENSION_CONFIG = {
    "topic":             {"threshold": 0.22, "max_tags": 3},
    "business":          {"threshold": 0.24, "max_tags": 2},
    "regulation_policy": {"threshold": 0.26, "max_tags": 2},
}


def tag_article(
    title: str,
    summary: str = "",
    article_embedding: list[float] | np.ndarray | None = None,
) -> dict[str, list[str]]:
    """
    Assign multi-dimensional tags to one article.

    If `article_embedding` is provided (the pipeline already computes it),
    it's reused — no re-embedding. Otherwise the article text is embedded here.

    Returns e.g.:
        {
          "topic":             ["Artificial Intelligence & ML", "Hardware & Chips"],
          "business":          ["M&A & Funding"],
          "regulation_policy": [],
        }
    """
    if article_embedding is not None:
        art_emb = np.asarray(article_embedding)
    else:
        text = f"{title}. {summary}".strip()
        art_emb = np.asarray(_get_model().encode(text))

    tag_embs = _get_tag_embeddings()
    result: dict[str, list[str]] = {}

    for dimension, cfg in _DIMENSION_CONFIG.items():
        scored = [
            (tag, _cosine(art_emb, emb))
            for tag, emb in tag_embs.get(dimension, {}).items()
        ]
        scored.sort(key=lambda x: -x[1])
        result[dimension] = [
            tag for tag, score in scored[: cfg["max_tags"]]
            if score >= cfg["threshold"]
        ]

    return result


def tag_articles_batch(records: list) -> None:
    """
    Tag a list of ArticleRecord objects in place.

    Expects each record to expose `.title`, `.summary`, and optionally
    `.embedding` (reused if present). Writes the tag dict onto `record.tags`.
    """
    for r in records:
        emb = getattr(r, "embedding", None)
        r.tags = tag_article(r.title, getattr(r, "summary", ""), article_embedding=emb)


# ── CLI smoke test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    samples = [
        ("OpenAI releases GPT-5 with improved reasoning",
         "Major gains in math and coding benchmarks"),
        ("EU fines Meta 1.2 billion over data transfers",
         "Regulators cite GDPR violations in transatlantic data flows"),
        ("NVIDIA unveils H200 GPU for AI training",
         "Doubles memory bandwidth for large language models"),
        ("Fintech startup raises $50M Series B",
         "Round led by a major venture capital firm to expand payments"),
    ]
    print("Tagger smoke test (downloads MiniLM on first run):\n")
    for title, summary in samples:
        tags = tag_article(title, summary)
        print(title)
        for dim, vals in tags.items():
            if vals:
                print(f"  {dim}: {', '.join(vals)}")
        print()