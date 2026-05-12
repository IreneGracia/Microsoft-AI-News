"""
tag_discovery.py — RSS tag discovery pipeline
Ingests articles, runs NER + BERTopic, writes tag_discovery_report.md
"""

import re
import sys
import string
from datetime import datetime
from collections import Counter, defaultdict

# ── dependency check ────────────────────────────────────────────────────────
REQUIRED = [
    "feedparser", "bs4", "nltk", "spacy", "bertopic",
    "sentence_transformers", "pandas",
]
missing = []
for pkg in REQUIRED:
    try:
        __import__(pkg)
    except ImportError:
        missing.append(pkg)
if missing:
    print(
        "Missing dependencies. Install with:\n"
        f"  pip install {' '.join(missing)}\n"
        "Then also run:\n"
        "  python -m spacy download en_core_web_sm\n"
        "  python -m nltk.downloader stopwords"
    )
    sys.exit(1)

import feedparser
import nltk
import spacy
import pandas as pd
from bs4 import BeautifulSoup
from bertopic import BERTopic
from nltk.corpus import stopwords
from sklearn.cluster import KMeans

# ── feed list ────────────────────────────────────────────────────────────────
RSS_FEEDS = [
    {"id": "mit_tech_review",      "url": "https://www.technologyreview.com/feed/",              "category": "tech"},
    {"id": "techcrunch",           "url": "https://techcrunch.com/feed/",                        "category": "tech"},
    {"id": "wired",                "url": "https://wired.com/feed/rss",                          "category": "tech"},
    {"id": "venturebeat",          "url": "https://venturebeat.com/feed/",                       "category": "tech"},
    {"id": "the_verge",            "url": "https://www.theverge.com/rss/index.xml",              "category": "tech"},
    {"id": "ars_technica_policy",  "url": "https://arstechnica.com/tech-policy/feed/",           "category": "regulation"},
    {"id": "tech_policy_press",    "url": "https://techpolicy.press/feed/",                      "category": "regulation"},
    {"id": "euractiv",             "url": "https://euractiv.com/feed",                           "category": "eu_policy"},
    {"id": "politico_eu",          "url": "https://politico.eu/feed",                            "category": "politics"},
    {"id": "eu_parliament",        "url": "https://europarl.europa.eu/rss/doc/top-20-rss.xml",  "category": "government"},
    {"id": "edpb",                 "url": "https://edpb.europa.eu/news/rss_en",                  "category": "government"},
    {"id": "bloomberg_tech",       "url": "https://feeds.bloomberg.com/technology/news.rss",     "category": "finance"},
    {"id": "economist",            "url": "https://economist.com/latest/rss.xml",                "category": "finance"},
    {"id": "sifted",               "url": "https://sifted.eu/feed",                              "category": "finance"},
    {"id": "politico_us",          "url": "https://rss.politico.com/politics-news.xml",          "category": "politics"},
    {"id": "the_local_de",         "url": "https://feeds.thelocal.com/rss/de",                   "category": "regional"},
    {"id": "the_local_fr",         "url": "https://feeds.thelocal.com/rss/fr",                   "category": "regional"},
    {"id": "the_local_es",         "url": "https://feeds.thelocal.com/rss/es",                   "category": "regional"},
    {"id": "the_local_it",         "url": "https://feeds.thelocal.com/rss/it",                   "category": "regional"},
    {"id": "the_local_se",         "url": "https://feeds.thelocal.com/rss/se",                   "category": "regional"},
    {"id": "the_local_dk",         "url": "https://feeds.thelocal.com/rss/dk",                   "category": "regional"},
    {"id": "the_local_no",         "url": "https://feeds.thelocal.com/rss/no",                   "category": "regional"},
    {"id": "the_local_at",         "url": "https://feeds.thelocal.com/rss/at",                   "category": "regional"},
    {"id": "the_local_ch",         "url": "https://feeds.thelocal.com/rss/ch",                   "category": "regional"},
    {"id": "the_recursive",        "url": "https://therecursive.com/feed",                       "category": "regional"},
]

# ── STEP 1: ingest ───────────────────────────────────────────────────────────

