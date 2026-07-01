"""
Source registry — loads sources.json and exposes filtered views.

Canonical source: the repo-root sources.json (shared with the backend's
`seed_sources`). Falls back to a local config copy if absent.

Tags are stored as slugs (e.g. "artificial_intelligence_ml") derived
from the human labels in sources.json via the same `tag_slug` rule the
backend's seed uses. The pipeline-side flat `TechCategory` enum is gone
— sources carry slugs across all backend tag dimensions, and matching
against users is done by slug overlap per dimension.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from app.pipeline.models import UserProfile

# Prefer repo-root sources.json; fall back to local config copy
# File lives at <root>/app/pipeline/ingestion/source_registry.py — 4 dirname calls reach <root>
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
_ROOT_SOURCES = os.path.join(_REPO_ROOT, "sources.json")
_LOCAL_SOURCES = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "sources.json")
_SOURCES_PATH = _ROOT_SOURCES if os.path.exists(_ROOT_SOURCES) else _LOCAL_SOURCES

# Short-form IDs used by data_engineering/sources.py → canonical ID in sources.json
_DE_ID_ALIASES: dict[str, str] = {
    "mit_tech_review":     "mit_technology_review",
    "techcrunch":          "techcrunch",
    "wired":               "wired",
    "venturebeat":         "venturebeat",
    "the_verge":           "the_verge",
    "ars_technica_policy": "ars_technica_tech_policy",
    "tech_policy_press":   "tech_policy_press",
    "euractiv":            "euractiv",
    "politico_eu":         "politico_europe",
    "eu_parliament":       "eu_parliament",
    "edpb":                "edpb",
    "bloomberg_tech":      "bloomberg_technology",
    "economist":           "the_economist",
    "sifted":              "sifted",
    "politico_us":         "politico_us",
    "the_local_de":        "the_local_de",
    "the_local_fr":        "the_local_fr",
    "the_local_es":        "the_local_es",
    "the_local_it":        "the_local_it",
    "the_local_se":        "the_local_se",
    "the_local_dk":        "the_local_dk",
    "the_local_no":        "the_local_no",
    "the_local_at":        "the_local_at",
    "the_local_ch":        "the_local_ch",
    "the_recursive":       "the_recursive",
}


def tag_slug(label: str) -> str:
    """
    Derive a stable, machine-friendly slug from a taxonomy label. Mirrors
    backend/app/seed.tag_slug — keep the two in sync.

      "Artificial Intelligence & ML"  -> "artificial_intelligence_ml"
      "M&A & Funding"                 -> "ma_funding"
    """
    s = label.lower().replace("&", "")
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


@dataclass
class Source:
    id: str
    name: str
    homepage: str
    rss_url: str
    source_type: str          # "primary" | "secondary" | "aggregator"
    scrape_tier: str          # "breaking" | "standard" | "daily"
    scrape_interval_min: int
    content_quality: str      # "full" | "excerpts"

    # Slugs per backend tag dimension. Populated from the source's
    # default_*_tags labels in sources.json via tag_slug().
    topic_tags: list[str] = field(default_factory=list)
    business_tags: list[str] = field(default_factory=list)
    regulation_tags: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)

    source_region: Optional[str] = None
    notes: str = ""

    @property
    def needs_full_fetch(self) -> bool:
        return self.content_quality == "excerpts"

    @property
    def is_primary(self) -> bool:
        return self.source_type == "primary"


def _slug_list(labels: list) -> list[str]:
    return [tag_slug(label) for label in labels if isinstance(label, str) and label]


@lru_cache(maxsize=1)
def load_sources() -> list[Source]:
    with open(_SOURCES_PATH, encoding="utf-8") as f:
        data = json.load(f)

    sources = []
    for s in data["sources"]:
        sources.append(Source(
            id=s["id"],
            name=s["name"],
            homepage=s["homepage"],
            rss_url=s["rss_url"],
            source_type=s["source_type"],
            scrape_tier=s["scrape_tier"],
            scrape_interval_min=s["scrape_interval_min"],
            content_quality=s["content_quality"],
            topic_tags=_slug_list(s.get("default_topic_tags", [])),
            business_tags=_slug_list(s.get("default_business_tags", [])),
            regulation_tags=_slug_list(s.get("default_regulation_tags", [])),
            regions=_slug_list(s.get("region_tags", [])),
            source_region=s.get("source_region"),
            notes=s.get("notes", ""),
        ))
    return sources


def get_sources_for_tier(tier: str) -> list[Source]:
    return [s for s in load_sources() if s.scrape_tier == tier]


def get_sources_for_user(user: UserProfile) -> list[Source]:
    """
    Return sources whose tags overlap with the user's preferences along
    any of the four content dimensions, or primary AI/ML sources for
    users with the AI/ML topic interest (high-signal floor).

    If the user has no tags at all across every dimension (e.g. they
    finished onboarding without picking any topics), matching against an
    empty set would return zero sources and produce a permanently empty
    digest with no visible error. Fall back to the primary source set so
    these users still get a newsletter instead of silence.
    """
    user_topics = set(user.topic_tags)
    user_business = set(user.business_tags)
    user_regulation = set(user.regulation_tags)
    user_regions = set(user.regions)

    if not (user_topics or user_business or user_regulation or user_regions):
        return [s for s in load_sources() if s.is_primary]

    relevant: list[Source] = []
    for source in load_sources():
        if (
            user_topics & set(source.topic_tags)
            or user_business & set(source.business_tags)
            or user_regulation & set(source.regulation_tags)
            or user_regions & set(source.regions)
        ):
            relevant.append(source)
            continue
        # Primary AI/ML sources are high signal — always include for AI/ML users.
        if (
            source.is_primary
            and "artificial_intelligence_ml" in source.topic_tags
            and "artificial_intelligence_ml" in user_topics
        ):
            relevant.append(source)

    return relevant


def get_source_by_id(source_id: str) -> Optional[Source]:
    """Resolve a source by its canonical ID or a data_engineering short-form alias."""
    canonical_id = _DE_ID_ALIASES.get(source_id, source_id)
    return next((s for s in load_sources() if s.id == canonical_id), None)
