# Deployment Runbook — Email Digest & Login

Everything done to get email digest delivery and magic-link login working end-to-end on Azure. Written so anyone can reproduce this from scratch.

---

## Azure Subscription

The resource group `mai-news-rg` lives under **Azure subscription 1** (`98947069-b86f-4a38-a42d-43af815debd3`), not "IE Workspaces". Always set this before running `az` commands:

```bash
az login
az account set --subscription 98947069-b86f-4a38-a42d-43af815debd3
```

---

## Resources in `mai-news-rg`

| Resource | Name | Type |
|---|---|---|
| Backend | `mainews-api` | Azure Container App |
| Container Apps Environment | `mainews-cae` | Managed Environment |
| Database | `mainews-pgserver` | Postgres Flexible Server |
| Email | `mainews-email` | ACS Email Service |
| Communication | `mainews-comms2026` | ACS Communication Service |
| Frontend | `mainews-vault` | Key Vault |
| Frontend storage | `mainewswebstorage` | Storage Account (static website) |

**Note:** The ACS Communication Service is named `mainews-comms2026` (not `mainews-comms`) because `mainews-comms` was globally reserved. `infra/main.bicep` has been updated to reflect this.

---

## Part 1 — Email Digest

### 1.1 Fix missing Python package

`azure-communication-email` was missing from `backend/requirements.txt`. Added:

```
azure-communication-email==1.0.0
```

### 1.2 Provision ACS manually (Portal)

Bicep did not provision ACS. Created manually via Azure Portal:

1. Portal → **Create a resource** → **Communication Services**
   - Resource group: `mai-news-rg`
   - Name: `mainews-comms2026`
   - Data location: Europe
2. Inside the resource → **Email** → **Domains** → **Add domain** → **Azure managed domain**
   - Wait for DKIM/DMARC/SPF to auto-verify (~2 min)
3. Inside the resource → **Settings** → **Keys** → copy **Primary connection string**
4. From the domain → copy the **MailFrom address** (`DoNotReply@<random>.azurecomm.net`)

### 1.3 Set ACS credentials on the Container App

```bash
az containerapp update \
  --name mainews-api \
  --resource-group mai-news-rg \
  --subscription 98947069-b86f-4a38-a42d-43af815debd3 \
  --set-env-vars \
    "ACS_CONNECTION_STRING=<primary-connection-string>" \
    "ACS_SENDER_ADDRESS=DoNotReply@<your-domain>.azurecomm.net"
```

### 1.4 Set GitHub Actions secrets

```bash
gh secret set BACKEND_URL --body "https://mainews-api.mangorock-b0c3e0fe.francecentral.azurecontainerapps.io"
gh secret set WORKER_SHARED_SECRET --body "<value-from-container-app>"
```

To find the current `WORKER_SHARED_SECRET` on the container:
```bash
az containerapp secret show \
  --name mainews-api \
  --resource-group mai-news-rg \
  --subscription 98947069-b86f-4a38-a42d-43af815debd3 \
  --secret-name worker-shared-secret \
  --query "value" -o tsv
```

### 1.5 Delete the old disabled workflow

```bash
git rm .github/workflows/digest-cron.yml.disabled
git commit -m "chore: remove deprecated digest-cron disabled workflow"
```

### 1.6 Test the cron workflows

```bash
gh workflow run ingest-cron.yml
gh run watch

gh workflow run digest-cron.yml
gh run watch
```

Both should show green. The digest response should include `"emailed": 1` if a user is eligible.

---

## Part 2 — Frontend Deployment

### 2.1 Create `frontend/.env.production`

Without this file, Next.js falls back to `http://localhost:8000` and login fails.

```
NEXT_PUBLIC_API_URL=https://mainews-api.mangorock-b0c3e0fe.francecentral.azurecontainerapps.io/api/v1
```

This file is committed to the repo (gitignore exception added).

### 2.2 Build and upload

```bash
cd frontend
npm run build

az storage blob upload-batch \
  --account-name mainewswebstorage \
  --destination '$web' \
  --source out \
  --overwrite \
  --subscription 98947069-b86f-4a38-a42d-43af815debd3
```

