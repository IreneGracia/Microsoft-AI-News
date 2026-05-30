// Azure deployment for the Microsoft-AI-News backend.
//
// Sized for the Azure for Students ($100/yr) credit ceiling. The cheapest
// production-grade stack on Azure that keeps the backend on Azure end-to-end:
//
//   - Azure Database for PostgreSQL Flexible Server, Burstable B1ms
//     (free for the first 12 months on a new account; ~$13/month after).
//     `vector` extension is allowlisted via azure.extensions so pgvector works.
//
//   - Container Apps Environment (consumption plan) hosting the backend.
//     The free monthly grant is 180k vCPU-seconds + 360k GB-seconds, which
//     is more than enough at MVP scale if scale-to-zero is enabled.
//
//   - Static Web App on the Free tier for the Next.js frontend.
//
//   - Log Analytics workspace (Container Apps requires one; ~$2 GB/month
//     ingested, the 5 GB free monthly grant covers MVP traffic).
//
// Container images are pulled from GitHub Container Registry (ghcr.io),
// which is free for public repos — keeps us off Azure Container Registry
// ($5/mo Basic tier minimum).
//
// Deploy:
//   az login
//   az group create --name mai-news-rg --location francecentral
// (This subscription has TWO stacked region policies:
//   - subscription-level: francecentral, spaincentral, germanywestcentral,
//                         swedencentral, austriaeast
//   - management-group-level: europe, northeurope, westeurope,
//                             francecentral, uksouth, switzerlandnorth,
//                             swedencentral
// The intersection — the only regions allowed by BOTH — is
// francecentral and swedencentral. francecentral is the default:
// closer to Spain, lower latency, EUR pricing.)
//   az deployment group create \
//     --resource-group mai-news-rg \
//     --template-file infra/main.bicep \
//     --parameters infra/main.parameters.json \
//     --parameters postgresAdminPassword=$(openssl rand -base64 24)
//
// After deploy, set the runtime secrets on the Container App:
//   az containerapp secret set --name mai-news-api --resource-group mai-news-rg \
//     --secrets jwt-secret=... entra-client-secret=... openai-api-key=... \
//               anthropic-api-key=... worker-shared-secret=...

targetScope = 'resourceGroup'

// ─── Parameters ───────────────────────────────────────────────────────

@description('Location for all resources. Inherits from the resource group. Stacked subscription + management-group region policies restrict this deployment to francecentral or swedencentral — francecentral is the default.')
param location string = resourceGroup().location

@description('Short project name. Used as a prefix for resource names. Lowercase letters/numbers only.')
@minLength(3)
@maxLength(16)
param projectName string = 'mainews'

@description('Image reference for the backend container. Format: ghcr.io/<owner>/<repo>:<tag>')
param backendImage string = 'ghcr.io/bertolikimberly/microsoft-ai-news-backend:latest'

@description('Initial Postgres admin username.')
param postgresAdminUser string = 'mai_admin'

@description('Postgres admin password. Pass via --parameters at deploy time; do not commit.')
@secure()
param postgresAdminPassword string

@description('Frontend origin allowed by backend CORS. Update once Static Web App URL is known.')
param frontendUrl string = ''

@description('Container registry hostname. Leave empty for public images (no auth). For ghcr.io with a private package, set to "ghcr.io" and supply registryUsername + registryPassword.')
param registryServer string = ''

@description('Container registry username. For ghcr.io this is a GitHub username with read:packages on the image.')
param registryUsername string = ''

@description('Container registry password / token. For ghcr.io this is a GitHub PAT with the read:packages scope. Pass via --parameters at deploy time; do not commit.')
@secure()
param registryPassword string = ''

// ─── Names (composed from projectName + uniqueness suffix) ────────────

var uniqueSuffix = uniqueString(resourceGroup().id)
var postgresName = '${projectName}-pg-${uniqueSuffix}'
var containerAppEnvName = '${projectName}-cae'
var containerAppName = '${projectName}-api'
// var staticWebAppName = '${projectName}-web'  // re-enable with the SWA resource below
var logAnalyticsName = '${projectName}-logs'
var emailServiceName = '${projectName}-email'
var communicationServiceName = '${projectName}-comms'

// ─── Log Analytics (Container Apps needs a workspace) ────────────────

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// ─── Postgres Flexible Server ────────────────────────────────────────

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2023-12-01-preview' = {
  name: postgresName
  location: location
  sku: {
    // Burstable B1ms is the cheapest tier and qualifies for the
    // 12-month free offer on new Azure accounts.
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: postgresAdminUser
    administratorLoginPassword: postgresAdminPassword
    storage: {
      storageSizeGB: 32
      autoGrow: 'Disabled'
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    network: {
      // Public endpoint with firewall rules for simplicity; production
      // should switch to private DNS + VNet integration.
      publicNetworkAccess: 'Enabled'
    }
  }
}

