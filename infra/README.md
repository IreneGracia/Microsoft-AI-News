# Azure deployment

This directory holds the Bicep templates that provision the production
stack on Azure. Sized for the **Azure for Students** ($100/yr) credit
ceiling — every resource is on the cheapest tier that still supports
the app's requirements.

## The stack

| Resource | SKU | Cost (after free offers) |
|---|---|---|
| Azure Database for PostgreSQL Flexible Server | Burstable B1ms, 32 GB | ~$13/mo (free for 12 months on new accounts) |
| Container Apps Environment + App | Consumption, 0.5 vCPU / 1 GiB, scale-to-zero | $0 under free monthly grant (180k vCPU-sec) |
| Storage account (static website) | Standard_LRS, ~1-2 MB of static assets | a few cents/month |
| Log Analytics workspace | PerGB2018 | $0 under 5 GB free monthly grant |

**Frontend note:** Static Web Apps (the originally-planned host) isn't
available in this subscription's allowed regions — see the comment above
the `frontendStorage` resource in `main.bicep`. The frontend is instead a
Next.js **static export** (`output: 'export'` in `frontend/next.config.ts`,
since the app has no API routes or server actions) hosted on a plain
Storage account's static-website feature, in the same francecentral
region as everything else. Its `<account>.z##.web.core.windows.net`
endpoint is served over HTTPS by default — no custom domain needed for
a demo.

**Why this shape:** Postgres + pgvector is mandatory (semantic search,
RAG). Container Apps with scale-to-zero is the cheapest way to run a
FastAPI service on Azure — between cron fires the app uses no compute.
Static Web Apps Free is free forever for personal sites.

Container images come from **ghcr.io** (free for public repos) instead
of Azure Container Registry (~$5/mo Basic tier).

## First-time deploy

```bash
# 1. Log in and create the resource group.
az login
az group create --name mai-news-rg --location francecentral

# 2. Generate a strong Postgres admin password.
export PG_PWD=$(openssl rand -base64 24)

# 3. Deploy the stack.
az deployment group create \
  --resource-group mai-news-rg \
  --template-file main.bicep \
  --parameters main.parameters.json \
  --parameters postgresAdminPassword="$PG_PWD"

# 4. Set runtime secrets on the Container App. Replace the placeholders.
az containerapp secret set \
  --name mainews-api \
  --resource-group mai-news-rg \
  --secrets \
    jwt-secret=$(openssl rand -base64 48) \
    entra-tenant-id=<your-tenant-id> \
    entra-client-id=<your-client-id> \
    entra-client-secret=<your-entra-secret> \
    openai-api-key=<sk-...> \
    anthropic-api-key=<sk-ant-...> \
    resend-api-key=<re_...> \
    worker-shared-secret=$(openssl rand -base64 32)

# 5. Roll the app to pick up the new secrets.
az containerapp update --name mainews-api --resource-group mai-news-rg
```

The deployment outputs the Container App URL (`backendUrl`) and the
frontend storage static-website URL (`frontendUrl`) — grab those for the
next step. The frontend URL won't actually serve anything until the
frontend deploy workflow runs (step below) and uploads a build to it.

## Wire CORS once the frontend has a URL

```bash
az deployment group create \
  --resource-group mai-news-rg \
  --template-file main.bicep \
  --parameters main.parameters.json \
  --parameters postgresAdminPassword="$PG_PWD" \
  --parameters frontendUrl="<frontendUrl output from step 3>"
```

## Grant the deploy identity access to the frontend storage account

The frontend workflow uploads via Azure AD auth (`--auth-mode login`),
not an account key, so the same service principal used for
`AZURE_CREDENTIALS` needs the **Storage Blob Data Contributor** role on
the storage account:

```bash
az role assignment create \
  --assignee <AZURE_CREDENTIALS clientId> \
  --role "Storage Blob Data Contributor" \
  --scope $(az storage account show --name <frontendStorageAccountName output> \
              --resource-group mai-news-rg --query id -o tsv)
```

## CI/CD

`.github/workflows/deploy-backend.yml` rebuilds the image and rolls the
Container App on every push to `main` that touches backend code.

`.github/workflows/deploy-frontend.yml` builds the Next.js static export
and uploads it to the storage account's `$web` container on every push to
`main` that touches frontend code.

Set these GitHub secrets (Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `AZURE_CREDENTIALS` | output of `az ad sp create-for-rbac --name mai-news-deploy --role contributor --scopes /subscriptions/<sub>/resourceGroups/mai-news-rg --sdk-auth` |
| `AZURE_RESOURCE_GROUP` | `mai-news-rg` |
| `CONTAINER_APP_NAME` | `mainews-api` |
| `FRONTEND_STORAGE_ACCOUNT` | the `frontendStorageAccountName` Bicep output |
| `NEXT_PUBLIC_API_URL` | the deployed backend's API base, e.g. `https://mainews-api.<env>.azurecontainerapps.io/api/v1` |

## Cost watch

The single biggest cost driver after the 12-month free Postgres offer
expires is the database. After 12 months either:

- migrate to **Neon free tier** (still Postgres + pgvector, costs $0); or
- accept ~$13/mo for the Burstable B1ms on Azure (~$160/yr — would
  consume most of a renewed student credit).

Container Apps scale-to-zero keeps compute cost negligible at MVP
traffic. The hourly digest cron is ~30s of compute per fire = ~12
vCPU-minutes/day; well inside the free grant.

## Tear it all down

```bash
az group delete --name mai-news-rg --yes --no-wait
```
