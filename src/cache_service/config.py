"""Server configuration, read from ``CACHE_*`` environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CACHE_")

    database_url: str = "sqlite:///./data/cache.db"

    # Lets a demo/CLI run with ``--repeat`` visibly show the cache at work,
    # since the real transformer is an external (slow) service.
    transform_latency_seconds: float = Field(default=0.0, ge=0)
