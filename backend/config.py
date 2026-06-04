"""Application settings loaded from environment variables.

All values can be overridden via a .env file (see .env.example).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the quarry extraction pipeline."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://quarry:quarry@localhost:5432/quarry"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # OpenAI
    openai_api_key: str = ""

    # Overpass API — override to use a private instance and avoid rate limits
    overpass_url: str = "https://overpass-api.de/api/interpreter"

    # Scraper
    scraper_user_agent: str = "QuarryBot/1.0 (research; contact@example.com)"
    max_pages_per_quarry: int = 5
    base_scrape_delay_s: float = 1.0

    # App
    log_level: str = "INFO"


settings = Settings()
