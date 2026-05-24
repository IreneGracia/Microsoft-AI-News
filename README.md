# MAI News — Microsoft AI Capstone

AI-powered tech intelligence platform that ingests news from 54 sources, deduplicates and indexes articles semantically, and delivers personalized newsletters and a RAG-powered chat interface — tailored by role, region, and interests.

---

## Architecture

```
sources.json (54 RSS feeds, canonical source list)
      │
      ▼
data_engineering/          ← ingestion & tag discovery
  rss_fetcher.py           — incremental RSS polling with per-source watermarks
  tag_discovery.py         — NER + BERTopic topic clustering
  sources.py               — feed list used by the DE scripts
      │
      ▼ Article dicts
llm_engineering/           ← AI/ML pipeline
  src/ingestion/           — async RSS fetcher + semantic deduplicator
  src/rag/                 — ChromaDB vector store (all-MiniLM-L6-v2 embeddings)
  src/personalization/     — weighted ranking (semantic + category + recency)
  src/llm/                 — Claude/GPT newsletter generator + RAG chatbot
  src/pipeline.py          — end-to-end orchestration entry point
      │
      ▼ NewsletterDigest / ChatResponse
backend/                   ← API layer (coming soon)
      │
      ▼ JSON
frontend/                  ← Next.js React UI
  src/components/          — chat, news cards, preferences wizard, auth
```

---

## Modules

### `data_engineering/`

Handles raw ingestion from RSS feeds.

| File | Purpose |
|---|---|
| `sources.py` | Feed list (25 sources, subset of `sources.json`) |
| `rss_fetcher.py` | Incremental poller — persists watermarks to `fetch_state.json` |
| `tag_discovery.py` | NER (spaCy) + topic clustering (BERTopic) across all feeds |
| `tag_discovery_report.md` | Latest discovery run — 802 articles, 22 sources |

**Run the fetcher:**
```bash
cd data_engineering
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python rss_fetcher.py
```

**Run tag discovery** (takes 2–3 min, downloads models on first run):
```bash
python tag_discovery.py   # writes tag_discovery_report.md
```

---

### `llm_engineering/`

End-to-end AI pipeline: fetch → deduplicate → embed → rank → generate.

**Setup:**
```bash
cd llm_engineering
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your API keys
```

**Run the full pipeline for a test user:**
```python
import asyncio
from src.pipeline import NewsPipeline
from src.models import UserProfile, TechCategory, TonePreference

user = UserProfile(
    user_id="u1",
    name="Ada Lovelace",
    email="ada@microsoft.com",
    role="ML Engineer",
    interests=[TechCategory.AI_ML, TechCategory.CLOUD],
    companies_to_track=["OpenAI", "Microsoft", "Google"],
    tone=TonePreference.TECHNICAL,
)

pipeline = NewsPipeline()
digest = asyncio.run(pipeline.run_for_user(user))
print(digest.intro)
for item in digest.articles:
    print(f"[{item.rank}] {item.article.title}")
    print(item.summary)
```

**Pipeline stages:**

| Stage | File | What it does |
|---|---|---|
| Fetch | `src/ingestion/fetcher.py` | Async RSS polling, watermark state, full-body fetch for paywalled excerpts |
| Dedup | `src/ingestion/deduplicator.py` | URL-hash + cosine similarity clustering (threshold 0.88) |
| Index | `src/rag/vector_store.py` | ChromaDB with `all-MiniLM-L6-v2` embeddings, skip-re-embed on existing docs |
| Rank | `src/personalization/ranker.py` | Weighted score: semantic (35%) + category (25%) + company mention (20%) + recency (10%) + source quality (10%) |
| Generate | `src/llm/newsletter.py` | Claude/GPT newsletter with prompt caching, per-user tone, token cost tracking |
| Chat | `src/llm/chatbot.py` | RAG chatbot — retrieves relevant articles, cites sources |

**Consuming data_engineering output:**

If you have article dicts from `data_engineering/rss_fetcher.py`, convert them directly:

```python
from src.ingestion.fetcher import article_from_de_dict

raw = {"url": "...", "title": "...", "summary": "...", "source_id": "techcrunch", "pub_date": "2026-05-24T10:00:00+00:00"}
article = article_from_de_dict(raw)   # returns Article | None
```

