"""
/me/folders — topic folders with persistent threads.

GET    /me/folders              → list user's folders (with threads)
POST   /me/folders              → create a folder
PATCH  /me/folders/{id}         → rename / change topics / frequency
DELETE /me/folders/{id}         → delete folder + soft-delete its threads
POST   /me/folders/{id}/threads → create a new thread (ChatSession) in a folder
DELETE /me/folders/{id}/threads/{session_id} → remove thread from folder
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import current_user, get_db
from app.errors import problem
from app.models import ChatSession, User
from app.models.folder import UserFolder, UserFolderThread

router = APIRouter(prefix="/me/folders", tags=["folders"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─── Schemas ──────────────────────────────────────────────────────────────


class FolderThreadOut(BaseModel):
    id: str
    title: str | None
    time: str


class FolderOut(BaseModel):
    id: str
    name: str
    topics: list[str]
    frequency: str
    keywords: list[str]
    threads: list[FolderThreadOut]


class FolderIn(BaseModel):
    name: str
    topics: list[str] = []
    frequency: str = "daily"
    keywords: list[str] = []


class FolderPatch(BaseModel):
    name: str | None = None
    topics: list[str] | None = None
    frequency: str | None = None
    keywords: list[str] | None = None


class ThreadIn(BaseModel):
    title: str | None = None


# ─── Helpers ──────────────────────────────────────────────────────────────


def _load_folder(db: Session, user: User, folder_id: str) -> UserFolder:
    folder = db.get(UserFolder, folder_id)
    if folder is None or folder.user_id != user.id:
        raise problem(status=404, title="Folder not found")
    return folder


def _folder_to_out(db: Session, folder: UserFolder) -> FolderOut:
    threads = (
        db.query(ChatSession)
        .join(UserFolderThread, UserFolderThread.session_id == ChatSession.id)
        .filter(
            UserFolderThread.folder_id == folder.id,
            ChatSession.deleted_at.is_(None),
        )
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return FolderOut(
        id=folder.id,
        name=folder.name,
        topics=json.loads(folder.topics_json),
        frequency=folder.frequency,
        keywords=json.loads(folder.keywords_json),
        threads=[
            FolderThreadOut(
                id=s.id,
                title=s.title,
                time=s.updated_at.strftime("%-d %b") if s.updated_at else "",
            )
            for s in threads
        ],
    )


# ─── Endpoints ────────────────────────────────────────────────────────────


@router.get("", response_model=list[FolderOut])
def list_folders(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[FolderOut]:
    folders = (
        db.query(UserFolder)
        .filter(UserFolder.user_id == user.id)
        .order_by(UserFolder.created_at)
        .all()
    )
    return [_folder_to_out(db, f) for f in folders]


@router.post("", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
def create_folder(
    body: FolderIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> FolderOut:
    folder = UserFolder(
        user_id=user.id,
        name=body.name,
        topics_json=json.dumps(body.topics),
        frequency=body.frequency,
        keywords_json=json.dumps(body.keywords),
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return _folder_to_out(db, folder)


@router.patch("/{folder_id}", response_model=FolderOut)
def patch_folder(
    folder_id: str,
    body: FolderPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> FolderOut:
    folder = _load_folder(db, user, folder_id)
    if body.name is not None:
        folder.name = body.name
    if body.topics is not None:
        folder.topics_json = json.dumps(body.topics)
    if body.frequency is not None:
        folder.frequency = body.frequency
    if body.keywords is not None:
        folder.keywords_json = json.dumps(body.keywords)
    db.commit()
    return _folder_to_out(db, folder)


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_folder(
    folder_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    folder = _load_folder(db, user, folder_id)
    # Soft-delete all linked sessions before removing the folder
    session_ids = [ft.session_id for ft in folder.folder_threads]
    if session_ids:
        (
            db.query(ChatSession)
            .filter(ChatSession.id.in_(session_ids))
            .update({"deleted_at": _utcnow()}, synchronize_session=False)
        )
    db.delete(folder)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{folder_id}/threads", response_model=FolderThreadOut, status_code=status.HTTP_201_CREATED)
def create_thread(
    folder_id: str,
    body: ThreadIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> FolderThreadOut:
    folder = _load_folder(db, user, folder_id)
    session = ChatSession(user_id=user.id, title=body.title)
    db.add(session)
    db.flush()
    db.add(UserFolderThread(folder_id=folder.id, session_id=session.id))
    db.commit()
    db.refresh(session)
    return FolderThreadOut(
        id=session.id,
        title=session.title,
        time="Now",
    )


@router.put("/{folder_id}/threads/{session_id}", response_model=FolderThreadOut)
def attach_thread(
    folder_id: str,
    session_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> FolderThreadOut:
    """
    Attach an EXISTING chat session to a folder (drag & drop in the UI).
    Move semantics: a chat lives in at most one folder, so any previous
    folder link is removed first. Idempotent.
    """
    folder = _load_folder(db, user, folder_id)
    sess = db.get(ChatSession, session_id)
    if sess is None or sess.user_id != user.id or sess.deleted_at is not None:
        raise problem(status=404, title="Session not found")
    db.query(UserFolderThread).filter(
        UserFolderThread.session_id == session_id
    ).delete(synchronize_session=False)
    db.add(UserFolderThread(folder_id=folder.id, session_id=session_id))
    db.commit()
    return FolderThreadOut(
        id=sess.id,
        title=sess.title,
        time=sess.updated_at.strftime("%-d %b") if sess.updated_at else "Now",
    )


@router.delete(
    "/{folder_id}/threads/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_thread(
    folder_id: str,
    session_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    folder = _load_folder(db, user, folder_id)
    link = db.get(UserFolderThread, (folder.id, session_id))
    if link is not None:
        db.delete(link)
        sess = db.get(ChatSession, session_id)
        if sess and sess.user_id == user.id:
            sess.deleted_at = _utcnow()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
