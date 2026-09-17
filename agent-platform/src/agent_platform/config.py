from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://agent_platform:agent_platform@localhost:5433/agent_platform"

    anthropic_api_key: str | None = None
    anthropic_base_url: str | None = None
    anthropic_default_model: str = "claude-sonnet-4-6"
    anthropic_timeout_seconds: float = 120.0
    anthropic_default_max_output_tokens: int = 4096


@lru_cache
def get_settings() -> Settings:
    return Settings()