// Allow Azure-internal services (Container Apps) to reach the DB.
// Specific Container App egress IPs are not stable on the consumption
// plan; the 0.0.0.0 rule below is the standard "allow Azure services"
// shortcut. Combine with strong auth + sslmode=require.
resource postgresAllowAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-12-01-preview' = {
  parent: postgres
  name: 'AllowAllAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// Allowlist the pgvector extension at the server level. Without this,
// `CREATE EXTENSION vector` (run by the backend at startup) fails.
resource postgresExtensions 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2023-12-01-preview' = {
  parent: postgres
  name: 'azure.extensions'
  properties: {
    value: 'VECTOR'
    source: 'user-override'
  }
}

resource postgresDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-12-01-preview' = {
  parent: postgres
  name: 'mai_news'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// ─── Container Apps environment ──────────────────────────────────────

resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerAppEnvName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

// ─── Container App (backend) ─────────────────────────────────────────

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        // Required so the backend's CORS middleware sees correct origins.
        corsPolicy: {
          allowCredentials: true
          allowedHeaders: ['*']
          allowedMethods: ['*']
          allowedOrigins: empty(frontendUrl) ? ['*'] : [frontendUrl]
        }
      }
      // Runtime secrets — values are placeholders; replace with
      // `az containerapp secret set` after the initial deployment.
      // sentinel value `replace-me` makes accidental boots loud.
      // The registry-password entry is only included when pulling from
      // a private registry (registryServer != '').
      secrets: empty(registryServer) ? [
        { name: 'database-url', value: 'postgresql+psycopg://${postgresAdminUser}:${postgresAdminPassword}@${postgres.properties.fullyQualifiedDomainName}:5432/mai_news?sslmode=require' }
        { name: 'jwt-secret', value: 'replace-me' }
        { name: 'google-client-id', value: 'replace-me' }
        { name: 'google-client-secret', value: 'replace-me' }
        { name: 'openai-api-key', value: 'replace-me' }
        { name: 'anthropic-api-key', value: 'replace-me' }
        { name: 'acs-connection-string', value: communicationService.listKeys().primaryConnectionString }
        { name: 'acs-sender-address', value: 'DoNotReply@${azureManagedDomain.properties.fromSenderDomain}' }
        { name: 'worker-shared-secret', value: 'replace-me' }
      ] : [
        { name: 'database-url', value: 'postgresql+psycopg://${postgresAdminUser}:${postgresAdminPassword}@${postgres.properties.fullyQualifiedDomainName}:5432/mai_news?sslmode=require' }
        { name: 'jwt-secret', value: 'replace-me' }
        { name: 'google-client-id', value: 'replace-me' }
        { name: 'google-client-secret', value: 'replace-me' }
        { name: 'openai-api-key', value: 'replace-me' }
        { name: 'anthropic-api-key', value: 'replace-me' }
        { name: 'acs-connection-string', value: communicationService.listKeys().primaryConnectionString }
        { name: 'acs-sender-address', value: 'DoNotReply@${azureManagedDomain.properties.fromSenderDomain}' }
        { name: 'worker-shared-secret', value: 'replace-me' }
        { name: 'registry-password', value: registryPassword }
      ]
      // Private registry credentials (e.g. ghcr.io with a private package).
      // When registryServer is empty the array is empty and Container Apps
      // pulls anonymously, which works for public images.
      registries: empty(registryServer) ? [] : [
        {
          server: registryServer
          username: registryUsername
          passwordSecretRef: 'registry-password'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: backendImage
          resources: {
            // 0.5 vCPU / 1 GiB is the sweet spot for FastAPI + the
            // sentence-transformers model (~500MB in RAM after load).
            // Smaller will OOM during embedding inference.
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'ENV', value: 'prod' }
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'JWT_SECRET', secretRef: 'jwt-secret' }
            { name: 'JWT_ALGORITHM', value: 'HS256' }
            { name: 'JWT_ISSUER', value: 'tech-intel-news' }
            { name: 'JWT_AUDIENCE', value: 'tech-intel-news-api' }
            { name: 'JWT_TTL_MINUTES', value: '30' }
            { name: 'GOOGLE_CLIENT_ID', secretRef: 'google-client-id' }
            { name: 'GOOGLE_CLIENT_SECRET', secretRef: 'google-client-secret' }
            // Deterministic FQDN for the Container App = <appname>.<env-default-domain>.
            // Computing it here means the redirect URI is correct from the
            // first deploy without a second pass. Don't forget to ALSO add
            // this exact URL to the Google OAuth client's "Authorized
            // redirect URIs" list (Google Cloud Console → Credentials →
            // OAuth 2.0 Client IDs → Web client → Edit).
            { name: 'OAUTH_REDIRECT_URI', value: 'https://${containerAppName}.${containerAppEnv.properties.defaultDomain}/api/v1/auth/callback' }
            { name: 'OPENAI_API_KEY', secretRef: 'openai-api-key' }
            { name: 'ANTHROPIC_API_KEY', secretRef: 'anthropic-api-key' }
            { name: 'ACS_CONNECTION_STRING', secretRef: 'acs-connection-string' }
            { name: 'ACS_SENDER_ADDRESS', secretRef: 'acs-sender-address' }
            { name: 'WORKER_SHARED_SECRET', secretRef: 'worker-shared-secret' }
            { name: 'FRONTEND_URL', value: frontendUrl }
            { name: 'ALLOWED_ORIGINS', value: frontendUrl }
            { name: 'EMBEDDING_MODEL', value: 'all-MiniLM-L6-v2' }
            { name: 'EMBEDDING_DIM', value: '384' }
            // L4 — RSS fetcher writes per-source watermarks here. The backend's
            // digest worker (app/integrations/fetch_state.py) brackets each
            // run with restore-from / save-to Postgres so state survives the
            // Container Apps scale-to-zero recycle. /tmp is fine because the
            // restore/save is the durability layer.
            { name: 'FETCH_STATE_PATH', value: '/tmp/fetch_state.json' }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/api/v1/health/live'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/api/v1/health/ready'
                port: 8000
              }
              // Allow extra time on cold start while pgvector extension
              // creation + sentence-transformers warm-up complete.
              initialDelaySeconds: 30
              periodSeconds: 30
              failureThreshold: 5
            }
          ]
        }
      ]
      scale: {
        // Scale-to-zero is the cost-saver: when no requests come in
        // (between hourly cron fires) the app uses zero compute.
        minReplicas: 0
        maxReplicas: 3
        rules: [
          {
            name: 'http-rule'
            http: {
              metadata: {
                concurrentRequests: '20'
              }
            }
          }
        ]
      }
    }
  }
  dependsOn: [
    postgresDatabase
    postgresExtensions
    postgresAllowAzure
  ]
}

