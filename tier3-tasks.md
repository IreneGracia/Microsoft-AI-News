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

## 4. Email Delivery → Resend

**Decision:** Use Resend. App is hosted on Azure but Resend is provider-agnostic — one API key, no Azure portal setup needed.

**Current state:** Email is wired to ACS (`backend/app/integrations/email.py`). `resend==2.4.0` is already in `requirements.txt` but unused. `azure-communication-email` is used in code but missing from `requirements.txt` (runtime failure).

- [x] Rewrite `backend/app/integrations/email.py` to use the `resend` SDK
- [x] Update `backend/app/config.py` — replaced ACS fields with `resend_api_key` and `resend_from` as primary
- [x] Update `backend/.env.example` — Resend section already present and correct
- [ ] Remove ACS resource block from `infra/main.bicep:354–398`
- [ ] Update `render.yaml` env vars to use `RESEND_API_KEY` (lines 82–86 already reference Resend — verify they match)
- [ ] Set `RESEND_API_KEY` and `RESEND_FROM` in Azure Container Apps environment (portal or Bicep)

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
