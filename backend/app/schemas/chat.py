"""
Wire-format schemas for chat resources — docs/api.md §3.5.

The streaming POST endpoint does NOT use a Pydantic response model — it
returns SSE bytes directly. The shapes below cover the non-streaming
endpoints (create session, list, history) plus the request body.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.content import Citation


class SessionCreate(BaseModel):
    """Body for POST /me/sessions — title is optional."""

    title: str | None = Field(default=None, max_length=200)


class SessionOut(BaseModel):
    """List/get response (without messages)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    """One turn in a session — user or assistant."""

    id: str
    role: Literal["user", "assistant"]
    content: str
    citations: list[Citation] = []
    created_at: datetime


class SessionWithMessages(SessionOut):
    """GET /me/sessions/{id} returns the session plus its full history."""

    messages: list[MessageOut] = []


class MessageIn(BaseModel):
    """Body for POST /me/sessions/{id}/messages — what the user typed."""

    content: str = Field(min_length=1, max_length=8000)