// ─── Azure Communication Services (transactional email) ─────────────
//
// Three resources work together:
//   - Email Communication Service: namespace for email domains
//   - Azure Managed Domain: free `<random>.azurecomm.net` sender, no DNS
//     verification required (swap to a custom domain later for branded
//     mail). The `DoNotReply@<domain>` username is fixed for managed
//     domains.
//   - Communication Service: the connection-string-bearing resource that
//     the SDK actually talks to. Linked to the email domain so the
//     sender address resolves.
//
// All three are `location: 'global'` (the ACS control plane is global);
// `dataLocation: 'Europe'` keeps the message data + customer info in EU
// regions. This sidesteps the subscription's region policy because
// `global` is always allowed.

resource emailService 'Microsoft.Communication/emailServices@2023-04-01' = {
  name: emailServiceName
  location: 'global'
  properties: {
    dataLocation: 'Europe'
  }
}

resource azureManagedDomain 'Microsoft.Communication/emailServices/domains@2023-04-01' = {
  parent: emailService
  name: 'AzureManagedDomain'
  location: 'global'
  properties: {
    domainManagement: 'AzureManaged'
    userEngagementTracking: 'Disabled'
  }
}

resource communicationService 'Microsoft.Communication/communicationServices@2023-04-01' = {
  name: communicationServiceName
  location: 'global'
  properties: {
    dataLocation: 'Europe'
    linkedDomains: [
      azureManagedDomain.id
    ]
  }
}

// ─── Static Web App (frontend) ───────────────────────────────────────
//
// DISABLED for this subscription: Microsoft.Web/staticSites is only
// available in centralus, eastus2, westus2, westeurope, eastasia —
// none of which intersect with this subscription's stacked region
// policies (allowed EU set: francecentral, swedencentral). Re-enable
// once on a subscription without the region restriction, or pair with
// an Azure Storage static website in francecentral as a substitute.
//
// resource staticWebApp 'Microsoft.Web/staticSites@2023-12-01' = {
//   name: staticWebAppName
//   location: location
//   sku: {
//     name: 'Free'
//     tier: 'Free'
//   }
//   properties: {
//     // GitHub linkage is configured by the SWA GitHub Action workflow at
//     // deploy time, not in IaC, so we leave repositoryUrl empty here.
//     provider: 'Custom'
//   }
// }

// ─── Outputs ─────────────────────────────────────────────────────────

output backendUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output postgresFqdn string = postgres.properties.fullyQualifiedDomainName
output postgresDatabaseName string = postgresDatabase.name
// output staticWebAppDefaultHostname string = staticWebApp.properties.defaultHostname
// output staticWebAppName string = staticWebApp.name
