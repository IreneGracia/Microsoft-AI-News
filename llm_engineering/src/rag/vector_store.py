"""
ChromaDB vector store for article embeddings.

Each article is stored as a document with its embedding.
Retrieval returns the top-k most semantically relevant articles for a query.
"""
from __future__ import annotations

from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from src.models import Article, TechCategory
from config.settings import settings


class ArticleVectorStore:
    COLLECTION_NAME = "tech_articles"

    def __init__(self, persist_dir: Optional[str] = None):
        persist_dir = persist_dir or settings.chroma_persist_dir
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._encoder = SentenceTransformer(settings.embedding_model)

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_articles(self, articles: list[Article]) -> int:
        """Add articles to the vector store. Returns number of new articles added."""
        if not articles:
            return 0

        # Check which ids are already indexed (avoid re-embedding)
        existing_ids = set(
            self._collection.get(ids=[a.id for a in articles])["ids"]
        )
        new_articles = [a for a in articles if a.id not in existing_ids]

        if not new_articles:
            return 0

        texts = [self._article_to_text(a) for a in new_articles]
        embeddings = self._encoder.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        ).tolist()

        self._collection.add(
            ids=[a.id for a in new_articles],
            embeddings=embeddings,
            documents=texts,
            metadatas=[self._article_to_metadata(a) for a in new_articles],
        )

        # Store embedding_id back on the article objects
        for a in new_articles:
            a.embedding_id = a.id

        return len(new_articles)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: int = 8,
        category_filter: Optional[list[TechCategory]] = None,
    ) -> list[tuple[Article, float]]:
        """
        Returns (article, similarity_score) pairs, highest first.
        category_filter restricts results to articles containing any of the given categories.
        """
        query_embedding = self._encoder.encode(
            [query], normalize_embeddings=True, show_progress_bar=False
        ).tolist()

        where = None
        if category_filter:
            # Chroma supports $in for array containment via metadata field
            # We store categories as a comma-separated string for simplicity
            where = {
                "categories": {
                    "$in": [c.value for c in category_filter]
                }
            }

        results = self._collection.query(
            query_embeddings=query_embedding,
            n_results=min(top_k, self._collection.count() or 1),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        articles_with_scores: list[tuple[Article, float]] = []
        for i, metadata in enumerate(results["metadatas"][0]):
            distance = results["distances"][0][i]
            similarity = 1.0 - distance  # cosine distance → similarity
            article = self._metadata_to_article(metadata, results["documents"][0][i])
            articles_with_scores.append((article, round(similarity, 4)))

        return articles_with_scores

    def count(self) -> int:
        return self._collection.count()

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _article_to_text(article: Article) -> str:
        return f"{article.title}\n\n{article.content[:1500]}"

    @staticmethod
    def _article_to_metadata(article: Article) -> dict:
        return {
            "id": article.id,
            "url": article.url,
            "title": article.title,
            "source": article.source,
            "published_at": article.published_at.isoformat(),
            # Store first category as string (Chroma metadata is flat)
            "categories": article.categories[0].value if article.categories else "other",
        }

    @staticmethod
    def _metadata_to_article(metadata: dict, document: str) -> Article:
        from datetime import datetime
        return Article(
            id=metadata["id"],
            url=metadata["url"],
            title=metadata["title"],
            source=metadata["source"],
            published_at=datetime.fromisoformat(metadata["published_at"]),
            content=document,
            categories=[TechCategory(metadata.get("categories", "other"))],
        )
