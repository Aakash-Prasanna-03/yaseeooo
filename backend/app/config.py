from functools import lru_cache
from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_jwt_secret: Optional[str] = None

    database_url: str = "postgresql://postgres:postgres@localhost:54322/postgres"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    google_api_key: Optional[str] = None
    llm_provider: Literal["gemini", "openai", "ollama"] = "gemini"
    openai_api_key: Optional[str] = None
    openai_pro_model: str = "gpt-4o-mini"
    openai_flash_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_pro_model: str = "qwen2.5:7b"
    ollama_flash_model: str = "qwen2.5:3b"
    pinecone_api_key: Optional[str] = None
    pinecone_index: Optional[str] = None
    pinecone_environment: Optional[str] = None

    dataforseo_login: Optional[str] = None
    dataforseo_password: Optional[str] = None
    ahrefs_api_key: Optional[str] = None

    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None
    reddit_user_agent: str = "yeseeeooo/1.0"

    linkedin_client_id: Optional[str] = None
    linkedin_client_secret: Optional[str] = None

    medium_integration_token: Optional[str] = None

    wordpress_base_url: Optional[str] = None
    wordpress_user: Optional[str] = None
    wordpress_app_password: Optional[str] = None

    quora_automation_enabled: bool = False

    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None

    sentry_dsn: Optional[str] = None
    posthog_api_key: Optional[str] = None
    posthog_host: str = "https://us.i.posthog.com"

    geo_monitoring_mock: bool = True

    # Defaults avoid retired / free-tier-blocked IDs; override via GEMINI_PRO / GEMINI_FLASH in .env.
    gemini_pro: str = "gemini-2.0-flash"
    gemini_flash: str = "gemini-2.0-flash-lite"


@lru_cache
def get_settings() -> Settings:
    return Settings()