def ingest_feeds(feeds):
    articles = []
    for feed_meta in feeds:
        src_id = feed_meta["id"]
        url = feed_meta["url"]
        category = feed_meta["category"]
        try:
            parsed = feedparser.parse(url)
            # feedparser doesn't raise on network errors — check bozo
            if parsed.get("bozo") and not parsed.entries:
                exc = parsed.get("bozo_exception", "unknown error")
                print(f"[{src_id}] feed error: {exc} — skipping")
                continue
            entries = parsed.entries
            count = 0
            for entry in entries:
                title = entry.get("title", "")
                summary = (
                    entry.get("summary")
                    or entry.get("content", [{}])[0].get("value", "")
                    or ""
                )
                link = entry.get("link", "")
                published = entry.get("published", entry.get("updated", ""))
                text = f"{title} {summary}".strip()
                if not text:
                    continue
                articles.append({
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "published": published,
                    "source_id": src_id,
                    "category": category,
                    "text": text,
                })
                count += 1
            print(f"[{src_id}] fetched {count} articles")
        except Exception as exc:
            print(f"[{src_id}] failed to fetch: {exc} — skipping")
    return articles


# ── STEP 2: clean text ────────────────────────────────────────────────────────

def _ensure_stopwords():
    try:
        stopwords.words("english")
    except LookupError:
        nltk.download("stopwords", quiet=True)

def build_stopword_set():
    _ensure_stopwords()
    return set(stopwords.words("english"))

URL_RE = re.compile(r"https?://\S+|www\.\S+")
PUNCT_NUM_RE = re.compile(r"[^a-z\s]")
MULTI_SPACE_RE = re.compile(r"\s+")

def clean_text(raw: str, stop_words: set) -> str:
    # strip HTML
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text(separator=" ")
    text = text.lower()
    text = URL_RE.sub(" ", text)
    text = PUNCT_NUM_RE.sub(" ", text)
    text = MULTI_SPACE_RE.sub(" ", text).strip()
    tokens = [w for w in text.split() if w not in stop_words and len(w) > 2]
    return " ".join(tokens)


# ── STEP 3: NER ──────────────────────────────────────────────────────────────

ENTITY_TYPES = {"ORG", "PERSON", "GPE", "LAW", "PRODUCT", "EVENT"}

def run_ner(articles, nlp):
    print("[NER] running named entity recognition ...")
    entity_counts = {etype: Counter() for etype in ENTITY_TYPES}
    # also track per-entity which source categories it appears in
    entity_sources = {etype: defaultdict(Counter) for etype in ENTITY_TYPES}

    for art in articles:
        doc = nlp(art["text"][:100_000])  # spaCy token limit guard
        entities = []
        for ent in doc.ents:
            if ent.label_ in ENTITY_TYPES:
                name = ent.text.strip()
                if len(name) < 2:
                    continue
                entities.append({"text": name, "label": ent.label_})
                entity_counts[ent.label_][name] += 1
                entity_sources[ent.label_][name][art["category"]] += 1
        art["entities"] = entities

    print("[NER] done")
    return entity_counts, entity_sources


def top_entities_with_source(counter, source_map, n):
    results = []
    for name, count in counter.most_common(n):
        top_src = source_map[name].most_common(1)[0][0]
        results.append({"entity": name, "count": count, "top_source": top_src})
    return results


# ── STEP 4: BERTopic ─────────────────────────────────────────────────────────

