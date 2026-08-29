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

    # Database
    database_url: str = "sqlite:///./mandi.db"

    # CORS – comma-separated origins, e.g. "http://localhost:3000,https://example.com"
    cors_origins: list[str] = ["*"]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
