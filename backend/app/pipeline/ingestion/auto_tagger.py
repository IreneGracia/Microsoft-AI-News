"""
Per-article content tagger.

Articles used to inherit their tags from source-level defaults in
sources.json — every article from The Verge got "Metaverse & XR" whether
or not the story had anything to do with it, which made preference
filtering look broken. This module assigns topic / business / regulation
tags per article by cosine similarity between the article's embedding and
each taxonomy label's embedding, reusing the same encoder as the vector
store (all-MiniLM-L6-v2 locally) — no API key, no per-article cost.

Ported from data_engineering/tagger.py (which is not shipped in the
backend image). Regional tags are left untouched — region genuinely is a
property of the source, not of individual stories.
"""
from __future__ import annotations

import logging

from app.pipeline.ingestion.source_registry import tag_slug
from app.pipeline.models import Article
from app.seed import _load_taxonomy

log = logging.getLogger(__name__)

# Per-dimension similarity thresholds + caps. Topic is the richest
# dimension so more tags are allowed; regulation is sparse so a higher
# bar avoids false positives. Topic additionally always keeps the top-1
# match so every article stays reachable from at least one topic tab.
_DIMENSION_CONFIG = {
    "topic":             {"threshold": 0.22, "max_tags": 3, "keep_top1": True},
    "business":          {"threshold": 0.24, "max_tags": 2, "keep_top1": False},
    "regulation_policy": {"threshold": 0.26, "max_tags": 2, "keep_top1": False},
}

# Pipeline Article field per taxonomy dimension.
_DIMENSION_FIELD = {
    "topic": "topic_tags",
    "business": "business_tags",
    "regulation_policy": "regulation_tags",
}

# What gets embedded for each tag. Bare labels like "Metaverse & XR" are
# too little signal for the encoder; a short descriptor anchors each tag
# to the vocabulary that actually appears in headlines. Slugs missing
# here fall back to their label text.
_TAG_DESCRIPTORS = {
    # topic
    "artificial_intelligence_ml": "Artificial intelligence and machine learning: AI models, LLMs, neural networks, model training and inference",
    "ai_tools_productivity": "AI tools and productivity software: AI assistants, copilots, coding agents, workplace productivity apps",
    "creative_ai_generative_media": "Creative AI and generative media: AI-generated images, video, music, art and design tools",
    "cybersecurity": "Cybersecurity: hacking, data breaches, malware, ransomware, vulnerabilities, security attacks",
    "cloud_infrastructure": "Cloud computing and infrastructure: data centers, cloud platforms, servers, networking, DevOps",
    "software_development": "Software development: programming languages, frameworks, developer tools, code, APIs, open source",
    "hardware_chips": "Hardware and chips: semiconductors, processors, GPUs, consumer devices, smartphones, gadgets",
    "data_privacy": "Data and privacy: personal data collection, surveillance, tracking, user privacy",
    "quantum_computing": "Quantum computing: qubits, quantum processors, quantum research and algorithms",
    "robotics_automation": "Robotics and automation: robots, drones, autonomous vehicles, self-driving, industrial automation",
    "fintech_payments": "Fintech and payments: digital banking, payment systems, cryptocurrencies, financial technology",
    "health_biotech": "Health and biotech: medicine, drugs, healthcare technology, biotechnology, medical devices",
    "clean_tech_sustainability": "Clean tech and sustainability: renewable energy, climate technology, electric vehicles, green energy",
    "space_satellites": "Space and satellites: rockets, satellite launches, space exploration, aerospace",
    "metaverse_xr": "Metaverse and XR: virtual reality, augmented reality, VR headsets, immersive 3D worlds",
    # business
    "ma_funding": "Mergers, acquisitions and funding: fundraising rounds, venture capital investments, company acquisitions",
    "ipo_markets": "IPOs and stock markets: public offerings, stock prices, market valuations, shares",
    "big_tech_faang_microsoft": "Big Tech companies: Google, Apple, Meta, Amazon, Microsoft and their corporate strategy",
    "startups_venture": "Startups and venture capital: new companies, founders, seed funding, venture-backed businesses",
    "layoffs_hiring": "Layoffs and hiring: job cuts, workforce reductions, recruiting, tech employment",
    "earnings_revenue": "Earnings and revenue: quarterly results, profits, financial performance, sales figures",
    # regulation_policy
    "ai_regulation": "AI regulation: laws and rules governing artificial intelligence, AI safety policy, the AI Act",
    "data_protection_gdpr_dpdp_lgpd": "Data protection law: GDPR, privacy regulation, data transfer rules, privacy fines",
    "antitrust_competition": "Antitrust and competition law: monopoly investigations, competition regulators, market dominance cases",
    "export_controls_sanctions": "Export controls and sanctions: chip export bans, trade restrictions, national security controls",
    "digital_infrastructure_policy": "Digital infrastructure policy: broadband regulation, telecom policy, government technology programs",
    "cybersecurity_policy": "Cybersecurity policy: government security rules, breach disclosure laws, critical infrastructure protection",
    "platform_regulation": "Platform regulation: content moderation laws, app store rules, social media regulation, DSA and DMA",
}

