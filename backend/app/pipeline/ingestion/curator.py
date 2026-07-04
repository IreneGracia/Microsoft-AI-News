"""
LLM-based article curator.

After deduplication we may have 100-400 raw articles. Before embedding them
into pgvector, we let the LLM act as an editor: send it a compact list of
titles + sources and ask it to pick the most newsworthy, diverse subset.

This kills two problems at once:
  - Low-quality articles (press releases, listicles, thinly-sourced posts)
    never hit the vector store and never appear in RAG responses.
  - Thematic redundancy: if five feeds covered the same GPT announcement,
    the curator picks the best one and drops the rest.

The curator prompt mirrors the "Jefe de Redacción" pattern from the reference
implementation — a single structured LLM call with a JSON response.
"""
from __future__ import annotations

import json
import logging

from app.pipeline.models import Article, UserProfile
from app.pipeline.llm.client import LLMClient

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a senior tech news editor for MAI, an AI-powered intelligence
platform for Microsoft employees. Your job is to select the most valuable articles
from a raw feed.

SELECTION CRITERIA (in order of importance):
1. Genuine news value — actual developments, not opinion or speculation.
2. Relevance to AI, cloud, enterprise tech, policy, and emerging technology.
3. Source quality — prefer primary sources (company blogs, official announcements,
   research papers) and top-tier journalism over aggregators.
4. Thematic diversity — if five articles cover the same story, pick the best one.
5. Recency signal — breaking developments beat follow-up commentary.

WHAT TO REJECT:
- Listicles and "top 10" posts with no real news.
- Pure opinion pieces with no new facts.
- Press release reposts (same story, weaker source than another candidate).
- Off-topic articles that slipped through the RSS filter.

Respond ONLY with a valid JSON object. No prose, no markdown fences."""

_USER_TEMPLATE = """Select the {top_n} most valuable articles from the list below.
Assign a priority score from 1 (lowest) to 10 (highest).
{reader_context}
Return exactly this JSON schema:
{{
  "selection": [
    {{"index": 0, "priority": 10}},
    ...
  ]
}}

ARTICLES:
{articles_block}"""

_READER_CONTEXT_TEMPLATE = """
READER CONTEXT — weight relevance to this specific reader above generic
newsworthiness. An article that strongly matches their interests should
outrank an equally newsworthy article that doesn't, even if the
non-matching one is bigger news in the abstract:
- Topics they follow: {topics}
- Business/industry interest: {business}
- Regions they care about: {regions}
- Role: {role}
"""


def _build_reader_context(user: "UserProfile | None") -> str:
    """Render the READER CONTEXT block, or '' if no user profile was given."""
    if user is None:
        return ""
    topics = ", ".join(t.replace("_", " ") for t in user.topic_tags) or "none specified"
    business = ", ".join(t.replace("_", " ") for t in user.business_tags) or "none specified"
    regions = ", ".join(t.replace("_", " ") for t in user.regions) or "none specified"
    role = (user.role or "unspecified").replace("_", " ")
    return _READER_CONTEXT_TEMPLATE.format(topics=topics, business=business, regions=regions, role=role)


class ArticleCurator:
    """
    Uses the configured LLM to select and rank the best articles.
    Falls back to returning all articles unchanged on any LLM failure —
    curation is a quality improvement, not a hard requirement.
    """

    def __init__(self, llm_client=None):
        self._llm = llm_client

    def _get_llm(self):
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    def curate(
        self,
        articles: list[Article],
        top_n: int = 30,
        user: UserProfile | None = None,
        min_priority: int | None = None,
    ) -> list[Article]:
        """
        Return up to `top_n` articles, sorted by LLM-assigned priority (highest first).
        If fewer articles are provided than `top_n`, all are returned as-is.

        `min_priority`, if set, additionally drops any article scoring below that
        threshold even if `top_n` hasn't been reached — so raising `top_n` widens
        the ceiling without lowering the quality floor.
        """
        if len(articles) <= top_n:
            return articles

        articles_block = "\n".join(
            f'  <article index="{i}" source="{a.source}">'
            f"<title>{a.title}</title>"
            f"<excerpt>{(a.summary or a.content)[:120]}</excerpt>"
            f"</article>"
            for i, a in enumerate(articles)
        )

        prompt = _USER_TEMPLATE.format(
            top_n=top_n,
            articles_block=articles_block,
            reader_context=_build_reader_context(user),
        )

        try:
            llm = self._get_llm()
            raw, _usage = llm.complete(
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                # Each selection entry ({"index": N, "priority": P}) costs ~15
                # tokens of JSON; a flat 1024 cap truncated the response (and
                # broke JSON parsing) once top_n grew past ~40.
                max_tokens=max(1024, top_n * 40),
                use_cache=False,
            )
            data = json.loads(raw)
            priority_map: dict[int, int] = {
                item["index"]: item["priority"]
                for item in data.get("selection", [])
                if isinstance(item.get("index"), int)
            }
        except Exception as exc:
            log.warning("curator: LLM call failed (%s) — returning all articles", exc)
            return articles

        if not priority_map:
            log.warning("curator: LLM returned empty selection — returning all articles")
            return articles

        selected = [
            (articles[idx], priority)
            for idx, priority in priority_map.items()
            if idx < len(articles)
        ]
        selected.sort(key=lambda x: x[1], reverse=True)

        top = selected[:top_n]
        if min_priority is not None:
            top = [(a, p) for a, p in top if p >= min_priority]

        result = [a for a, _ in top]
        log.info(
            "curator: selected %d/%d articles (top priority=%.0f)",
            len(result),
            len(articles),
            selected[0][1] if selected else 0,
        )
        return result
