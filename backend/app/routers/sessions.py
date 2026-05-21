"""
/me/sessions/* — chat session CRUD + streaming message POST.

Implements docs/api.md §3.5 and the SSE protocol in §4.

Scope here is the **API surface**, not the LLM. The streaming POST emits
a deterministic placeholder reply that follows the real event protocol
(turn_start → token → citation → token → turn_end) so the frontend can
build against it. Backend Dev 2 + LLM Engineer wire the real RAG +
Azure OpenAI streaming in behind the same surface.
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.deps import current_user, get_db
from app.errors import problem
from app.models import Article, ChatSession, ChatTurn, User
from app.pagination import Page, PageInfo, decode_cursor, encode_cursor
from app.schemas.chat import (
    MessageIn,
    MessageOut,
    SessionCreate,
    SessionOut,
    SessionWithMessages,
)
from app.schemas.content import Citation

router = APIRouter(prefix="/me/sessions", tags=["chat"])


# ─── Helpers ──────────────────────────────────────────────────────────────


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _load_session(db: Session, user: User, session_id: str) -> ChatSession:
    """Fetch a session, scoped to the caller. 404 (not 403) on mismatch."""
    sess = db.get(ChatSession, session_id)
    if sess is None or sess.user_id != user.id or sess.deleted_at is not None:
        raise problem(status=404, title="Session not found")
    return sess


def _turn_to_out(db: Session, turn: ChatTurn) -> MessageOut:
    """Materialize a stored turn into the wire shape, resolving citations."""
    try:
        cite_refs = json.loads(turn.citations_json or "[]")
    except (ValueError, TypeError):
        cite_refs = []
    article_ids = [c["article_id"] for c in cite_refs if isinstance(c, dict) and "article_id" in c]
    citations: list[Citation] = []
    if article_ids:
        articles = {
            a.id: a
            for a in db.query(Article).filter(Article.id.in_(article_ids)).all()
        }
        for ref in cite_refs:
            a = articles.get(ref.get("article_id"))
            if a is None:
                continue
            citations.append(
                Citation(
                    article_id=a.id,
                    title=a.title,
                    source=a.source.name if a.source else "",
                    url=a.url,
                    published_at=a.published_at,
                )
            )
    return MessageOut(
        id=turn.id,
        role=turn.role,  # type: ignore[arg-type]  # validated by DB convention
        content=turn.content,
        citations=citations,
        created_at=turn.created_at,
    )


# ─── Session CRUD ─────────────────────────────────────────────────────────


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_session(
    body: SessionCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ChatSession:
    """Create an empty session. Title optional — derived from first message if absent."""
    sess = ChatSession(user_id=user.id, title=body.title)
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


@router.get("", response_model=Page[SessionOut])
def list_sessions(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> Page[SessionOut]:
    """List the caller's recent sessions, newest-updated first."""
    after_id = decode_cursor(cursor)

    q = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.id, ChatSession.deleted_at.is_(None))
        .order_by(desc(ChatSession.updated_at), desc(ChatSession.id))
    )

    if after_id:
        anchor = db.query(ChatSession.updated_at).filter(ChatSession.id == after_id).first()
        if anchor is not None:
            q = q.filter(
                (ChatSession.updated_at < anchor[0])
                | ((ChatSession.updated_at == anchor[0]) & (ChatSession.id < after_id))
            )

    rows = q.limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    data = [SessionOut.model_validate(r) for r in rows]
    next_cursor = encode_cursor(rows[-1].id) if has_more and rows else None
    return Page(data=data, page=PageInfo(next_cursor=next_cursor, limit=limit))