_encoder = None          # shared ArticleVectorStore used only for _encode
_label_embeddings: dict[str, list[tuple[str, list[float]]]] | None = None


def _encode(texts: list[str]) -> list[list[float]]:
    """Encode via the vector store's encoder so tagger and retrieval always share a model."""
    global _encoder
    if _encoder is None:
        from app.pipeline.rag.vector_store import ArticleVectorStore
        _encoder = ArticleVectorStore()
    return _encoder._encode(texts)


def _get_label_embeddings() -> dict[str, list[tuple[str, list[float]]]]:
    """Embed every taxonomy label once: {dimension: [(slug, embedding), ...]}."""
    global _label_embeddings
    if _label_embeddings is None:
        taxonomy = _load_taxonomy()
        embeddings: dict[str, list[tuple[str, list[float]]]] = {}
        for dimension in _DIMENSION_CONFIG:
            labels = [l for l in taxonomy.get(dimension, []) if isinstance(l, str)]
            if not labels:
                embeddings[dimension] = []
                continue
            slugs = [tag_slug(label) for label in labels]
            texts = [_TAG_DESCRIPTORS.get(slug, label) for slug, label in zip(slugs, labels)]
            vectors = _encode(texts)
            embeddings[dimension] = list(zip(slugs, vectors))
        _label_embeddings = embeddings
    return _label_embeddings


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    return dot / ((norm_a * norm_b) or 1.0)


def _article_text(article: Article) -> str:
    # Title + summary + a body excerpt: short marketing-y blurbs alone give
    # the encoder too little signal and tags degrade to near-random.
    parts = [article.title, article.summary or "", (article.content or "")[:800]]
    return ". ".join(p for p in parts if p).strip()


def tags_for_text(embedding: list[float]) -> dict[str, list[str]]:
    """Score one article embedding against every dimension's labels → slug lists."""
    result: dict[str, list[str]] = {}
    for dimension, cfg in _DIMENSION_CONFIG.items():
        scored = [
            (slug, _cosine(embedding, label_vec))
            for slug, label_vec in _get_label_embeddings()[dimension]
        ]
        scored.sort(key=lambda x: -x[1])
        picked = [
            slug for slug, score in scored[: cfg["max_tags"]]
            if score >= cfg["threshold"]
        ]
        if not picked and cfg["keep_top1"] and scored:
            picked = [scored[0][0]]
        result[dimension] = picked
    return result


def retag_articles(articles: list[Article]) -> int:
    """
    Overwrite the content-dimension tags of each article in place with
    per-article tags. Regions are preserved. Never raises — on any
    failure the articles keep their source-default tags.

    Returns the number of articles re-tagged.
    """
    if not articles:
        return 0
    try:
        texts = [_article_text(a) for a in articles]
        embeddings = _encode(texts)
        for article, embedding in zip(articles, embeddings):
            tags = tags_for_text(embedding)
            for dimension, field in _DIMENSION_FIELD.items():
                setattr(article, field, tags[dimension])
        return len(articles)
    except Exception:
        log.exception("auto_tagger: per-article tagging failed; keeping source-default tags")
        return 0
