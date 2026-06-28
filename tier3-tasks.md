# Tier 3 Backend Tasks

Decisions made and work needed to resolve inconsistencies in the backend.

---

## 1. Frequency Model → User Chooses (Daily / Weekdays / Weekly)

**Decision:** Keep all three options — users pick their own frequency: `daily`, `weekdays`, or `weekly`. Already fully implemented.

**Current state:** `UserPreferences` has a per-user `frequency` field (daily/weekdays/weekly) with `_is_delivery_day()` logic in `digest_worker.py`. No changes needed.

- [x] ~~Decide frequency model~~ — per-user, three options, already implemented

---

## 2. Delivery Timing → Per-User Timezone-Aware

**Decision:** Keep per-user timezone-aware delivery. Already fully implemented.

**Current state:** `UserPreferences` stores `timezone` (IANA) and `delivery_hour_local` (0–23). `digest_worker.py` converts UTC → user local time via `_to_user_local()`. No changes needed.

- [x] ~~Decide delivery timing~~ — per-user timezone-aware, already implemented

---

## 3. Digest Length → Keep User-Configurable (Short / Standard / Deep)

**Decision:** Leave as-is. User preference is already stored and passed to the pipeline. No backend enforcement needed for MVP — the pipeline handles it.

- [x] ~~Decide digest length~~ — user-configurable, already implemented

---

## 4. Email Delivery → Azure Communication Services (ACS)

**Decision:** Use ACS — team prefers staying fully on Azure.

**Fix applied:** `azure-communication-email` was missing from `requirements.txt` (runtime failure). Now added. `email.py` and `config.py` restored to ACS.

**ACS resources created manually** (Bicep name `mainews-comms` was globally reserved):
- Communication Service: `mainews-comms2026`
- Email Service: `mainews-email` with Azure Managed Domain (DKIM/DMARC/SPF auto-verified)
- Both linked; credentials pushed to Container App secrets and Key Vault

- [x] Add `azure-communication-email==1.0.0` to `backend/requirements.txt` (was missing — fixed)
- [x] `backend/app/integrations/email.py` — ACS implementation confirmed correct
- [x] `backend/app/config.py` — `acs_connection_string` and `acs_sender_address` fields confirmed
- [x] Set `ACS_CONNECTION_STRING` and `ACS_SENDER_ADDRESS` in Azure Container Apps environment
- [x] Update `infra/main.bicep` — `communicationServiceName` hardcoded to `mainews-comms2026` (was `${projectName}-comms`)

---

## 5. Streaming → Keep SSE Streaming

**Decision:** Keep streaming (SSE) for MVP.

**Current state:** Fully implemented — `sessions.py:262–407` streams `turn_start`, `token`, `citation`, `turn_end` events. No changes needed.

- [x] ~~Decide streaming vs non-streaming~~ — SSE streaming confirmed, already implemented

---

## 6. Migrations → Keep `create_all` for MVP

**Decision:** No Alembic for now. Stay on `create_all`.

**Current state:** `backend/app/main.py:67` runs `Base.metadata.create_all()` on startup. An explicit TODO already exists in the code. No changes needed for MVP.

- [x] ~~Decide on Alembic~~ — deferred, `create_all` stays for MVP
- [ ] *(Post-MVP)* Introduce Alembic before any prod schema change

---

## 7. Backend Hosting → Stay on Azure

**Decision:** Azure Container Apps remains the primary deployment target.

**Current state:** Backend deployed and live at `https://mainews-api.mangorock-b0c3e0fe.francecentral.azurecontainerapps.io`. CI/CD auto-deploy is blocked (needs Azure service principal with tenant admin rights — emailed Gustavo). Deploys are manual via `az containerapp update`.

- [x] ~~Decide hosting~~ — Azure confirmed
- [x] Backend deployed and live on Azure Container Apps
- [x] `infra/main.bicep` updated to match real ACS resource name

---

## 8. Scheduler → GitHub Actions Cron

**Decision:** Use GitHub Actions cron — already built, right tool for the job. No Airflow needed for MVP.

**Current state:** Both cron workflows are live. Repo secrets set. Old disabled file deleted.

- [x] Created `.github/workflows/digest-cron.yml` (hourly, POSTs to `/internal/run-digest-worker`)
- [x] Created `.github/workflows/ingest-cron.yml` (every 6 hours, POSTs to `/internal/run-ingest`)
- [x] Deleted `.github/workflows/digest-cron.yml.disabled` (superseded)
- [x] Set repo secret `BACKEND_URL`
- [x] Set repo secret `WORKER_SHARED_SECRET`
- [ ] Test both workflows manually via `workflow_dispatch` before relying on the schedule

---

## Remaining Steps to Go Live

Do these in order.

---

### Step 1 — Merge tier3 into main

```bash
git checkout main
git merge tier3
git push origin main
```

---

### Step 2 — Rebuild and redeploy the backend

CI/CD is blocked (needs Azure service principal with tenant admin rights). Do it manually:

```bash
# Find your GitHub username
gh api user --jq .login

# Log into ghcr.io
gh auth token | docker login ghcr.io -u <your-github-username> --password-stdin

# Build from repo root (takes a few minutes)
docker build -t ghcr.io/bertolikimberly/microsoft-ai-news-backend:latest -f backend/Dockerfile .

# Push
docker push ghcr.io/bertolikimberly/microsoft-ai-news-backend:latest

# Tell Azure to use the new image
az containerapp update \
  --name mainews-api \
  --resource-group mai-news-rg \
  --subscription 98947069-b86f-4a38-a42d-43af815debd3 \
  --image ghcr.io/bertolikimberly/microsoft-ai-news-backend:latest
```

> Note: `docker push` requires write access to the `bertolikimberly` GitHub packages. If it fails with a permission error, the teammate who originally deployed needs to do this step.

---

### Step 3 — Test the cron workflows

```bash
# Trigger ingest first and watch the logs
gh workflow run ingest-cron.yml
gh run watch

# Then trigger digest and watch the logs
gh workflow run digest-cron.yml
gh run watch
```

Both should show a green checkmark. The digest run should also produce an email to any user in the database who has a digest scheduled.
