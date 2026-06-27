"""
Embedding wrapper for the ingestion pipeline.

Loads all-MiniLM-L6-v2 once and keeps it in memory for the lifetime of
the process.  The LLM/digest side never calls this — it reads the
pre-computed embeddings from the articles table.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
_EXPECTED_DIM = 384

_model: "SentenceTransformer | None" = None


def _get_model() -> "SentenceTransformer":
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        print(f"[embedder] loading {_MODEL_NAME} ...")
        _model = SentenceTransformer(_MODEL_NAME)
        actual_dim = (
            _model.get_embedding_dimension()
            if hasattr(_model, "get_embedding_dimension")
            else _model.get_sentence_embedding_dimension()
        )
        if actual_dim != _EXPECTED_DIM:
            raise RuntimeError(
                f"Model {_MODEL_NAME!r} produces {actual_dim}-dim vectors "
                f"but the articles table expects {_EXPECTED_DIM}. "
                "Update EMBEDDING_MODEL or recreate the table."
            )
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    """
    Embed a batch of texts.  Returns one 384-dim float list per text.
    Caller should pass `article.embed_text` (title + summary).
    """
    if not texts:
        return []
    model = _get_model()
    vecs = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return [v.tolist() for v in vecs]
