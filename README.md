# MAI News

AI-powered tech intelligence platform for IE × Microsoft AI/ML Engineering Capstone 2026.

Ingests articles from 40+ curated RSS sources, deduplicates and indexes them with pgvector embeddings, and delivers a RAG-powered chat interface personalised by role, region, and topic interests.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 + React 19 + Tailwind (port 3000, static SPA export) |
| Backend API | FastAPI + SQLAlchemy + pgvector (port 8000, Docker) |
| Database | Postgres 16 + pgvector (`mai-news-postgres`) |
| LLM | Anthropic Claude (`claude-sonnet-4-6`) by default; OpenAI GPT-4o available via `LLM_PROVIDER=openai` |
| Embeddings | `all-MiniLM-L6-v2` 384-dim via sentence-transformers |
| Auth | Passwordless magic-link + `dev-login` shortcut for local dev <!-- TODO: confirm with team: Google OAuth vs Entra; ACS vs Resend/Sendgrid --> |
| Deploy target | Docker locally · Azure Container Apps (backend) · Azure Storage static website (frontend) · `render.yaml` also present |

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Node 20+
- An Anthropic API key (default) **or** an OpenAI API key — see [Environment variables](#environment-variables)

---

## Local setup

### 1. Clone and configure

```bash
git clone <repo-url>
cd Microsoft-AI-News

cp backend/.env.example backend/.env
cp llm_engineering/.env.example llm_engineering/.env

# Open backend/.env and:
#   - Set ANTHROPIC_API_KEY (or OPENAI_API_KEY if switching to LLM_PROVIDER=openai).
#   - Set WORKER_SHARED_SECRET to any non-empty string.
#     Leaving it blank means /internal/* endpoints return 503.
# Everything else is pre-filled for local dev — leave it as-is.
```

### 2. Start Postgres + API

```bash
docker compose up -d
```

First time or after any Python/dependency change:

```bash
docker compose up --build -d
```

Tables and seed data (tags, sources) are created automatically on first boot.

Verify the backend is healthy:

```bash
curl http://localhost:8000/api/v1/health/ready
# → {"status":"ok","checks":{"db":"ok"}}

curl http://localhost:8000/api/v1/health/live
# → {"status":"ok"}
```

### 3. Ingest articles

Pulls from all RSS sources, deduplicates, embeds, and writes to pgvector. Requires `WORKER_SHARED_SECRET` to be set in `backend/.env` — a blank secret returns 503.

```bash
curl -X POST http://localhost:8000/api/v1/internal/run-ingest \
  -H "Authorization: Bearer <your-WORKER_SHARED_SECRET>"
# → {"fetched": 427, "unique": 381, "indexed": 381}
```

Only needed on first run or to refresh stale data. The DB persists across `docker compose` restarts.

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Opens at **http://localhost:3000**.

### 5. Sign in

Click **Sign in** — no email or password needed in dev mode. The `dev-login` endpoint takes no body and automatically provisions a fixed test user (`dev.user@microsoft.com`), returning a JWT.

---

## What is built and working

| Feature | Status |
|---|---|
| Dev login (no credentials needed) | ✅ |
| SSE streaming chat with Claude / GPT-4o | ✅ |
| RAG retrieval (pgvector cosine similarity, top 8 chunks) | ✅ |
| Topic filtering in RAG from user preferences | ✅ |
| Citations returned alongside streamed response | ✅ |
| User preferences (role, region, topics, tone, depth) | ✅ |
| Dashboard with today's top articles | ✅ |
| Dashboard filters by user topic preferences | ✅ |
| Clicking article → chat "Tell me more about {title}" | ✅ |
| General chat sessions | ✅ |
| Folder-based chat threads (named containers) | ✅ |
| Save / unsave articles from chat cards | ✅ |
| Saved articles view | ✅ |
| RSS ingestion pipeline (watermark-based, incremental) | ✅ |
| Deduplication (URL-hash + semantic similarity 0.88) | ✅ |
| Multi-dimension article tagging (topic/business/region/role) | ✅ |
| Internal ingest endpoint (`POST /internal/run-ingest`) | ✅ |
| Internal digest endpoint (`POST /internal/run-digest-worker`) | ✅ |

---

## Architecture

```
data_engineering/              — decoupled ingestion service (see Data engineering section)
  pipeline.py                  — daily entry point: fetch → embed → upsert
  init_schema.py               — schema bootstrap for standalone DE environment
  dags/ingest_dag.py           — Airflow DAG (06:00 UTC daily)
        │
        │ SQL + pgvector writes (articles, sources, kv_state)
        ▼
frontend/ (Next.js, port 3000, static SPA)
  src/components/              — App, AuthGate, chat/*, dashboard/*, news/*, saved/*
  src/lib/api.ts               — typed fetch + SSE client
        │
        │ HTTP / SSE
        ▼
backend/app/ (FastAPI, port 8000)
  routers/                     — auth, me, articles, sessions, saved, folders,
                                  tags, sources, digests, internal, health
  integrations/                — llm_bridge (adapts pipeline to API layer)
  workers/                     — ingest_worker, digest_worker
        │
        │ Python imports
        ▼
llm_engineering/src/
  ingestion/                   — RSSFetcher, ArticleDeduplicator
  rag/                         — ArticleVectorStore (pgvector-backed cosine search)
  personalization/             — article ranker
  llm/                         — chatbot (RAG), client, prompts, newsletter generator
  pipeline.py                  — end-to-end orchestration
  config/settings.py           — pydantic-settings (reads llm_engineering/.env)
        │
        │ SQL + pgvector reads
        ▼
Postgres 16 + pgvector (port 5432, Docker)
```

---

## Key API endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/auth/login` | Start OAuth flow (302 to provider) <!-- TODO: confirm with team --> |
| `GET` | `/api/v1/auth/callback` | OAuth redirect — mints JWT, redirects to frontend <!-- TODO: confirm with team --> |
| `POST` | `/api/v1/auth/email/request-login` | Send magic-link to `{email}` <!-- TODO: confirm with team --> |
| `GET` | `/api/v1/auth/email/verify` | Verify magic-link token, mint JWT <!-- TODO: confirm with team --> |
| `POST` | `/api/v1/auth/logout` | Stateless logout (204; frontend discards token) |
| `POST` | `/api/v1/auth/dev-login` | Dev-only — provisions `dev.user@microsoft.com`, returns JWT (no body) |
| `GET` | `/api/v1/health/ready` | Readiness probe — checks DB reachability |
| `GET` | `/api/v1/health/live` | Liveness probe — returns 200 if process is up |
| `GET` | `/api/v1/me` | Current user profile |
| `GET/PUT` | `/api/v1/me/preferences` | Read / write user preferences |
| `GET` | `/api/v1/articles` | List articles (supports `?topics=ai&limit=50`) |
| `GET` | `/api/v1/articles/{id}` | Single article metadata (used by citation cards) |
| `GET` | `/api/v1/articles/{id}/source` | 302 redirect to the original article URL |
| `GET` | `/api/v1/tags` | Full tag taxonomy (topic/business/region/role dimensions) |
| `GET` | `/api/v1/sources` | RSS source registry |
| `POST` | `/api/v1/me/sessions` | Create chat session |
| `POST` | `/api/v1/me/sessions/{id}/messages` | Send message (SSE stream) |
| `GET` | `/api/v1/me/digests` | List past digest summaries (cursor-paginated) |
| `GET` | `/api/v1/me/digests/{id}` | Single digest detail |
| `POST` | `/api/v1/internal/run-ingest` | Trigger RSS ingest (requires `WORKER_SHARED_SECRET`) |
| `POST` | `/api/v1/internal/run-digest-worker` | Trigger email digest (requires `WORKER_SHARED_SECRET`) |

Interactive docs at **http://localhost:8000/docs**.

---

## Environment variables

Two env files power the system. Copy from their `.example` counterparts:

```bash
cp backend/.env.example backend/.env
cp llm_engineering/.env.example llm_engineering/.env
```

### `backend/.env`

| Variable | Default | Notes |
|---|---|---|
| `ENV` | `dev` | `dev` enables dev-login and relaxed CORS |
| `DATABASE_URL` | pre-filled | Points to Docker Postgres |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Must match `EMBEDDING_DIM` |
| `EMBEDDING_DIM` | `384` | Dimensionality of pgvector embeddings |
| `JWT_SECRET` | `dev-only-change-me-in-prod` | Change in prod — generate with `secrets.token_urlsafe(64)` |
| `JWT_ALGORITHM` | `HS256` | Signing algorithm |
| `JWT_ISSUER` | `tech-intel-news` | JWT `iss` claim |
| `JWT_AUDIENCE` | `tech-intel-news-api` | JWT `aud` claim |
| `JWT_TTL_MINUTES` | `30` | Access token lifetime (minutes) |
| `OPENAI_API_KEY` | blank | Required when `LLM_PROVIDER=openai` |
| `OPENAI_MODEL_SMALL` | `gpt-4o-mini` | Used for headline summaries |
| `OPENAI_MODEL_LARGE` | `gpt-4o` | Used for chat and deep summary |
| `ANTHROPIC_API_KEY` | blank | Required when `LLM_PROVIDER=anthropic` (default) |
| `WORKER_SHARED_SECRET` | **blank** | **Must be set** — blank → `/internal/*` returns 503 |
| `FRONTEND_URL` | `http://localhost:3000` | Auth callback redirect target |
| `ALLOWED_ORIGINS` | blank | Prod only; comma-separated origins |
| `ENTRA_TENANT_ID` | blank | <!-- TODO: confirm with team --> Leave blank; dev-login works without OAuth |
| `ENTRA_CLIENT_ID` | blank | <!-- TODO: confirm with team --> |
| `ENTRA_CLIENT_SECRET` | blank | <!-- TODO: confirm with team --> |
| `ACS_CONNECTION_STRING` | blank | <!-- TODO: confirm with team --> Leave blank; emails skipped gracefully |
| `ACS_SENDER_ADDRESS` | blank | <!-- TODO: confirm with team --> |
| `RESEND_API_KEY` | blank | <!-- TODO: confirm with team --> Legacy fallback |

### `llm_engineering/.env`

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `anthropic` (default) or `openai` |
| `ANTHROPIC_API_KEY` | blank | Claude API key — required for default provider |
| `OPENAI_API_KEY` | blank | OpenAI API key — required when `LLM_PROVIDER=openai` |
| `TAVILY_API_KEY` | blank | Real-time news search; optional |
| `NEWS_API_KEY` | blank | Fallback news source; optional |
| `SMTP_HOST` | `smtp.gmail.com` | Email delivery |
| `SMTP_PORT` | `587` | |
| `SMTP_USER` | blank | SMTP credentials |
| `SMTP_PASSWORD` | blank | |

---

## Frontend: static SPA export

`next.config.ts` sets `output: 'export'`, which means:

- The frontend builds to plain HTML/CSS/JS in `out/` — no Node server needed at runtime.
- **Server Components, API routes, and `next/image` optimisation are unavailable.**
- All data fetching is client-side via `src/lib/api.ts`.
- Azure Storage static website is the deployment target (see `infra/`).

---

## Data engineering

`data_engineering/` is a standalone ingestion service decoupled from the FastAPI backend. It owns all writes to the `articles`, `sources`, and `kv_state` tables; the backend and LLM layer only read those tables.

### How it works

```
rss_fetcher.py  — watermark-based incremental fetch from all 40+ sources
      ↓
embedder.py     — batch embed title+summary with all-MiniLM-L6-v2 (384-dim)
      ↓
writer.py       — upsert articles + embeddings to Postgres, write watermarks
```

### Running manually

```bash
# Bootstrap the schema on a fresh DB (safe to re-run — uses IF NOT EXISTS):
cd data_engineering
python init_schema.py

# Run one full ingestion pass:
python pipeline.py
# → {"fetched": 427, "embedded": 381, "written": 381, "sources_upserted": 40}
```

### Automated ingestion (Airflow)

`data_engineering/dags/ingest_dag.py` defines a DAG (`mai_news_ingest`) that runs at 06:00 UTC daily. Copy or symlink it into your Airflow `dags/` folder and set `DATABASE_URL` in the Airflow environment.

### Embedding model

`all-MiniLM-L6-v2` (sentence-transformers), 384-dim. Produces vectors stored in `articles.embedding` (`vector(384)`). Must match `EMBEDDING_MODEL` / `EMBEDDING_DIM` in `backend/.env`.

---

## Useful commands

```bash
# Tail API logs
docker logs mai-news-api -f

# Rebuild API after Python/dependency changes
docker compose up --build api -d

# Stop everything (keeps DB data)
docker compose down

# Wipe DB and start fresh
docker compose down -v && docker compose up -d
```

---

## Azure deployment notes

- Restricted to **francecentral** or **swedencentral** regions.
- **Azure Static Web Apps is not available** in those regions — use **Storage static website** for the frontend instead.
- Backend targets Azure Container Apps.
- Bicep templates and a step-by-step deployment guide live in `infra/` — see `infra/README.md`.
- `render.yaml` at the repo root is an alternative deploy option (Render.com). The team has decided to stay on Azure, but the file is kept for reference.

---

## Team

IE × Microsoft AI/ML Engineering Capstone — 2026
