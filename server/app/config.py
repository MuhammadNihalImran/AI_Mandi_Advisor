from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    app_name: str = "AI Mandi Advisor API"
    debug: bool = False

    # Groq LLM
    groq_api_key: str = ""
    # Per-request timeout for Groq API calls in seconds. The SDK default
    # (~10 minutes) would let advice requests hang for far too long.
    groq_timeout_seconds: float = 30.0

    # Database
    database_url: str = "sqlite:///./mandi.db"

    # CORS – JSON list of origins, e.g. '["http://localhost:5173"]'
    # (pydantic-settings parses list fields as JSON; comma-separated
    # values are invalid and crash startup)
    cors_origins: list[str] = ["*"]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
