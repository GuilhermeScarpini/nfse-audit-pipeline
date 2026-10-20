from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Read from environment variables (or a .env file). See .env.example."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"
    data_dir: Path = Path("data")
    queue_name: str = "audits"
    log_level: str = "INFO"
    max_files_per_batch: int = 500
    max_file_bytes: int = 5 * 1024 * 1024
    job_timeout_seconds: int = 600
    idempotency_ttl_seconds: int = 24 * 60 * 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