@router.get("/{session_id}", response_model=SessionWithMessages)
def get_session(
    session_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> SessionWithMessages:
    """Resume — session metadata plus full message history."""
    sess = _load_session(db, user, session_id)
    messages = [_turn_to_out(db, t) for t in sess.turns]
    return SessionWithMessages(
        id=sess.id,
        title=sess.title,
        created_at=sess.created_at,
        updated_at=sess.updated_at,
        messages=messages,
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Soft-delete (GDPR-aligned). Hard delete cascades on DELETE /me."""
    sess = _load_session(db, user, session_id)
    sess.deleted_at = _utcnow()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── Message history (non-streaming) ──────────────────────────────────────


@router.get("/{session_id}/messages", response_model=Page[MessageOut])
def list_messages(
    session_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> Page[MessageOut]:
    """Paginate the full history. Useful for very long sessions."""
    sess = _load_session(db, user, session_id)
    after_id = decode_cursor(cursor)

    q = (
        db.query(ChatTurn)
        .filter(ChatTurn.session_id == sess.id)
        .order_by(ChatTurn.created_at, ChatTurn.id)
    )
    if after_id:
        anchor = db.query(ChatTurn.created_at).filter(ChatTurn.id == after_id).first()
        if anchor is not None:
            q = q.filter(
                (ChatTurn.created_at > anchor[0])
                | ((ChatTurn.created_at == anchor[0]) & (ChatTurn.id > after_id))
            )

    rows = q.limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    data = [_turn_to_out(db, r) for r in rows]
    next_cursor = encode_cursor(rows[-1].id) if has_more and rows else None
    return Page(data=data, page=PageInfo(next_cursor=next_cursor, limit=limit))


# ─── Streaming POST ───────────────────────────────────────────────────────


def _sse(event: str, data: dict) -> bytes:
    """Format one SSE frame. Trailing blank line is the event boundary."""
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n".encode()


def _stub_reply_tokens(user_text: str) -> list[str]:
    """
    Placeholder token stream. Real impl swaps this for an Azure OpenAI
    streaming call once Backend Dev 2 + LLM Engineer land the RAG path.

    Splitting into chunks (not single tokens) keeps the demo readable; the
    real provider chunks however it chunks and the frontend doesn't care.
    """
    return [
        "Thanks for asking about ",
        f"\"{user_text[:80]}\". ",
        "Here is a grounded answer drawing on recent coverage",
    ]


@router.post("/{session_id}/messages")
def post_message(
    session_id: str,
    body: MessageIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> StreamingResponse:
    """
    Stream an assistant reply over SSE (docs/api.md §4).

    Steps:
      1. Validate session ownership.
      2. Persist the user turn.
      3. Stream `turn_start` → tokens (interleaved with `citation` events)
         → `turn_end`.
      4. Persist the assistant turn after the stream completes.

    The `Idempotency-Key` header is **accepted** but not yet enforced
    (api.md AQ4 — "required or just honored?" is still open). When we
    settle it, the dedup table goes into Postgres or Redis and this
    handler looks up the cached response before generating.
    """
    sess = _load_session(db, user, session_id)

    # 1. Persist the user turn synchronously so it can't be lost on disconnect.
    user_turn = ChatTurn(
        session_id=sess.id,
        role="user",
        content=body.content,
        citations_json="[]",
    )
    db.add(user_turn)

    # Backfill session title from first user message if empty.
    if not sess.title:
        sess.title = body.content[:80]
    sess.updated_at = _utcnow()
    db.commit()
    db.refresh(user_turn)

    # 2. Pick a "citation" — most recent article in the DB so the frontend
    # has something to render. Real RAG picks via retrieval.
    #
    # We materialize the article's fields into a plain dict *now*, before
    # the StreamingResponse body iterator starts running. FastAPI closes
    # the request-scoped DB session as soon as this handler returns, so any
    # ORM access from inside `event_stream` would hit DetachedInstanceError
    # on lazy relationships (e.g. `article.source`).
    sample_article = (
        db.query(Article).order_by(desc(Article.published_at)).first()
    )
    sample_citation: dict | None = None
    if sample_article is not None:
        sample_citation = {
            "article_id": sample_article.id,
            "title": sample_article.title,
            "source": sample_article.source.name if sample_article.source else "",
            "url": sample_article.url,
            "published_at": sample_article.published_at.isoformat(),
        }

    # Capture the session id as a plain string for the same reason.
    sess_id = sess.id
    user_content = body.content

    def event_stream():
        # Generate the assistant turn ID up-front so turn_start matches the
        # row we eventually persist.
        from app.models.chat import _new_message_id  # local import: avoid widening top-level deps
        msg_id = _new_message_id()

        yield _sse("turn_start", {"message_id": msg_id})

        tokens = _stub_reply_tokens(user_content)
        for tok in tokens:
            yield _sse("token", {"content": tok})

        citations_for_db: list[dict] = []
        if sample_citation is not None:
            yield _sse("citation", {"index": 1, **sample_citation})
            yield _sse("token", {"content": " [1]."})
            citations_for_db = [{"article_id": sample_citation["article_id"], "index": 1}]
        else:
            yield _sse("token", {"content": "."})

        # Persist the assistant turn at end-of-stream. We open a fresh
        # session because the request-scoped one closes when the response
        # generator starts streaming.
        from app.db.session import SessionLocal
        with SessionLocal() as write_db:
            write_db.add(
                ChatTurn(
                    id=msg_id,
                    session_id=sess_id,
                    role="assistant",
                    content="".join(tokens) + (" [1]." if sample_citation else "."),
                    citations_json=json.dumps(citations_for_db),
                    prompt_tokens=0,  # placeholders — LLME wires real counts
                    completion_tokens=0,
                )
            )
            touched = write_db.get(ChatSession, sess_id)
            if touched is not None:
                touched.updated_at = _utcnow()
            write_db.commit()

        yield _sse(
            "turn_end",
            {
                "message_id": msg_id,
                # Placeholder telemetry. LLME wires real tokenizer counts here.
                "tokens_used": {"prompt": 0, "completion": 0},
            },
        )

    # `text/event-stream` + no buffering tells nginx/Container Apps to flush
    # frames immediately. `X-Accel-Buffering` is the nginx convention.
    response_headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    if idempotency_key:
        # Echo it back so clients can correlate. Real enforcement TBD.
        response_headers["Idempotency-Key"] = idempotency_key

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=response_headers,
    )