Frontend live at: `https://mainewswebstorage.z28.web.core.windows.net`

---

## Part 3 — Magic-Link Login

Three env vars on the Container App were wrong or missing, all set in one pass:

### 3.1 CORS (ENV + ALLOWED_ORIGINS)

The backend defaulted to `ENV=dev`, which ignores `ALLOWED_ORIGINS` and only allows localhost. The deployed frontend got blocked by CORS.

### 3.2 Magic link redirect (FRONTEND_URL)

After clicking the magic link the backend redirects to `{FRONTEND_URL}/#access_token={jwt}`. Without this set, it redirected to `http://localhost:3000`.

### 3.3 Magic link URL (OAUTH_REDIRECT_URI)

`build_login_url()` in `email_link.py` derives the backend base URL from `settings.oauth_redirect_uri`. Without this set, the link in the email pointed to `http://localhost:8000`.

### 3.4 Fix — set all three

```bash
az containerapp update \
  --name mainews-api \
  --resource-group mai-news-rg \
  --subscription 98947069-b86f-4a38-a42d-43af815debd3 \
  --set-env-vars "ENV=prod" "ALLOWED_ORIGINS=https://mainewswebstorage.z28.web.core.windows.net" "FRONTEND_URL=https://mainewswebstorage.z28.web.core.windows.net"

az containerapp update \
  --name mainews-api \
  --resource-group mai-news-rg \
  --subscription 98947069-b86f-4a38-a42d-43af815debd3 \
  --set-env-vars "OAUTH_REDIRECT_URI=https://mainews-api.mangorock-b0c3e0fe.francecentral.azurecontainerapps.io/api/v1/auth/callback"
```

**Note:** Setting `ENV=prod` disables the `/auth/dev-login` endpoint. Magic-link is the only login method on the live backend.

---

## Part 4 — Database Access (if needed)

Connect to the live Postgres database:

```bash
# Get connection string from Container App secrets
az containerapp secret show \
  --name mainews-api \
  --resource-group mai-news-rg \
  --subscription 98947069-b86f-4a38-a42d-43af815debd3 \
  --secret-name database-url \
  --query "value" -o tsv

# Connect (psql must be installed — C:\Program Files\PostgreSQL\18\bin\ on Windows)
"/c/Program Files/PostgreSQL/18/bin/psql" "<connection-string>"
```

---

## CI/CD Status

Automated deploy on push is **blocked** — requires an Azure service principal (`az ad sp create-for-rbac`) which needs tenant admin rights. Emailed Gustavo. Until resolved, deploys are manual:

**Backend redeploy:**
```bash
gh auth token | docker login ghcr.io -u <github-username> --password-stdin
docker build -t ghcr.io/bertolikimberly/microsoft-ai-news-backend:latest -f backend/Dockerfile .
docker push ghcr.io/bertolikimberly/microsoft-ai-news-backend:latest
az containerapp update --name mainews-api --resource-group mai-news-rg \
  --subscription 98947069-b86f-4a38-a42d-43af815debd3 \
  --image ghcr.io/bertolikimberly/microsoft-ai-news-backend:latest
```

**Frontend redeploy:**
```bash
cd frontend && npm run build
az storage blob upload-batch --account-name mainewswebstorage \
  --destination '$web' --source out --overwrite \
  --subscription 98947069-b86f-4a38-a42d-43af815debd3
```

When the service principal is available, add these GitHub secrets to enable CI/CD:

| Secret | Value |
|---|---|
| `AZURE_CREDENTIALS` | JSON from `az ad sp create-for-rbac --sdk-auth` |
| `AZURE_RESOURCE_GROUP` | `mai-news-rg` |
| `CONTAINER_APP_NAME` | `mainews-api` |
| `FRONTEND_STORAGE_ACCOUNT` | `mainewswebstorage` |
| `NEXT_PUBLIC_API_URL` | `https://mainews-api.mangorock-b0c3e0fe.francecentral.azurecontainerapps.io/api/v1` |
