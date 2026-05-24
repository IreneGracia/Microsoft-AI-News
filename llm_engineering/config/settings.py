from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # LLM provider: "anthropic" | "openai"
    llm_provider: str = "anthropic"

    # Anthropic
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-6"
    llm_fast_model: str = "claude-haiku-4-5-20251001"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_fast_model: str = "gpt-4o-mini"

    # News retrieval
    tavily_api_key: str = ""
    news_api_key: str = ""

    # Vector store
    chroma_persist_dir: str = "./data/chroma_db"
    embedding_model: str = "all-MiniLM-L6-v2"  # lightweight, 384-dim

    # Token economy — max tokens per newsletter generation call
    max_tokens_newsletter: int = 2000
    max_tokens_chat: int = 1500
    # How many articles to pass to the LLM (retrieved context window)
    retrieval_top_k: int = 8

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # Email (SMTP)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""


settings = Settings()
