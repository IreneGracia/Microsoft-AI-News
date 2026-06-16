# Hosting Plan — Azure Student-Tier Production Deploy

> What we actually deploy for the capstone — laptop-first build, Azure-hosted demo, sized for the **Azure for Students** ($100/yr credit) ceiling.
> See [personas_and_features.md](./personas_and_features.md) for the product, [feature_endpoints.md](./feature_endpoints.md) for the API surface.
>
> Total recurring cost in Year 1: **$0** (everything fits free tiers or one-time free offers) + cents-to-low-dollars in LLM tokens.

---

## 1. Stack Summary

| Piece | Provider | Plan | Year-1 cost | Why this one |
|---|---|---|---|---|
| **Backend API** ([backend/](../backend/)) | **Azure Container Apps** | Consumption, 0.5 vCPU / 1 GiB, scale-to-zero | $0 under free monthly grant (180k vCPU-sec) | Scales to zero between cron fires — compute bill is effectively zero at MVP traffic. Pulls image from ghcr.io. |
| **Frontend** ([frontend/](../frontend/), Next.js static export) | **Azure Storage static website** | Standard_LRS | a few cents/month | Static Web Apps isn't available in this subscription's allowed regions (francecentral/swedencentral); Storage's static-website feature has no such restriction and serves HTTPS by default. |
| **PostgreSQL + pgvector** | **Azure Database for PostgreSQL** | Flexible Server, Burstable B1ms, 32 GB | $0 for first 12 months (then ~$13/mo) | Real Postgres with pgvector via `azure.extensions`. Free for a year on new accounts. |
| **Container registry** | **GitHub Container Registry** (ghcr.io) | Free for public repos | $0 | Skips Azure Container Registry's ~$5/mo Basic tier. |
| **Log Analytics** | **Azure Monitor Log Analytics** | PerGB2018 | $0 under 5 GB free monthly grant | Required by Container Apps; cheapest option that integrates. |
| **LLM** | **OpenAI** + **Anthropic** API | PAYG | cents-to-dollars | Public pricing → defensible cost-per-user in the report. Hard $-caps on both accounts. |
| **Email** | **Resend** | Free | $0 | 3 000 emails/month free. Could migrate to Azure Communication Services later. |
| **Identity** | **Microsoft Entra ID** | Free standalone tenant | $0 | Real OIDC + "Sign in with Microsoft". |
| **CI / cron** | **GitHub Actions** | Free for public repos | $0 | Hourly digest cron + image build/deploy workflow. |
| **Secrets** | Container App secrets (encrypted) | — | $0 | Lighter than Azure Key Vault for MVP; swap to KV later. |

---

## 2. The Shape on a Diagram

```
                       USER'S BROWSER
                              │
                              ▼
            Azure Storage static website ─── Next.js frontend (static export)
                              │
                              │ HTTPS / REST + SSE
                              ▼
            Azure Container Apps ─── FastAPI backend ◄── Entra ID (sign-in)
                              │                       ◄── OpenAI + Anthropic
                              │                       ◄── Resend (email)
                              ▼
                Azure Database for PostgreSQL Flexible Server
                          (with pgvector)
```

One cloud (Azure). Three external API providers (OpenAI, Anthropic, Resend). One managed database. One repo, one CI/CD pipeline.

---

## 3. Deploy Order (one-time setup)

