# Digest Personalization & Ranking Fixes — 2026-07-04

**Branch:** `email-fix`
**Root cause investigated:** users were seeing the same source (e.g. the VS Code Blog) dominate their email digest. Investigation found four separate issues in the digest pipeline — three actual bugs and one incomplete feature — that compounded into a single source being able to fill most or all of a digest's article slots.

---

## Files modified

### `backend/app/pipeline/personalization/ranker.py`

**Bug 1 — no source-diversity cap when selecting the ranked shortlist**

`rank_articles()` sorted every candidate by score and returned the top `top_n`, with nothing stopping a single source from filling every slot. The chat/RAG retrieval path already caps any one source at 3 articles (`vector_store.py`'s `_diversify_by_source`); the digest ranker never got the same protection, so a source that happened to tag-match a user's preferences well (e.g. official Microsoft blogs matching the default "software development" + "AI/ML" + "Big Tech" preferences) could take over the entire digest.

Fixed by adding the same `max_per_source` cap, applied while walking the already-sorted list:

```python
# before
def rank_articles(
    articles_with_similarity: list[tuple[Article, float]],
    user: UserProfile,
    top_n: int = 10,
) -> list[Article]:
    scored = [...]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [article for article, _ in scored[:top_n]]

# after
def rank_articles(
    articles_with_similarity: list[tuple[Article, float]],
    user: UserProfile,
    top_n: int = 10,
    max_per_source: int = 3,
) -> list[Article]:
    scored = [...]
    scored.sort(key=lambda x: x[1], reverse=True)

    per_source: dict[str, int] = {}
    result: list[Article] = []
    for article, _ in scored:
        if len(result) >= top_n:
            break
        source_key = article.source or "unknown"
        if per_source.get(source_key, 0) >= max_per_source:
            continue
        per_source[source_key] = per_source.get(source_key, 0) + 1
        result.append(article)
    return result
```

---

**Bug 2 — `company_mention` scoring factor always contributed zero**

The scoring formula allocated a 20% default weight to whether an article mentions a company the user tracks. `UserProfile.companies_to_track` is hardcoded to `[]` in `user_to_profile()` (backend preferences don't collect this yet), so this factor silently scored 0 for every article, for every user, on both the chat and digest paths — 1/5 of the formula was dead weight without anything indicating so.

Fixed by removing `company` from the default weights (the existing normalization step automatically redistributes it proportionally across the remaining factors) while keeping `_company_score` available as an opt-in via `UserProfile.topic_weights` for when this is wired up properly:

```python
# before
_DEFAULT_WEIGHTS = {
    "semantic": 0.35, "tags": 0.25, "company": 0.20,
    "recency": 0.10, "source_quality": 0.10,
}
...
+ w["company"] * _company_score(article, user)

# after
_DEFAULT_WEIGHTS = {
    "semantic": 0.35, "tags": 0.25,
    "recency": 0.10, "source_quality": 0.10,
}
...
+ w.get("company", 0) * _company_score(article, user)
```

Since this factor always scored 0 anyway, this is a formula-honesty fix, not a ranking-order change — multiplying every candidate's score by the same renormalization constant doesn't change relative order.

---

### `backend/app/pipeline/pipeline.py`

**Bug — semantic similarity was a hardcoded constant in the digest path**

Before ranking, every curated article was assigned a fake similarity score of `1.0`, regardless of content: `results = [(a, 1.0) for a in curated_articles]`. This meant the single largest factor in the scoring formula (35% weight) did nothing to differentiate articles in digests, unlike chat, which computes real cosine similarity via pgvector. A `_build_interest_query(user)` method already existed on `NewsPipeline` to build a text query from the user's topics/business/regulation tags, but was never called anywhere.

Fixed by wiring it up: embed the interest query and each candidate article with the same model, score by cosine similarity, with a safe fallback to the old constant if the injected store doesn't support embeddings (e.g. the plain `ArticleStore` used in tests) or embedding fails for any reason:

```python
# before
results = [(a, 1.0) for a in curated_articles]
ranked = rank_articles(results, user, top_n=12)

# after
interest_query = self._build_interest_query(user)
results = _score_similarity(self._store, interest_query, curated_articles)
ranked = rank_articles(results, user, top_n=12)
```

Added two new module-level helpers: `_score_similarity()` (embeds the query + articles, falls back gracefully) and `_cosine()` (plain cosine similarity between two vectors — no numpy dependency needed at this article-count scale).

---

### `backend/app/pipeline/ingestion/curator.py`

**Bug — the first-pass editorial filter ignored the user entirely**

Before ranking, an LLM editorial pass (`ArticleCurator.curate()`) narrows hundreds of raw articles down to ~30 candidates. It accepted a `user: UserProfile | None` parameter but never referenced it anywhere in the method body — every user got the exact same generic "Microsoft employee audience" filter. This meant personalization only ever started at the ranking stage, working with whatever 30 candidates a non-personalized filter had already decided were worth keeping.

Fixed by building a "reader context" block from the user's topics, business tags, regions, and role, and injecting it into the curation prompt so the LLM weights relevance to that specific reader:

```python
# before
prompt = _USER_TEMPLATE.format(top_n=top_n, articles_block=articles_block)
# `user` parameter accepted but unused

# after
prompt = _USER_TEMPLATE.format(
    top_n=top_n,
    articles_block=articles_block,
    reader_context=_build_reader_context(user),
)
```

`_build_reader_context()` returns an empty string when no user profile is given, so the prompt still renders correctly for non-personalized calls.

---

## Verification

No project test suite exists for these modules yet. Verified by exercising the changed functions directly with synthetic data (no DB/network/LLM calls):

- Confirmed the diversity cap holds under an 8-vs-1 source skew (8 "VS Code Blog" candidates + 4 others → capped at 3 VS Code Blog articles in the result).
- Confirmed `score_article()` no longer raises `KeyError` without a company override, and the opt-in override path still works.
- Confirmed real similarity differentiates a relevant vs. irrelevant article (1.0 vs 0.0 in a toy embedding) instead of both scoring the old constant `1.0`.
- Confirmed the embedding-failure and no-embedding-support fallbacks degrade gracefully instead of crashing.
- Confirmed `curate()` actually sends the reader context into the LLM prompt it builds — topics, business tags, region, and role all appear in the captured prompt.

**Not yet verified:** a full end-to-end run of `NewsPipeline.run_for_user()` against a live Postgres + `ArticleVectorStore`, since that requires the full Docker stack. Recommend running one real digest generation for a test user before merging.

## Files changed

| File | Change |
|---|---|
| `backend/app/pipeline/personalization/ranker.py` | Source diversity cap + removed dead `company_mention` weight |
| `backend/app/pipeline/pipeline.py` | Real semantic similarity instead of a hardcoded `1.0` |
| `backend/app/pipeline/ingestion/curator.py` | First-pass LLM curation now personalized to the user |
