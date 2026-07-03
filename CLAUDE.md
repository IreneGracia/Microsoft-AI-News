# CLAUDE.md — MAI News

IE × Microsoft AI/ML Engineering Capstone 2026. AI-powered tech news platform: RSS ingestion → pgvector RAG → GPT-4o chat, personalised by user role/region/topics.

---

## How to run locally

**Requirements:** Docker Desktop + Node 20+ + an OpenAI API key in `backend/.env`.

```bash
# 1. Start Postgres + API (first time or after Python changes add --build)
docker compose up -d

# 2. Ingest articles (only needed on first run or to refresh stale data)
curl -X POST http://localhost:8000/api/v1/internal/run-ingest \
  -H "Authorization: Bearer local-dev-test-secret-123"

# 3. Start frontend (separate terminal)
cd frontend && npm install && npm run dev
```

- Backend: http://localhost:8000 — interactive docs at http://localhost:8000/docs
- Frontend: http://localhost:3001 (falls back to 3000)
- Sign in with any email/password — dev mode bypasses real auth

After any Python/backend change: `docker compose up --build api -d`

---

## Stack

| Layer | Tech | Port |
|---|---|---|
| Frontend | Next.js 15 + React 19 + Tailwind | 3001 |
| Backend | FastAPI + SQLAlchemy 2 + pgvector | 8000 |
| Database | Postgres 16 + pgvector | 5432 (Docker) |
| LLM | OpenAI GPT-4o | — |
| Embeddings | `all-MiniLM-L6-v2` 384-dim | — |
| Auth | Passwordless magic-link + dev-login shortcut | — |

---

## Project structure

```
Microsoft-AI-News/
├── CLAUDE.md                     ← you are here
├── README.md                     ← human-facing setup guide
├── plan.md                       ← living feature status + next steps
├── docker-compose.yml            ← local dev: Postgres + API
├── Dockerfile                    ← multi-stage: installs backend + llm_engineering
├── sources.json                  ← canonical 40-source RSS registry (v2.0)
│
├── backend/
│   ├── .env.example              ← copy to backend/.env, fill in OPENAI_API_KEY
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py               ← FastAPI entry, router wiring, lifespan startup
│       ├── config.py             ← pydantic-settings (reads backend/.env)
│       ├── models/               ← SQLAlchemy ORM: User, Article, Source, Tag, Session, Folder, SavedArticle
│       ├── routers/              ← auth, sessions, articles, me, internal, saved, folders, health, tags, sources
│       ├── integrations/
│       │   └── llm_bridge.py     ← adapts llm_engineering pipeline into FastAPI layer
│       └── workers/
│           ├── ingest_worker.py  ← called by POST /internal/run-ingest
│           └── digest_worker.py  ← called by POST /internal/run-digest-worker
│
├── frontend/
│   ├── package.json
│   └── src/
│       ├── app/                  ← Next.js app router (layout, page, globals.css)
│       ├── components/
│       │   ├── App.tsx           ← root component: auth gate, routing, prefs state
│       │   ├── auth/AuthGate.tsx ← login form (uses dev-login in dev mode)
│       │   ├── chat/             ← Composer, Message, CardsBlock, BriefingPreview
│       │   ├── dashboard/        ← DashboardView, ArticleCard
│       │   ├── layout/Sidebar.tsx
│       │   ├── news/NewsCard.tsx
│       │   └── saved/SavedView.tsx
│       ├── lib/api.ts            ← typed fetch + SSE client, all backend calls go here
│       └── types/index.ts        ← shared TypeScript types
│
└── llm_engineering/
    ├── config/settings.py        ← pydantic-settings, reads same backend/.env
    └── src/
        ├── ingestion/
        │   ├── fetcher.py        ← RSSFetcher with per-source watermark state
        │   ├── deduplicator.py   ← URL-hash + cosine 0.88 semantic dedup
        │   └── vector_store.py   ← ArticleVectorStore: embed + upsert to pgvector
        └── llm/
            ├── chatbot.py        ← RAG chat with history trimming
            ├── client.py         ← OpenAI/Anthropic client wrapper
            └── prompts.py        ← system + chat prompt templates
```

---

## Architecture: request flow