---

### `frontend/`

Next.js + Tailwind UI. Standalone prototype runs without a build step.

**Quick start (no build):**
1. Open `frontend/index.html` with [Live Server](https://marketplace.visualstudio.com/items?itemName=ritwickdey.LiveServer) in VS Code
2. Browser opens at `http://127.0.0.1:5500`

**Full dev server:**
```bash
cd frontend
npm install
npm run dev
```

**Auth:** Currently mocked (Microsoft + Google SSO dialogs). Wire to real Entra ID via `@azure/msal-browser` — see the auth section in the component docs.

**User shape** (stored in `localStorage` under `mai_user`):
```ts
{
  name: string,
  email: string,       // @microsoft.com enforced
  department: string,
  region: "na" | "eu" | "china" | "apac" | "india" | "latam" | "mea",
  signedInAt: number
}
```

---

## Sources & Tag Taxonomy

All 54 RSS sources live in **`sources.json`** at the repo root — the single source of truth consumed by both `data_engineering` and `llm_engineering`.

**Scrape tiers:**
- `breaking` — checked every 60 min (TechCrunch, MIT TR, Bloomberg, arXiv, …)
- `standard` — every 360 min (Wired, Ars Technica, Politico, …)
- `daily` — once per day (regional, government sources)

**Tag dimensions** (used by the preferences wizard and ranking):

| Dimension | Tags |
|---|---|
| Topic | AI & ML, Cybersecurity, Cloud & Infrastructure, Software Development, Hardware & Chips, Data & Privacy, Quantum Computing, Robotics, Fintech, Health & Biotech, Clean Tech, Space, Metaverse & XR |
| Business | M&A & Funding, IPO & Markets, Big Tech, Startups & Venture, Layoffs & Hiring, Earnings |
| Regulation | AI Regulation, GDPR/DPDP/LGPD, Antitrust, Export Controls, Digital Infrastructure Policy, Cybersecurity Policy, Platform Regulation |
| Region | North America, Europe, Greater China, Asia Pacific, India, Latin America, Middle East & Africa |
| Role | Engineers, Business & Sales, Legal & Compliance, Executives, Researchers |

---

## Environment variables

Copy `.env.example` → `.env` in the repo root (or in `llm_engineering/` when running standalone). **Never commit `.env`.**

| Variable | Required | Description |
|---|---|---|
| `LLM_PROVIDER` | yes | `anthropic` or `openai` |
| `ANTHROPIC_API_KEY` | if using Claude | Claude API key |
| `OPENAI_API_KEY` | if using GPT | OpenAI API key |
| `TAVILY_API_KEY` | optional | Real-time news search fallback |
| `CHROMA_PERSIST_DIR` | no | Vector store path (default `./data/chroma_db`) |
| `SMTP_*` | optional | Gmail SMTP for email delivery |

---

## Docker

```bash
docker compose up        # starts all services
docker compose up --build   # rebuild after dependency changes
```

---

## Repo structure

```
Microsoft-AI-News/
├── sources.json              # canonical feed registry (54 sources)
├── .env.example              # environment variable template
├── docker-compose.yaml
├── data_engineering/
│   ├── sources.py            # feed list for DE scripts
│   ├── rss_fetcher.py        # incremental RSS ingestion
│   ├── tag_discovery.py      # NER + BERTopic pipeline
│   └── requirements.txt
├── llm_engineering/
│   ├── src/
│   │   ├── models.py         # Article, UserProfile, NewsletterDigest, …
│   │   ├── pipeline.py       # orchestration entry point
│   │   ├── ingestion/        # fetcher + deduplicator + source registry
│   │   ├── rag/              # ChromaDB vector store
│   │   ├── personalization/  # ranked article scoring
│   │   └── llm/              # newsletter generator + chatbot + prompts
│   ├── config/
│   │   └── settings.py       # pydantic-settings config
│   ├── tests/
│   ├── scripts/
│   └── requirements.txt
├── backend/                  # API layer (coming soon)
└── frontend/
    ├── index.html            # standalone prototype (no build needed)
    ├── src/components/       # React components
    └── package.json
```

---

## Team

IE × Microsoft AI/ML Engineering Capstone — 2026
