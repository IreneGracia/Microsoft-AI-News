"""
Adapter layer between backend ORM types and the LLM pipeline's Pydantic
types. Three directions:

  user_to_profile(user, prefs)              -> pipeline UserProfile (input)
  persist_digest(db, user, newsletter)      -> Digest + DigestItems + Articles + ArticleTags (output)
  chat_reply(user, prefs, query, history)   -> (answer, citations, token_usage) for SSE streaming (L2)

The pipeline now speaks the backend's multi-dimensional tag vocabulary
directly (topic / business / regulation / regional slugs), so this
adapter is a thin shape-translator — no taxonomy collapse, no lossy
mappings.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import (
    Article as ArticleORM,
    ArticleTag as ArticleTagORM,
    Digest as DigestORM,
    DigestItem as DigestItemORM,
    Preferences as PreferencesORM,
    Source as SourceORM,
    User as UserORM,
)

from app.pipeline.models import (
    Article as PipelineArticle,
    DigestFrequency,
    NewsletterDigest,
    TonePreference,
    UserProfile,
)

log = logging.getLogger(__name__)


def user_to_profile(user: UserORM, prefs: PreferencesORM) -> UserProfile:
    """
    Build a pipeline UserProfile from backend User + Preferences rows.

    Tag lists round-trip verbatim — the pipeline uses the same slug
    vocabulary the backend stores.
    """
    return UserProfile(
        user_id=user.id,
        name=user.display_name or user.email.split("@", 1)[0],
        email=user.email,
        role=prefs.role,
        topic_tags=_safe_json_list(prefs.topics_json),
        business_tags=_safe_json_list(prefs.business_tags_json),
        regulation_tags=_safe_json_list(prefs.regulation_tags_json),
        regions=_safe_json_list(prefs.regions_json),
        companies_to_track=[],  # not modelled in backend prefs yet
        tone=_tone(prefs.tone),
        digest_frequency=_frequency(prefs.frequency),
        topic_weights={},
    )


def persist_digest(
    db: Session,
    user: UserORM,
    newsletter: NewsletterDigest,
    fallback_source_id: str,
) -> DigestORM:
    """
    Turn the pipeline's in-memory NewsletterDigest into ORM rows.

    For each article in the newsletter we either reuse an existing Article
    row (matched by URL) or insert a new one + its multi-dimensional
    ArticleTag rows. Digest + DigestItem rows are always new; idempotency
    lives in _find_eligible_users.

    Caller owns the commit; this function flushes but does not commit.
    """
    digest = DigestORM(user_id=user.id, generated_at=newsletter.generated_at)
    db.add(digest)
    db.flush()

    tone = (user.preferences.tone if user.preferences else None) or "balanced"
    length = (user.preferences.length if user.preferences else None) or "standard"

    valid_tags = _load_valid_tag_set(db)

    for entry in newsletter.articles:
        article_row = _upsert_article(db, entry.article, fallback_source_id, valid_tags)
        db.add(
            DigestItemORM(
                digest_id=digest.id,
                article_id=article_row.id,
                rank=entry.rank,
                summary=entry.summary,
                tone=tone,
                length=length,
                citations_json=json.dumps([]),
            )
        )

    return digest


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _upsert_article(
    db: Session,
    pipeline_article: PipelineArticle,
    fallback_source_id: str,
    valid_tags: set[tuple[str, str]],
) -> ArticleORM:
    """Match on URL; insert if missing. Returns the persisted ArticleORM row."""
    existing = db.query(ArticleORM).filter(ArticleORM.url == pipeline_article.url).first()
    if existing is not None:
        if pipeline_article.content and not existing.body:
            existing.body = pipeline_article.content
        return existing

    source_id = _resolve_source_id(db, pipeline_article.source, fallback_source_id)
    row = ArticleORM(
        source_id=source_id,
        title=pipeline_article.title,
        url=pipeline_article.url,
        author=None,
        published_at=_to_aware_utc(pipeline_article.published_at),
        extract=pipeline_article.summary or (pipeline_article.content[:280] if pipeline_article.content else None),
        body=pipeline_article.content,
        image_url=pipeline_article.image_url,
    )
    db.add(row)
    db.flush()

    # Persist multi-dimensional tags. Anything not in the seeded taxonomy
    # is dropped rather than violating the (dimension, slug) FK into `tags`.
    for dimension, slugs in (
        ("topic", pipeline_article.topic_tags),
        ("business", pipeline_article.business_tags),
        ("regulation_policy", pipeline_article.regulation_tags),
        ("regional", pipeline_article.regions),
    ):
        for slug in slugs:
            if (dimension, slug) not in valid_tags:
                continue
            db.add(ArticleTagORM(article_id=row.id, dimension=dimension, slug=slug))

    return row


def _resolve_source_id(db: Session, source_name: str, fallback_source_id: str) -> str:
    if not source_name:
        return fallback_source_id
    row = db.query(SourceORM).filter(SourceORM.name == source_name).first()
    return row.id if row else fallback_source_id


def _load_valid_tag_set(db: Session) -> set[tuple[str, str]]:
    """All (dimension, slug) pairs currently in the seeded taxonomy."""
    from app.models import Tag
    return {(t.dimension, t.slug) for t in db.query(Tag.dimension, Tag.slug).all()}


def _safe_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def _tone(value: str | None) -> TonePreference:
    try:
        return TonePreference(value) if value else TonePreference.TECHNICAL
    except ValueError:
        return TonePreference.TECHNICAL


def _frequency(value: str | None) -> DigestFrequency:
    try:
        return DigestFrequency(value) if value else DigestFrequency.WEEKLY
    except ValueError:
        return DigestFrequency.WEEKLY


def _to_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ----------------------------------------------------------------------
# Chat (L2 — used by /me/sessions/{id}/messages SSE handler)
# ----------------------------------------------------------------------


def chat_reply(
    db: Session,
    user: UserORM,
    prefs: PreferencesORM,
    query: str,
    history: list[tuple[str, str]],
) -> tuple[str, list[dict], int, int]:
    """
    Run the chatbot against the user's question and return:

        (answer_text, citations, prompt_tokens, completion_tokens)

    `history` is a list of (role, content) tuples already trimmed by the
    caller — the chatbot trims again internally but we keep it short to
    bound prompt size.

    `citations` is a list of plain dicts the SSE handler can serialize:
        [{"index": 1, "article_id": "...", "title": "...", "source": "...",
          "url": "...", "published_at": "ISO-Z"}, ...]
    Citation `article_id` is matched against the backend's `articles` table
    by URL — articles the pipeline returns that we've never seen are
    skipped from citations (they'd have no stable id for the frontend
    to deep-link).

    Raises RuntimeError on import / construction failure so the caller can
    fall back to a stub stream instead of streaming nothing.
    """
    try:
        from app.pipeline.llm.chatbot import Chatbot
        from app.pipeline.models import ChatMessage
    except ImportError as exc:
        raise RuntimeError(f"chat pipeline unavailable: {exc}") from exc

    chatbot = Chatbot()

    profile = user_to_profile(user, prefs)
    chat_history = [ChatMessage(role=r, content=c) for r, c in history]

    response = chatbot.chat(query=query, user=profile, history=chat_history)

    # Map pipeline source articles back to our ArticleORM rows by URL so
    # citations carry our internal `article_id`s (frontend deep-link target).
    citations: list[dict] = []
    if response.sources:
        urls = [a.url for a in response.sources if a.url]
        by_url = {
            row.url: row
            for row in db.query(ArticleORM).filter(ArticleORM.url.in_(urls)).all()
        }
        for idx, src in enumerate(response.sources, start=1):
            row = by_url.get(src.url)
            if row is None:
                continue
            citations.append(
                {
                    "index": idx,
                    "article_id": row.id,
                    "title": row.title,
                    "source": row.source.name if row.source else "",
                    "url": row.url,
                    "published_at": row.published_at.isoformat() if row.published_at else None,
                    "image_url": row.image_url,
                }
            )

    prompt_tokens = getattr(response.token_cost, "input_tokens", 0) or 0
    completion_tokens = getattr(response.token_cost, "output_tokens", 0) or 0
    return response.answer, citations, prompt_tokens, completion_tokens


def stream_chat_reply(
    db: Session,
    user: UserORM,
    prefs: PreferencesORM,
    query: str,
    history: list[tuple[str, str]],
):
    """
    Streaming chat. Yields events for the SSE handler:

        ('token',  str)                                  — each text chunk
        ('done',   citations, prompt_tokens, comp_tokens) — once, at end

    Raises RuntimeError on import / construction failure so the caller
    can fall back to the stub stream.
    """
    try:
        from app.pipeline.llm.chatbot import Chatbot
        from app.pipeline.models import ChatMessage
    except ImportError as exc:
        raise RuntimeError(f"chat pipeline unavailable: {exc}") from exc

    chatbot = Chatbot()
    profile = user_to_profile(user, prefs)
    chat_history = [ChatMessage(role=r, content=c) for r, c in history]

    sources = []
    for event_type, payload in chatbot.stream_chat(query=query, user=profile, history=chat_history):
        if event_type == "sources":
            sources = payload
        elif event_type == "token":
            yield "token", payload
        elif event_type == "done":
            usage = payload
            citations = _resolve_citations(db, sources)
            prompt_tokens = getattr(usage, "input_tokens", 0) or 0
            completion_tokens = getattr(usage, "output_tokens", 0) or 0
            yield "done", citations, prompt_tokens, completion_tokens


def _resolve_citations(db: Session, sources: list) -> list[dict]:
    """Map pipeline source articles to backend ArticleORM rows for citation links."""
    if not sources:
        return []
    urls = [a.url for a in sources if a.url]
    by_url = {
        row.url: row
        for row in db.query(ArticleORM).filter(ArticleORM.url.in_(urls)).all()
    }
    citations: list[dict] = []
    for idx, src in enumerate(sources, start=1):
        row = by_url.get(src.url)
        if row is None:
            continue
        citations.append({
            "index": idx,
            "article_id": row.id,
            "title": row.title,
            "source": row.source.name if row.source else "",
            "url": row.url,
            "published_at": row.published_at.isoformat() if row.published_at else None,
            "image_url": row.image_url,
        })
    return citations
