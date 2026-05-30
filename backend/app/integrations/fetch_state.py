"""
Persist the RSS fetcher's per-source watermarks across Container Apps
restarts (L4).

Container Apps with scale-to-zero recycles the container between cron
fires. The fetcher (llm_engineering/src/ingestion/fetcher.py) writes
state to a JSON file on disk, which evaporates with the container.
Without this bridge, every cold start re-fetches "everything new since
beginning of time" on every source — wasteful and risks RSS rate limits.

Approach: bracket each pipeline run with restore/save. The fetcher
itself still does file I/O (no llm_engineering changes needed beyond
honouring an env var for the path); we just snapshot the file to / from
Postgres around the call.

  context-manager usage:
    with persisted_fetch_state(db, path):
        await pipeline.run_for_user(profile)

The state file path is read from FETCH_STATE_PATH (set in the Bicep env
list); falls back to /tmp/fetch_state.json which works locally too.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import KvState

log = logging.getLogger(__name__)


_KV_KEY = "rss_fetch_state"
_DEFAULT_PATH = "/tmp/fetch_state.json"  # noqa: S108 — tmp on container; same dir on Mac/Linux dev


def default_state_path() -> Path:
    """Where the fetcher reads/writes. Honour FETCH_STATE_PATH env var."""
    return Path(os.environ.get("FETCH_STATE_PATH", _DEFAULT_PATH))


def restore_to_disk(db: Session, path: Path) -> None:
    """Read the saved state from Postgres and write it to `path`."""
    row = db.get(KvState, _KV_KEY)
    if row is None:
        # No prior state — make sure no stale file is left over.
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(row.value, encoding="utf-8")


def save_from_disk(db: Session, path: Path) -> None:
    """Read the on-disk state and persist it back to Postgres."""
    if not path.exists():
        return
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        log.warning("fetch_state.save_from_disk: read failed (%s) — skipping", exc)
        return
    row = db.get(KvState, _KV_KEY)
    if row is None:
        db.add(KvState(key=_KV_KEY, value=content))
    else:
        row.value = content
    db.commit()


@contextmanager
def persisted_fetch_state(db: Session, path: Path | None = None):
    """
    Bracket a pipeline run: restore state before, save state after.

    `db` is a backend Session. The fetcher uses plain file I/O while
    inside the `with` block — we just translate the file boundary to a
    DB boundary on either side. The `path` defaults to whatever the
    fetcher will read from (FETCH_STATE_PATH or /tmp/fetch_state.json).

    Failures here are logged and swallowed — fetch state is a perf
    optimisation, never a correctness requirement. Worst case the
    fetcher fetches a few hundred extra items; the URL-dedup in the
    pipeline catches dupes on insert.
    """
    state_path = path or default_state_path()
    try:
        restore_to_disk(db, state_path)
    except Exception:
        log.exception("fetch_state.persisted_fetch_state: restore failed")
    try:
        yield state_path
    finally:
        try:
            save_from_disk(db, state_path)
        except Exception:
            log.exception("fetch_state.persisted_fetch_state: save failed")
