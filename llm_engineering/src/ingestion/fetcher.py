"""
RSS-based news fetcher.

Two-step content pipeline:
  1. feedparser parses the RSS feed → title, url, published_date, summary/description
  2. For sources with content_quality="excerpts", httpx + BeautifulSoup fetches the
     full article body so the RAG embeddings get rich content, not just a teaser.

arXiv feeds are high-volume — a keyword relevance filter is applied before returning.

Incremental ingestion: per-source watermarks are persisted to fetch_state.json so
reruns never re-ingest the same article twice (same pattern as data_engineering/).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

import feedparser
import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from src.models import Article, TechCategory, UserProfile
from src.ingestion.source_registry import Source, get_sources_for_user, load_sources

_ARXIV_KEYWORDS = {
    "llm", "large language model", "transformer", "foundation model",
    "generative ai", "diffusion", "neural", "reinforcement learning",
    "multimodal", "agent", "rag", "retrieval", "fine-tun",
}

_CONTENT_TAGS = ["p", "h1", "h2", "h3", "li"]

_STATE_FILE = Path(__file__).parent.parent.parent / "data" / "fetch_state.json"


# ---------------------------------------------------------------------------
# Watermark state (mirrors data_engineering/rss_fetcher.py pattern)
# ---------------------------------------------------------------------------

def _load_state(source_ids: list[str]) -> dict[str, datetime | None]:
    defaults: dict[str, datetime | None] = {sid: None for sid in source_ids}
    if not _STATE_FILE.exists():
        return defaults
    try:
        raw = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("state file is not a JSON object")
    except (json.JSONDecodeError, ValueError, OSError):
        return defaults
    result = dict(defaults)
    for sid, iso in raw.items():
        if iso:
            try:
                result[sid] = datetime.fromisoformat(iso)
            except ValueError:
                pass
    return result


def _save_state(state: dict[str, datetime | None]) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STATE_FILE.with_suffix(".json.tmp")
    serialized = {k: v.isoformat() if v else None for k, v in state.items()}
    tmp.write_text(json.dumps(serialized, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(_STATE_FILE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _parse_date(entry: dict) -> datetime:
    for field in ("published", "updated"):
        raw = entry.get(field)
        if raw:
            try:
                return parsedate_to_datetime(raw).astimezone(timezone.utc).replace(tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def _entry_to_text(entry: dict) -> str:
    for field in ("content", "summary", "description"):
        val = entry.get(field)
        if isinstance(val, list) and val:
            return BeautifulSoup(val[0].get("value", ""), "html.parser").get_text(" ", strip=True)
        if isinstance(val, str) and val:
            return BeautifulSoup(val, "html.parser").get_text(" ", strip=True)
    return ""


def _is_arxiv_relevant(title: str, abstract: str) -> bool:
    text = f"{title} {abstract}".lower()
    return any(kw in text for kw in _ARXIV_KEYWORDS)


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=4))
async def _fetch_full_body(url: str, timeout: float = 10.0) -> str:
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "MAI-News-Bot/1.0 (research project)"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "aside", "header"]):
                tag.decompose()
            paragraphs = soup.find_all(_CONTENT_TAGS)
            text = " ".join(p.get_text(" ", strip=True) for p in paragraphs)
            return re.sub(r"\s+", " ", text).strip()[:4000]
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Adapter: data_engineering raw dict → Article
# ---------------------------------------------------------------------------

def article_from_de_dict(raw: dict) -> Article | None:
    """
    Convert a dict produced by data_engineering/rss_fetcher.py into an Article.
    Returns None if the dict is missing required fields.
    """
    from src.ingestion.source_registry import get_source_by_id

    url = raw.get("url", "")
    title = raw.get("title", "")
    if not url or not title:
        return None

    source = get_source_by_id(raw.get("source_id", ""))
    source_name = source.name if source else raw.get("source_id", "unknown")
    source_type = source.source_type if source else "secondary"
    categories = source.categories if source else [TechCategory.OTHER]

    pub_date_raw = raw.get("pub_date", "")
    try:
        published_at = datetime.fromisoformat(pub_date_raw)
    except (ValueError, TypeError):
        published_at = datetime.now(timezone.utc)

    return Article(
        id=_make_id(url),
        url=url,
        title=title,
        source=source_name,
        published_at=published_at,
        content=raw.get("summary", ""),
        categories=categories,
        source_type=source_type,
    )


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------

class RSSFetcher:
    """
    Fetches articles from RSS feeds defined in config/sources.json.
    Persists per-source watermarks to data/fetch_state.json so each run
    only processes articles newer than the last successful poll.
    """

    async def fetch_source(
        self,
        source: Source,
        max_articles: int = 20,
        since: datetime | None = None,
    ) -> list[Article]:
        """Parse one RSS feed and return Article objects newer than `since`."""
        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(None, feedparser.parse, source.rss_url)

        entries = feed.entries[:max_articles]
        articles: list[Article] = []
        full_fetch_tasks: list[tuple[int, str]] = []

        for entry in entries:
            url = entry.get("link", "")
            if not url:
                continue

            title = entry.get("title", "No title")
            content = _entry_to_text(entry)
            published_at = _parse_date(entry)

            # Incremental filter
            if since is not None and published_at <= since:
                continue

            if source.id.startswith("arxiv") and not _is_arxiv_relevant(title, content):
                continue

            article = Article(
                id=_make_id(url),
                url=url,
                title=title,
                source=source.name,
                published_at=published_at,
                content=content,
                categories=source.categories,
                source_type=source.source_type,
            )
            articles.append(article)

            if len(content) < 400:
                full_fetch_tasks.append((len(articles) - 1, url))

        if full_fetch_tasks:
            sem = asyncio.Semaphore(5)

            async def bounded_fetch(idx: int, url: str):
                async with sem:
                    body = await _fetch_full_body(url)
                    if body:
                        articles[idx].content = body

            await asyncio.gather(*[bounded_fetch(i, u) for i, u in full_fetch_tasks])

        return articles

    async def fetch_for_user(
        self,
        user: UserProfile,
        tiers: list[str] | None = None,
        max_per_source: int = 15,
        incremental: bool = True,
    ) -> list[Article]:
        """
        Fetch articles from all sources relevant to this user.
        When incremental=True, only articles newer than each source's last watermark
        are returned, and watermarks are updated on success.
        """
        sources = get_sources_for_user(user)
        if tiers:
            sources = [s for s in sources if s.scrape_tier in tiers]

        state = _load_state([s.id for s in sources]) if incremental else {s.id: None for s in sources}
        sem = asyncio.Semaphore(10)
        new_watermarks: dict[str, datetime] = {}

        async def fetch_one(source: Source) -> list[Article]:
            async with sem:
                try:
                    since = state.get(source.id)
                    articles = await self.fetch_source(source, max_per_source, since=since)
                    if articles:
                        new_watermarks[source.id] = max(a.published_at for a in articles)
                    return articles
                except Exception:
                    return []

        results = await asyncio.gather(*[fetch_one(s) for s in sources])

        if incremental and new_watermarks:
            updated = {**{k: v for k, v in state.items()}, **new_watermarks}
            _save_state(updated)

        all_articles: list[Article] = []
        seen_ids: set[str] = set()
        for batch in results:
            for a in batch:
                if a.id not in seen_ids:
                    seen_ids.add(a.id)
                    all_articles.append(a)

        return all_articles

    async def fetch_by_tier(
        self,
        tier: str,
        max_per_source: int = 20,
        incremental: bool = True,
    ) -> list[Article]:
        """Fetch all sources for a given scrape tier (for scheduled jobs)."""
        from src.ingestion.source_registry import get_sources_for_tier
        sources = get_sources_for_tier(tier)

        state = _load_state([s.id for s in sources]) if incremental else {s.id: None for s in sources}
        sem = asyncio.Semaphore(10)
        new_watermarks: dict[str, datetime] = {}

        async def fetch_one(source: Source) -> list[Article]:
            async with sem:
                try:
                    since = state.get(source.id)
                    articles = await self.fetch_source(source, max_per_source, since=since)
                    if articles:
                        new_watermarks[source.id] = max(a.published_at for a in articles)
                    return articles
                except Exception:
                    return []

        results = await asyncio.gather(*[fetch_one(s) for s in sources])

        if incremental and new_watermarks:
            updated = {**{k: v for k, v in state.items()}, **new_watermarks}
            _save_state(updated)

        articles: list[Article] = []
        seen: set[str] = set()
        for batch in results:
            for a in batch:
                if a.id not in seen:
                    seen.add(a.id)
                    articles.append(a)
        return articles
