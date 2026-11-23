from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    database_url: str = "postgresql+psycopg://subauditor:subauditor@localhost:5432/subscription_auditor"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    # When true, Celery runs tasks inline (no Redis/worker needed). Local-dev only.
    celery_eager: bool = False

    # Auth
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080

    # Token encryption (base64 32-byte key). If empty, a dev key is derived from jwt_secret.
    token_encryption_key: str = ""

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/connections/gmail/callback"

    # LLM (optional)
    openai_api_key: str = ""
    # Cheapest capable chat model by default (nano tier). Override via OPENAI_MODEL.
    openai_model: str = "gpt-5.4-nano"
    # Use the LLM to parse receipt emails (needs openai_api_key). Rule-based
    # parser is used as a fallback on any failure. Safety cap on LLM calls/scan.
    llm_receipt_parsing: bool = True
    llm_parse_max_messages: int = 300
    # Emails sent per LLM request (batching cuts cost/latency), and the minimum
    # model confidence (0..1) to trust an extraction before falling back to rules.
    llm_parse_batch_size: int = 10
    llm_parse_min_confidence: float = 0.6

    # Email
    resend_api_key: str = ""
    from_email: str = "alerts@subscription-auditor.app"

    # App
    frontend_url: str = "http://localhost:3000"
    renewal_lead_days: int = 2
    # How far back the Gmail scan looks for receipt emails, and the most a user may pick.
    gmail_scan_days: int = 90
    gmail_scan_max_days: int = 90
    # Safety cap on messages fetched per scan.
    gmail_scan_max_messages: int = 2000


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
