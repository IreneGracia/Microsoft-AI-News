"""
Source registry — loads and queries sources.json.

Canonical source: the repo-root sources.json (shared across all modules).
Falls back to llm_engineering/config/sources.json if the root file is absent
(useful when running this module standalone outside the monorepo).

Provides filtered views of sources by scrape tier, topic tag, region, or user profile.

Source ID aliases: data_engineering/sources.py uses shorter IDs (e.g. "mit_tech_review")
while sources.json uses full IDs (e.g. "mit_technology_review"). Both resolve correctly
via get_source_by_id() so adapters can work with either format.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from src.models import TechCategory, UserProfile

# Prefer repo-root sources.json; fall back to local config copy
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

# Map JSON topic/business/regulation tag strings → our TechCategory enum
_TAG_TO_CATEGORY: dict[str, TechCategory] = {
    "Artificial Intelligence & ML":         TechCategory.AI_ML,
    "Cybersecurity":                         TechCategory.SECURITY,
    "Cybersecurity Policy":                  TechCategory.SECURITY,
    "Cloud & Infrastructure":               TechCategory.CLOUD,
    "Software Development":                  TechCategory.DEVELOPER_TOOLS,
    "Hardware & Chips":                      TechCategory.HARDWARE,
    "Data & Privacy":                        TechCategory.SECURITY,
    "Startups & Venture":                    TechCategory.STARTUPS,
    "M&A & Funding":                         TechCategory.STARTUPS,
    "Big Tech (FAANG+Microsoft)":            TechCategory.ENTERPRISE_SOFTWARE,
    "Earnings & Revenue":                    TechCategory.ENTERPRISE_SOFTWARE,
    "IPO & Markets":                         TechCategory.STARTUPS,
    "AI Regulation":                         TechCategory.POLICY_REGULATION,
    "Data Protection (GDPR, DPDP, LGPD)":   TechCategory.POLICY_REGULATION,
    "Antitrust & Competition":               TechCategory.POLICY_REGULATION,
    "Export Controls & Sanctions":           TechCategory.POLICY_REGULATION,
    "Digital Infrastructure Policy":         TechCategory.POLICY_REGULATION,
    "Platform Regulation":                   TechCategory.POLICY_REGULATION,
    "Layoffs & Hiring":                      TechCategory.ENTERPRISE_SOFTWARE,
    "Health & Biotech":                      TechCategory.OTHER,
    "Fintech & Payments":                    TechCategory.OTHER,
    "Quantum Computing":                     TechCategory.OTHER,
    "Robotics & Automation":                 TechCategory.OTHER,
    "Clean Tech & Sustainability":           TechCategory.OTHER,
    "Space & Satellites":                    TechCategory.OTHER,
    "Metaverse & XR":                        TechCategory.OTHER,
}


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
    categories: list[TechCategory] = field(default_factory=list)
    region_tags: list[str] = field(default_factory=list)
    source_region: Optional[str] = None
    notes: str = ""

    @property
    def needs_full_fetch(self) -> bool:
        return self.content_quality == "excerpts"

    @property
    def is_primary(self) -> bool:
        return self.source_type == "primary"


def _tags_to_categories(topic_tags: list, business_tags: list, regulation_tags: list) -> list[TechCategory]:
    cats: set[TechCategory] = set()
    for tag in topic_tags + business_tags + regulation_tags:
        if cat := _TAG_TO_CATEGORY.get(tag):
            cats.add(cat)
    return list(cats) or [TechCategory.OTHER]


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
            categories=_tags_to_categories(
                s.get("default_topic_tags", []),
                s.get("default_business_tags", []),
                s.get("default_regulation_tags", []),
            ),
            region_tags=s.get("region_tags", []),
            source_region=s.get("source_region"),
            notes=s.get("notes", ""),
        ))
    return sources


def get_sources_for_tier(tier: str) -> list[Source]:
    return [s for s in load_sources() if s.scrape_tier == tier]


def get_sources_for_user(user: UserProfile) -> list[Source]:
    """
    Return sources relevant to this user's interests.
    - At least one source category overlaps with user interests, OR
    - Source covers a Big Tech company the user tracks.
    Always include primary sources (company blogs, gov sources) if interest matches.
    """
    all_sources = load_sources()
    user_cats = set(user.interests)

    relevant: list[Source] = []
    for source in all_sources:
        source_cats = set(source.categories)
        if user_cats & source_cats:
            relevant.append(source)
            continue
        # Always include primary sources for AI/ML — they're high signal
        if source.is_primary and TechCategory.AI_ML in source.categories:
            relevant.append(source)

    return relevant


def get_source_by_id(source_id: str) -> Optional[Source]:
    """Resolve a source by its canonical ID or a data_engineering short-form alias."""
    canonical_id = _DE_ID_ALIASES.get(source_id, source_id)
    return next((s for s in load_sources() if s.id == canonical_id), None)