def run_bertopic(articles):
    texts = [a["cleaned_text"] for a in articles]
    print("[BERTopic] fitting model... (this may take 2–3 minutes)")
    topic_model = BERTopic(
        hdbscan_model=KMeans(n_clusters=15, random_state=42),
        calculate_probabilities=False,
        verbose=True
    )
    topics, _ = topic_model.fit_transform(texts)

    # attach topic assignment to each article
    for i, art in enumerate(articles):
        art["topic_id"] = topics[i]

    # build topic info
    topic_info = topic_model.get_topic_info()
    # topic_info columns: Topic, Count, Name, Representation (list of (word, score))
    # filter out -1 (outlier topic)
    topic_info = topic_info[topic_info["Topic"] != -1]

    topic_results = []
    for _, row in topic_info.head(15).iterrows():
        tid = int(row["Topic"])
        count = int(row["Count"])
        # get top 10 keywords
        topic_words = topic_model.get_topic(tid)
        if not topic_words:
            keywords = []
        else:
            keywords = [w for w, _ in topic_words[:10]]

        # which categories appear in this topic
        cat_counter = Counter(
            a["category"] for a in articles if a["topic_id"] == tid
        )
        total = sum(cat_counter.values()) or 1
        dominant = ", ".join(
            f"{cat}({round(c/total*100)}%)"
            for cat, c in cat_counter.most_common()
        )

        topic_results.append({
            "topic_id": tid,
            "keywords": keywords,
            "article_count": count,
            "dominant_categories": dominant,
            "cat_counter": cat_counter,
        })

    print(f"[BERTopic] found {len(topic_results)} topics (excl. outliers)")
    return topic_results


# ── STEP 5: cross-source overlap ─────────────────────────────────────────────

def build_cross_source_overlap(topic_results, top_n=10):
    rows = []
    for tr in topic_results[:top_n]:
        cat_counter = tr["cat_counter"]
        total = sum(cat_counter.values()) or 1
        breakdown = " + ".join(
            f"{cat}({round(c/total*100)}%)"
            for cat, c in cat_counter.most_common()
        )
        rows.append({
            "topic_id": tr["topic_id"],
            "keywords_preview": ", ".join(tr["keywords"][:5]),
            "breakdown": breakdown,
            "num_categories": len(cat_counter),
        })
    return rows


# ── STEP 6: report ────────────────────────────────────────────────────────────

def _md_table(headers, rows):
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


