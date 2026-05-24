"""
Semantic deduplication of news articles.

Two-pass strategy:
1. URL-hash exact dedup (free, catches reposts)
2. Embedding cosine similarity — cluster near-duplicate stories,
   keep the highest-quality source (ranked by source tier list)
"""
from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from src.models import Article
from config.settings import settings

# Quality tiers keyed by source name (matches sources.json "name" field, lowercased).
# Higher = prefer this source when deduplicating a story cluster.
# Primary sources (company blogs, government) are tier 5 — cite with highest confidence.
_SOURCE_TIER: dict[str, int] = {
    # Primary / official
    "mit technology review": 5,
    "reuters technology": 5,
    "bloomberg technology": 5,
    "eu parliament": 5,
    "edpb (european data protection board)": 5,
    "eu commission press corner": 5,
    "google blog": 5,
    "aws news blog": 5,
    "openai blog": 5,
    "anthropic blog": 5,
    "nvidia blog": 5,
    "github blog": 5,
    "arxiv — cs.ai": 5,
    "arxiv — cs.lg": 5,
    # Tier 4 — high-trust journalism
    "techcrunch": 4,
    "wired": 4,
    "the verge": 4,
    "ars technica (tech policy)": 4,
    "politico europe": 4,
    "politico us": 4,
    "the economist": 4,
    "the register": 4,
    "stat news": 4,
    # Tier 3 — solid regional/specialist
    "venturebeat": 3,
    "euractiv": 3,
    "geekwire": 3,
    "rest of world": 3,
    "sifted": 3,
    "tech policy press": 3,
    "silicon republic": 3,
    "the recursive": 3,
    # Tier 2 — aggregators and community
    "hacker news": 2,
    "gdelt": 2,
}

_DEDUP_SIMILARITY_THRESHOLD = 0.88  # cosine similarity above this = same story


def _source_tier(source: str) -> int:
    return _SOURCE_TIER.get(source.lower(), 1)


class ArticleDeduplicator:
    """
    Uses a lightweight sentence encoder to find near-duplicate articles.
    On first call the model is downloaded (~80 MB) and cached locally.
    """

    def __init__(self, similarity_threshold: float = _DEDUP_SIMILARITY_THRESHOLD):
        self.threshold = similarity_threshold
        self._model: SentenceTransformer | None = None

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(settings.embedding_model)
        return self._model

    def _embed(self, texts: list[str]) -> np.ndarray:
        model = self._get_model()
        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.array(embeddings)

    def deduplicate(self, articles: list[Article]) -> list[Article]:
        if len(articles) <= 1:
            return articles

        # Step 1: exact id dedup
        seen_ids: set[str] = set()
        unique: list[Article] = []
        for a in articles:
            if a.id not in seen_ids:
                seen_ids.add(a.id)
                unique.append(a)

        if len(unique) <= 1:
            return unique

        # Step 2: semantic clustering
        texts = [f"{a.title}. {a.content[:300]}" for a in unique]
        embeddings = self._embed(texts)

        # Greedy clustering: assign each article to first cluster it's similar to
        clusters: list[list[int]] = []
        cluster_centroid: list[np.ndarray] = []

        for i, emb in enumerate(embeddings):
            assigned = False
            for j, centroid in enumerate(cluster_centroid):
                similarity = float(np.dot(emb, centroid))
                if similarity >= self.threshold:
                    clusters[j].append(i)
                    # Update centroid (running mean)
                    n = len(clusters[j])
                    cluster_centroid[j] = (centroid * (n - 1) + emb) / n
                    assigned = True
                    break
            if not assigned:
                clusters.append([i])
                cluster_centroid.append(emb.copy())

        # Pick best article from each cluster (highest source tier, then most recent)
        result: list[Article] = []
        for cluster in clusters:
            best = max(
                cluster,
                key=lambda i: (_source_tier(unique[i].source), unique[i].published_at),
            )
            result.append(unique[best])

        return result