### Chat message (SSE stream)
```
User types message
  → POST /api/v1/me/sessions/{id}/messages
  → llm_bridge.py: embed query → pgvector cosine search (top_k=8, topic-filtered)
  → Build prompt with retrieved article context
  → Stream GPT-4o response token-by-token via SSE
  → Return citations alongside stream
  → Frontend renders tokens in real time, appends citation cards
```

### RSS ingest
```
POST /internal/run-ingest  (auth: WORKER_SHARED_SECRET header)
  → ingest_worker.py
  → RSSFetcher: fetch all tiers concurrently, watermark-based (skips already-seen)
  → ArticleDeduplicator: URL-hash dedup → semantic similarity cluster (0.88 threshold)
  → ArticleVectorStore: embed (all-MiniLM-L6-v2) → upsert pgvector → write article_tags
  → Persist watermarks to KvState table (survive container restarts)
  → Return { fetched, unique, indexed }
```

---

## Database schema (key tables)

| Table | Purpose |
|---|---|
| `users` | user profile + preferences (role, region, topics, tone, depth) |
| `articles` | ingested articles with `rss_feed_url`, `robots_txt_status`, `content_hash`, `original_language` |
| `article_tags` | multi-dim tags per article: topic, business, regulation_policy, regional, role |
| `sources` | RSS source registry (synced from sources.json on startup) |
| `chat_sessions` | user chat sessions (general or folder-scoped) |
| `chat_messages` | message history per session |
| `folders` | named project containers |
| `saved_articles` | user bookmarks |
| `kv_state` | key-value store for RSS watermarks and fetch state |

Tables are created via `Base.metadata.create_all()` on startup — no migration runner yet.

---

## Auth

- Dev mode (`ENV=dev`): `POST /auth/dev-login` with any email/password creates `dev.user@microsoft.com` and returns a JWT. No credentials required.
- Prod: magic-link email flow (`POST /auth/email/request-login` → email link → JWT).
- JWT is stored in `localStorage` as `mai_token` and sent as `Authorization: Bearer` on every API call.
- Entra OAuth is wired but optional — leave `ENTRA_*` blank to skip it.

---

## Key environment variables

All in `backend/.env` (gitignored). Copy from `backend/.env.example`.

| Variable | Local value | Notes |
|---|---|---|
| `OPENAI_API_KEY` | **set your own** | Required for chat and ingest |
| `DATABASE_URL` | `postgresql+psycopg://mai:mai@localhost:5432/mai_news` | Pre-filled |
| `ENV` | `dev` | `dev` enables dev-login + relaxed CORS |
| `WORKER_SHARED_SECRET` | `local-dev-test-secret-123` | Used in curl calls to /internal/* |
| `JWT_SECRET` | `dev-only-change-me-in-prod` | Change in prod |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Must match `EMBEDDING_DIM=384` |

---

## What's done vs what's next

See `plan.md` for the full living status. Summary:

**Done:** full-stack wiring, SSE chat, RAG, dashboard, folders, saved articles, ingest pipeline, multi-dim tagging, dev auth.

**Next (in priority order):**
1. GitHub Actions cron for auto-ingest (`.github/workflows/ingest-cron.yml`, calls `/internal/run-ingest` on a schedule)
2. Wire `AuthGate` email input to real magic-link endpoint (currently always hits dev-login regardless of input)
3. Azure deployment: Container Apps (backend) + Storage static website (frontend)

---

## Constraints and gotchas

- **Sequential work only** — one person works at a time on one feature at a time to avoid merge conflicts. Always pull before starting.
- **Azure regions:** francecentral or swedencentral only. **Static Web Apps is unavailable** in those regions — use Storage static website for the frontend.
- **Backend changes need a Docker rebuild:** `docker compose up --build api -d`. Hot reload does not work for Python.
- **Frontend hot reloads** automatically on save.
- **OPENAI_API_KEY is never committed** — `backend/.env` is in `.gitignore`. Each developer sets their own key.
- **DB persists across restarts** — `docker compose down` keeps data. `docker compose down -v` wipes it.
- **`llm_engineering/` is imported by the backend** — it's not a standalone service. The Dockerfile installs both.
- **`FETCH_STATE_PATH`** defaults to `/tmp/fetch_state.json` (evaporates on restart). For prod, set it to a stable path. The Postgres `kv_state` table is the authoritative watermark store.

---

## Branch strategy

- `main` — stable, deployable, and the active working branch
- Feature branches should be short-lived, one per person, merged via PR to `main`

Always open a PR — do not push directly to `main`.
