"""
Vector store backed by Postgres + pgvector.

Reads and writes from the backend's `articles` table (with the `embedding`
column added by data engineering). This is the single source of truth for
article embeddings — the same DB that holds users, preferences, and digests.

Method signatures match the previous ChromaDB implementation so
`pipeline.py` continues to work without changes.
"""
from __future__ import annotations

import os
import hashlib
from typing import Iterable

import structlog
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker, Session
from sentence_transformers import SentenceTransformer

from src.models import Article  # LLM team's dataclass (NOT the ORM model)

log = structlog.get_logger()

# 384-dim model = matches the Vector(384) column on backend.app.models.Article
_EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_DEFAULT_DB_URL = "postgresql+psycopg://mainews:mainews_dev@localhost:5432/mainews"


def _content_hash(article: Article) -> str:
    """Stable hash of title+url for dedup audit and idempotent indexing."""
    h = hashlib.sha256()
    h.update((article.title or "").encode("utf-8"))
    h.update(b"|")
    h.update((article.url or "").encode("utf-8"))
    return h.hexdigest()


class ArticleVectorStore:
    """
    pgvector-backed store. Embeddings live on the `articles.embedding` column.

    Usage:
        store = ArticleVectorStore()
        store.index_articles(articles)             # writes embeddings
        results = store.retrieve(query, top_k=20)  # cosine similarity search
    """

    def __init__(self, db_url: str | None = None):
        self._db_url = db_url or os.environ.get("DATABASE_URL", _DEFAULT_DB_URL)
        self._engine = create_engine(self._db_url, pool_pre_ping=True)
        self._SessionLocal = sessionmaker(bind=self._engine, autoflush=False, expire_on_commit=False)
        # Lazy-load the embedding model on first use (saves ~200 MB at import).
        self._model: SentenceTransformer | None = None

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            log.info("vector_store.loading_model", model=_EMBEDDING_MODEL_NAME)
            self._model = SentenceTransformer(_EMBEDDING_MODEL_NAME)
        return self._model.encode(texts, convert_to_numpy=False, show_progress_bar=False)

    def index_articles(self, articles: Iterable[Article]) -> int:
        """
        Insert or update embeddings for the given articles.
        Returns the number of articles that had a new embedding written.
        Idempotent: re-running with the same articles is safe.
        """
        articles = list(articles)
        if not articles:
            return 0

        # Embed in one batch — much faster than per-article.
        texts = [f"{a.title}\n\n{a.summary or ''}" for a in articles]
        embeddings = self._embed(texts)

        written = 0
        with self._SessionLocal() as db:  # type: Session
            for article, emb in zip(articles, embeddings):
                # Match the backend Article row by URL (stable identifier).
                # If you change to matching by id, update both writers.
                result = db.execute(
                    text("""
                        UPDATE articles
                        SET embedding = :emb,
                            content_hash = :hash
                        WHERE url = :url
                          AND (embedding IS NULL OR content_hash != :hash)
                    """),
                    {
                        "emb": list(emb),
                        "hash": _content_hash(article),
                        "url": article.url,
                    },
                )
                written += result.rowcount or 0
            db.commit()

        log.info("vector_store.indexed", count=written, total=len(articles))
        return written

    def retrieve(self, query: str, top_k: int = 20) -> list[dict]:
        """
        Cosine-similarity search. Returns a list of dicts with:
            { article_id, url, title, score, source_id, published_at }
        Highest similarity first.
        """
        query_emb = self._embed([query])[0]

        with self._SessionLocal() as db:  # type: Session
            rows = db.execute(
                text("""
                    SELECT
                        id AS article_id,
                        url,
                        title,
                        source_id,
                        published_at,
                        1 - (embedding <=> :q) AS score
                    FROM articles
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> :q
                    LIMIT :k
                """),
                {"q": list(query_emb), "k": top_k},
            ).mappings().all()

        return [dict(r) for r in rows]

    def count(self) -> int:
        """Number of articles with an embedding stored."""
        with self._SessionLocal() as db:
            n = db.execute(
                text("SELECT COUNT(*) FROM articles WHERE embedding IS NOT NULL")
            ).scalar_one()
        return int(n)