| # | Step | Where | Notes |
|---|---|---|---|
| 1 | Create free Entra tenant | https://entra.microsoft.com | Steps in [backend/.env.example](../backend/.env.example) |
| 2 | Create OpenAI + Anthropic API keys + **set usage caps** | platform.openai.com / console.anthropic.com | Caps matter — runaway bugs can be expensive |
| 3 | Sign up for Resend, generate API key | https://resend.com | Verify a sending domain |
| 4 | `az login` + `az group create --name mai-news-rg --location francecentral` | local terminal | This subscription's stacked region policies only allow francecentral or swedencentral — see the comment in `infra/main.bicep` |
| 5 | `az deployment group create -g mai-news-rg -f infra/main.bicep -p infra/main.parameters.json -p postgresAdminPassword=$(openssl rand -base64 24)` | local terminal | Provisions Postgres, Container Apps, the frontend storage account, Log Analytics |
| 6 | `az containerapp secret set ...` for JWT, Entra, OpenAI, Anthropic, Resend, worker secrets | local terminal | See [infra/README.md](../infra/README.md) for the full command |
| 7 | Set up GitHub Actions secrets: `AZURE_CREDENTIALS`, `AZURE_RESOURCE_GROUP`, `CONTAINER_APP_NAME`, `FRONTEND_STORAGE_ACCOUNT`, `NEXT_PUBLIC_API_URL` | GitHub repo settings | First push to `main` triggers both `deploy-backend.yml` and `deploy-frontend.yml` |
| 8 | Grant the `AZURE_CREDENTIALS` service principal the **Storage Blob Data Contributor** role on the frontend storage account | local terminal | See "Grant the deploy identity access" in [infra/README.md](../infra/README.md) — needed since the workflow uploads via Azure AD auth, not an account key |
| 9 | Re-run step 5 with `frontendUrl=<frontendUrl Bicep output>` so CORS is wired | local terminal | Bicep is idempotent |
| 10 | Update Entra App Registration redirect URI to the deployed `/auth/callback` | Entra portal | `https://<your-container-app>.azurecontainerapps.io/api/v1/auth/callback` |

The full walkthrough with exact commands is in **[infra/README.md](../infra/README.md)**.

---

## 4. Cost Model

**Year-1 recurring infra:** **$0/month**.

Every Azure resource is either on the perpetual Free tier (Container Apps free grant, Static Web Apps Free, Log Analytics 5 GB grant) or on a 12-month free offer (Postgres Flexible Server B1ms). The image registry (ghcr.io) is free for public GitHub repos.

**Variable (LLM tokens):**
- Article summary cached across users (keyed by `article_id` + `length` + `tone`) — ~$0.003 per article on `gpt-4o-mini`.
- Chat: ~$0.01–0.05 per conversation on `gpt-4o` or `claude-sonnet`.
- Embeddings: **$0** — sentence-transformers `all-MiniLM-L6-v2` runs in-process (CPU), pre-baked into the Docker image so cold starts don't redownload it.

**Demo-scale estimate:** 100 users, weekly digest, 10 chat conversations/user/month → roughly **$5–15/month** in LLM tokens. Easily within an OpenAI / Anthropic hard cap.

**Year-2 cliff:** the 12-month free Postgres offer expires. Options:
- Migrate to **Neon free tier** (still Postgres + pgvector, zero code change — just swap `DATABASE_URL`)
- Stay on Azure Postgres B1ms (~$13/mo, ~$160/yr — would consume most of a renewed student credit)

---

## 5. Known Trade-offs

| Concern | Reality | Mitigation |
|---|---|---|
| Container Apps cold starts on scale-to-zero | First request after idle is ~2–5s while the replica spins | Acceptable for a hobbyist-traffic capstone; cron fires keep it warm during business hours. The sentence-transformers model is pre-loaded into the image so cold starts don't have to re-download it. |
| Postgres B1ms is small (1 vCore, 2 GB RAM) | Fine for MVP; tight for heavy vector search | Tune `ivfflat` index `lists` parameter once the archive grows past ~10k articles |
| 1 GiB RAM on the Container App | sentence-transformers uses ~500 MB at peak inference; close to the ceiling | Pre-loading the model in `Dockerfile` so it doesn't sit in /tmp at runtime. If memory pressure surfaces, swap to OpenAI embeddings (~$0.02/M tokens). |
| LLM tokens cost real money | Capstone-scale demo is cents, but a bug could spike | Hard $-caps on both OpenAI and Anthropic accounts + per-route rate limits |
| All-Azure routes EU traffic via `westeurope` | Latency is fine for EU users; US users will see ~100 ms RTT | Region is configurable in `infra/main.parameters.json` |
| No SLA on free tiers | Service outages possible | Acceptable for a capstone; mention in the report |
| Postgres free offer expires at 12 months | Year-2 stack is no longer $0 | See "Year-2 cliff" in §4 — easy migration to Neon |

