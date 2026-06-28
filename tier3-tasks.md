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

- [x] Add `azure-communication-email==1.0.0` to `backend/requirements.txt` (was missing — fixed)
- [x] `backend/app/integrations/email.py` — ACS implementation confirmed correct
- [x] `backend/app/config.py` — `acs_connection_string` and `acs_sender_address` fields confirmed
- [ ] Set `ACS_CONNECTION_STRING` and `ACS_SENDER_ADDRESS` in Azure Container Apps environment (portal or Bicep)

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

**Current state:** `infra/main.bicep` provisions Container Apps + Postgres Flexible Server + ACS + Storage. `render.yaml` exists as a fallback. CI/CD via `.github/workflows/deploy-backend.yml`.

- [x] ~~Decide hosting~~ — Azure confirmed
- [ ] After email provider switch (Task 4): update `infra/main.bicep` to remove ACS resource block
- [ ] After email provider switch (Task 4): add new email provider env var to `main.bicep` managed environment secrets

---

## 8. Scheduler → GitHub Actions Cron

**Decision:** Use GitHub Actions cron — already built, right tool for the job. No Airflow needed for MVP.

**Current state:** `.github/workflows/digest-cron.yml.disabled` exists (hourly cron, POSTs to `/internal/run-digest-worker`). Just needs enabling + two repo secrets. Ingest cron is a separate workflow to add.

- [x] Created `.github/workflows/digest-cron.yml` (hourly, POSTs to `/internal/run-digest-worker`)
- [x] Created `.github/workflows/ingest-cron.yml` (every 6 hours, POSTs to `/internal/run-ingest`)
- [ ] Delete `.github/workflows/digest-cron.yml.disabled` (superseded by the new file)
- [ ] Set repo secret `BACKEND_URL` in GitHub → Settings → Secrets → Actions
- [ ] Set repo secret `WORKER_SHARED_SECRET` in GitHub → Settings → Secrets → Actions
- [ ] Test both workflows manually via `workflow_dispatch` before relying on the schedule

---

## Exact Steps to Go Live

Do these in order. Everything below assumes you are logged into GitHub and the Azure Portal.

---

### Step 1 — Get ACS credentials from Azure

1. Go to **https://portal.azure.com**
2. Search for **Communication Services** in the top search bar → open your MAI News ACS resource (created by the Bicep deploy)
3. Left sidebar → **Settings** → **Keys** → copy the **Primary connection string** — this is your `ACS_CONNECTION_STRING`
4. Left sidebar → **Email** → **Domains** → open your Azure Managed Domain → copy the **MailFrom address** (looks like `DoNotReply@<random>.azurecomm.net`) — this is your `ACS_SENDER_ADDRESS`

---

### Step 2 — Add ACS credentials to your Container App

1. Go to **https://portal.azure.com**
2. Search for **Container Apps** → open your MAI News backend app
3. Left sidebar → **Settings** → **Environment variables**
4. Click **Add** and add these two variables:
   - Name: `ACS_CONNECTION_STRING` | Value: *(the connection string from Step 1)*
   - Name: `ACS_SENDER_ADDRESS` | Value: *(the MailFrom address from Step 1)*
5. Click **Save** → the container restarts automatically (~30 seconds)

---

### Step 3 — Add GitHub Actions secrets

1. Go to your GitHub repo → **Settings** tab (top of repo page)
2. Left sidebar → **Secrets and variables** → **Actions**
3. Click **New repository secret** and add these one at a time:

   | Name | Value |
   |---|---|
   | `BACKEND_URL` | Your Azure Container Apps URL, e.g. `https://your-app.azurecontainerapps.io` |
   | `WORKER_SHARED_SECRET` | The value of `WORKER_SHARED_SECRET` from your `backend/.env` file |

   > To find your Azure URL: Portal → Container Apps → your app → **Overview** → copy the **Application URL**

---

### Step 4 — Delete the old disabled workflow

In your repo, delete this file:
```
.github/workflows/digest-cron.yml.disabled
```
You can do it in the GitHub UI (open the file → click the trash icon) or locally:
```bash
git rm .github/workflows/digest-cron.yml.disabled
git commit -m "chore: remove deprecated digest-cron disabled workflow"
```

---

### Step 5 — Merge tier3 into main and redeploy

```bash
git checkout main
git merge tier3
git push origin main
```

This triggers `deploy-backend.yml` automatically — GitHub Actions will build a new Docker image and deploy it to Azure with the new Resend email code. Watch the **Actions** tab to confirm it succeeds.

---

### Step 6 — Test the cron workflows manually

Once the deploy is done:

1. GitHub repo → **Actions** tab
2. Left sidebar → **Run ingest pipeline** → **Run workflow** → **Run workflow** (green button)
   - Watch the logs — it should POST to `/internal/run-ingest` and return a JSON summary
3. Left sidebar → **Run digest worker** → **Run workflow** → **Run workflow**
   - Watch the logs — it should POST to `/internal/run-digest-worker`
   - Check your email (the one in the database) for a test digest

If both workflows show a green checkmark, everything is live and working.
