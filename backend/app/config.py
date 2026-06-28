"""
Application configuration.

All runtime settings live here. Values are read from environment variables
(or a `.env` file in dev). Using pydantic-settings means:

  - Settings are type-checked at startup — wrong type or missing required
    value fails fast at boot, not at request time.
  - Each setting has one canonical name. No `os.environ.get(...)` scattered
    across the codebase.

To use anywhere in the app:

    from app.config import settings
    print(settings.database_url)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # Tells pydantic-settings to also load values from a `.env` file when present.
    # `extra="ignore"` means unknown env vars don't raise — useful when sharing
    # `.env` files across services.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ─── Runtime ──────────────────────────────────────────────────────────
    # "dev" enables conveniences like /auth/dev-login. Anything else
    # (typically "prod") disables them.
    env: str = "dev"

    # ─── Database ─────────────────────────────────────────────────────────
    # SQLAlchemy-style Postgres URL. The default targets the docker-compose
    # service at the repo root (`docker compose up postgres`). Override in
    # prod via DATABASE_URL — Azure Postgres Flexible Server, Neon, etc.
    #
    # Azure example (note `sslmode=require` and the `azuredb` query param for
    # managed identity if used):
    #   postgresql+psycopg://user:pass@host.postgres.database.azure.com:5432/db?sslmode=require
    #
    # pgvector must be enabled — on Azure that means adding `vector` to the
    # azure.extensions server parameter; on local Docker it ships in the
    # pgvector/pgvector image; on Neon it's pre-enabled.
    database_url: str = "postgresql+psycopg://mai:mai@localhost:5432/mai_news"

    # Dimensionality must match the embedding model:
    #   local (all-MiniLM-L6-v2) → 384
    #   gemini (text-embedding-004) → 768
    # Override via EMBEDDING_DIM if needed; otherwise set automatically below.
    embedding_dim: int = 384
    embedding_model: str = "all-MiniLM-L6-v2"
    # Gemini embedding model name — used when EMBEDDING_PROVIDER=gemini
    gemini_embedding_model: str = "text-embedding-004"

    @property
    def effective_embedding_dim(self) -> int:
        """Return the correct dim for the configured embedding provider."""
        if self.embedding_provider.lower() == "gemini":
            return 768
        return self.embedding_dim

    # ─── JWT (our own session token; see docs/auth.md §4) ─────────────────
    # HS256 + a symmetric secret. In production the secret lives in the
    # hosting platform's secret store (Render env vars, not a file).
    # Generate one with: python -c "import secrets; print(secrets.token_urlsafe(64))"
    jwt_secret: str = "dev-only-change-me-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "tech-intel-news"
    jwt_audience: str = "tech-intel-news-api"
    # Access token lifetime in minutes. 480 = 8 hours (comfortable dev session).
    jwt_ttl_minutes: int = 480

    # ─── Microsoft Entra ID (OAuth identity provider — primary) ───────────
    # The App Registration is created in a personal Microsoft tenant
    # because the deployment subscription's IE tenant blocks student
    # accounts from registering apps. Setting `entra_tenant_id` to
    # `common` puts MSAL in multi-tenant mode — tokens from ANY Entra
    # tenant (including @student.ie.edu accounts) are accepted, so users
    # don't need to be in your personal tenant to sign in.
    entra_tenant_id: str = ""
    entra_client_id: str = ""
    entra_client_secret: str = ""
    entra_redirect_uri: str = "http://localhost:8000/api/v1/auth/callback"

    # ─── Google OAuth (alternative provider, currently unused) ────────────
    # See app/auth/google.py — wired but not imported by the auth router.
    # Re-enable by swapping `from app.auth import entra as oauth` to
    # `from app.auth import google as oauth` in routers/auth.py.
    google_client_id: str = ""
    google_client_secret: str = ""
    oauth_redirect_uri: str = "http://localhost:8000/api/v1/auth/callback"

    # ─── Frontend ─────────────────────────────────────────────────────────
    # Where /auth/callback redirects the browser back to after a successful
    # login. The JWT is appended as a URL fragment (`#access_token=...`);
    # the frontend extracts it on load and clears the URL.
    # In prod: the Vercel deployment URL (e.g. https://tech-intel-news.vercel.app).
    frontend_url: str = "http://localhost:5173"

    # ─── CORS allowed origins (prod) ──────────────────────────────────────
    # In dev, main.py uses a fixed list of localhost dev-server ports so
    # FE devs don't need to configure anything. In prod, ONLY the origins
    # listed here can hit the API. Comma-separated string in the env var;
    # parsed into a list at boot.
    #   e.g. ALLOWED_ORIGINS="https://tech-intel-news.vercel.app"
    allowed_origins_raw: str = Field(default="", alias="ALLOWED_ORIGINS")

    @property
    def allowed_origins(self) -> list[str]:
        """Parse the comma-separated env var into a list, ignoring blanks."""
        return [o.strip() for o in self.allowed_origins_raw.split(",") if o.strip()]

    # ─── LLM provider ────────────────────────────────────────────────────
    # "openai" | "anthropic" | "gemini"
    # Gemini Flash is free-tier and recommended when cost matters.
    llm_provider: str = "openai"

    # Anthropic
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-6"
    llm_fast_model: str = "claude-haiku-4-5-20251001"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_fast_model: str = "gpt-4o-mini"

    # Google Gemini — free tier available at aistudio.google.com
    # gemini-2.0-flash is the recommended model (generous free quota).
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_fast_model: str = "gemini-2.0-flash"

    # ─── Embeddings ───────────────────────────────────────────────────────
    # "local"  → all-MiniLM-L6-v2 via sentence-transformers (384-dim, no key needed)
    # "gemini" → text-embedding-004 via Gemini API (768-dim, free tier, needs GEMINI_API_KEY)
    # IMPORTANT: changing provider requires re-ingesting all articles (different dim).
    embedding_provider: str = "local"

    # ─── Pipeline tuning ─────────────────────────────────────────────────
    max_tokens_newsletter: int = 2000
    max_tokens_chat: int = 3000
    retrieval_top_k: int = 8

    # ─── Observability ───────────────────────────────────────────────────
    log_level: str = "INFO"

    # ─── Email (Gmail SMTP) ────────────────────────────────────────────────
    # Outbound mail via Gmail SMTP SSL (port 465) + an App Password.
    # Steps to get an App Password:
    #   1. Enable 2-Step Verification on the sending Gmail account.
    #   2. myaccount.google.com → Security → App Passwords.
    #   3. Create one (name it "MAI News"), copy the 16-char code.
    #   4. Set both variables — never use your account password here.
    gmail_sender: str = ""
    gmail_app_password: str = ""

    # ─── Internal worker auth ─────────────────────────────────────────────
    # Shared secret used to authenticate calls to /api/v1/internal/*
    # (e.g. the digest worker webhook hit by GitHub Actions cron).
    # Set in production; left blank in dev means the internal endpoints
    # return 503 — keeps them safely closed by default.
    worker_shared_secret: str = ""

    @property
    def is_dev(self) -> bool:
        """Convenience: True when running in dev mode."""
        return self.env.lower() == "dev"


# A single shared instance — import this everywhere, don't construct your own.
settings = Settings()