---

## 6. Migration / Alternative Hosts (for the report)

The whole stack is portable — application code (FastAPI, SQLAlchemy, the OAuth flow) is unchanged across hosts. The free-tier equivalent on a different cloud:

| This deployment | Render/Vercel equivalent | Effort to swap |
|---|---|---|
| Azure Container Apps | Render Web Service (Free) | swap deploy target, keep Dockerfile |
| Azure Static Web Apps | Vercel Hobby | reconnect repo, build settings auto-detected |
| Azure Postgres Flexible Server | Neon Free | connection string only |
| Microsoft corporate Entra tenant | Free standalone Entra tenant | App Registration in a different directory; same OIDC code |
| Container App secrets | Render env vars | UI step only |
| ghcr.io | Render's built-in registry | Render builds from source — no separate registry |

---

## 7. What's Already in the Code for This

| File | What it does |
|---|---|
| [infra/main.bicep](../infra/main.bicep) | Provisions the whole Azure stack — Postgres + pgvector ext, Container Apps env, Container App, frontend storage account, Log Analytics |
| [infra/main.parameters.json](../infra/main.parameters.json) | Default parameter values (region, project name, image reference) |
| [infra/README.md](../infra/README.md) | Step-by-step deploy guide with exact `az` commands + cost notes |
| [.github/workflows/deploy-backend.yml](../.github/workflows/deploy-backend.yml) | Builds + pushes the image to ghcr.io and rolls the Container App on every push to `main` |
| [.github/workflows/deploy-frontend.yml](../.github/workflows/deploy-frontend.yml) | Builds the Next.js static export and uploads it to the frontend storage account's `$web` container on every push to `main` |
| [.github/workflows/digest-cron.yml](../.github/workflows/digest-cron.yml) | Hourly cron that fires the digest worker webhook — TZ-aware so each user gets 08:00 in their own timezone |
| [backend/Dockerfile](../backend/Dockerfile) | Python 3.12 image; pre-downloads the sentence-transformers model at build so Container Apps cold starts don't refetch it |
| [backend/.env.example](../backend/.env.example) | Full env-var reference with Azure Postgres + Neon + Docker Compose connection string examples |
| [backend/app/config.py](../backend/app/config.py) | Typed settings (incl. `allowed_origins`, `embedding_model`, `embedding_dim`) |
| [backend/app/main.py](../backend/app/main.py) | Runs `CREATE EXTENSION IF NOT EXISTS vector` + creates the ivfflat index at startup so the app works against fresh Azure Postgres |
| [docker-compose.yml](../docker-compose.yml) | Local dev Postgres + pgvector (same image type as Azure) so dev matches prod |

---

## 8. Open Questions

| # | Question | Owner |
|---|---|---|
| HOST-1 | Region — `westeurope` (default) or somewhere else for the demo audience? | Backend Dev 1 |
| HOST-2 | After Year 1, migrate Postgres to Neon free tier or pay ~$13/mo to keep all-Azure? | Team |
| HOST-3 | Custom domain or stay on `*.azurecontainerapps.io` / `*.azurestaticapps.net`? | Backend Dev 1 |
| HOST-4 | Swap sentence-transformers for OpenAI embeddings to halve RAM footprint? | LLM Engineer |
| HOST-5 | Move secrets from Container App secret store to Azure Key Vault for the report-grade story? | Backend Dev 1 |