def generate_report(articles, entity_counts, entity_sources, topic_results, overlap_rows):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    source_count = len({a["source_id"] for a in articles})
    n_articles = len(articles)

    lines = []
    lines.append("# Tag Discovery Report")
    lines.append(f"\nGenerated: {now}")
    lines.append(f"Articles analysed: {n_articles}")
    lines.append(f"Sources: {source_count}")

    # ── named entities ────────────────────────────────────────────────────────
    lines.append("\n## Top Named Entities")

    lines.append("\n### Organisations (Top 30)")
    orgs = top_entities_with_source(entity_counts["ORG"], entity_sources["ORG"], 30)
    lines.append(_md_table(
        ["Entity", "Count", "Most frequent in"],
        [[r["entity"], r["count"], r["top_source"]] for r in orgs],
    ))

    lines.append("\n### People (Top 20)")
    people = top_entities_with_source(entity_counts["PERSON"], entity_sources["PERSON"], 20)
    lines.append(_md_table(
        ["Entity", "Count", "Most frequent in"],
        [[r["entity"], r["count"], r["top_source"]] for r in people],
    ))

    lines.append("\n### Locations (Top 20)")
    locs = top_entities_with_source(entity_counts["GPE"], entity_sources["GPE"], 20)
    lines.append(_md_table(
        ["Entity", "Count", "Most frequent in"],
        [[r["entity"], r["count"], r["top_source"]] for r in locs],
    ))

    lines.append("\n### Regulations / Laws (Top 15)")
    laws = top_entities_with_source(entity_counts["LAW"], entity_sources["LAW"], 15)
    if laws:
        lines.append(_md_table(
            ["Entity", "Count", "Most frequent in"],
            [[r["entity"], r["count"], r["top_source"]] for r in laws],
        ))
    else:
        lines.append("_No LAW entities detected in this corpus._")

    # ── topic clusters ────────────────────────────────────────────────────────
    lines.append("\n## Discovered Topic Clusters (BERTopic)")
    lines.append(_md_table(
        ["Topic ID", "Top Keywords", "Article Count", "Dominant Categories"],
        [
            [
                tr["topic_id"],
                ", ".join(tr["keywords"]),
                tr["article_count"],
                tr["dominant_categories"],
            ]
            for tr in topic_results
        ],
    ))

    # ── cross-source overlap ──────────────────────────────────────────────────
    lines.append("\n## Cross-Source Overlap")
    lines.append(
        "How the top 10 topics distribute across source categories "
        "(shows which tags will be useful across multiple pipelines):\n"
    )
    for row in overlap_rows:
        kw = row["keywords_preview"]
        lines.append(f"**Topic {row['topic_id']}** ({kw}): {row['breakdown']}")

    # ── suggested tag candidates ──────────────────────────────────────────────
    lines.append("\n## Suggested Tag Candidates")

    # Qualify: > 20 articles AND present in >= 2 source categories
    qualified = [
        tr for tr in topic_results
        if tr["article_count"] > 20 and len(tr["cat_counter"]) >= 2
    ]
    # Derive a short candidate name from top 2 keywords
    candidates = []
    for tr in qualified:
        kws = tr["keywords"][:2]
        name = " ".join(kws).title()
        candidates.append((name, tr["article_count"], len(tr["cat_counter"])))

    # Deduplicate by name, keep highest article count
    seen = {}
    for name, cnt, cats in candidates:
        if name not in seen or cnt > seen[name][0]:
            seen[name] = (cnt, cats)
    # Sort by article count desc, take top 12
    sorted_candidates = sorted(seen.items(), key=lambda x: -x[1][0])[:12]

    n_candidates = len(sorted_candidates)
    lines.append(
        f"Based on the above, the following {n_candidates} themes appear consistently "
        "across sources and could form the tag taxonomy:\n"
    )
    for i, (name, (cnt, cats)) in enumerate(sorted_candidates, 1):
        lines.append(f"{i}. {name}  _(~{cnt} articles, {cats} source categories)_")

    if n_candidates < 8:
        lines.append(
            "\n_Note: fewer than 8 candidates qualified (>20 articles, ≥2 categories). "
            "Consider lowering thresholds or fetching more articles._"
        )

    lines.append("\n## Next Step")
    lines.append(
        "These candidates must be reviewed and approved by the full team "
        "before being implemented as tags in the pipeline."
    )

    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    # Step 1 — ingest
    print("=" * 60)
    print("STEP 1 — ingesting RSS feeds")
    print("=" * 60)
    articles = ingest_feeds(RSS_FEEDS)
    print(f"\nTotal articles collected: {len(articles)}")

    if not articles:
        print("No articles collected — cannot continue.")
        sys.exit(1)

    # Step 2 — clean
    print("\n" + "=" * 60)
    print("STEP 2 — cleaning text")
    print("=" * 60)
    stop_words = build_stopword_set()
    for art in articles:
        art["cleaned_text"] = clean_text(art["text"], stop_words)
    # Drop articles whose cleaned text is too short to be useful
    articles = [a for a in articles if len(a["cleaned_text"].split()) >= 5]
    print(f"Articles after cleaning: {len(articles)}")

    # Step 3 — NER
    print("\n" + "=" * 60)
    print("STEP 3 — named entity recognition (spaCy)")
    print("=" * 60)
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        import subprocess
        subprocess.run(["py", "-m", "spacy", "download", "en_core_web_sm"], check=False)
        nlp = spacy.load("en_core_web_sm")
    entity_counts, entity_sources = run_ner(articles, nlp)

    # Step 4 — BERTopic
    print("\n" + "=" * 60)
    print("STEP 4 — topic discovery (BERTopic)")
    print("=" * 60)
    topic_results = run_bertopic(articles)

    # Step 5 — cross-source overlap
    print("\n" + "=" * 60)
    print("STEP 5 — cross-source overlap")
    print("=" * 60)
    overlap_rows = build_cross_source_overlap(topic_results, top_n=10)
    print(f"Built overlap table for {len(overlap_rows)} topics")

    # Step 6 — report
    print("\n" + "=" * 60)
    print("STEP 6 — generating report")
    print("=" * 60)
    report = generate_report(articles, entity_counts, entity_sources, topic_results, overlap_rows)
    out_path = "tag_discovery_report.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport written to: {out_path}")
    print("Done.")


if __name__ == "__main__":
    main()