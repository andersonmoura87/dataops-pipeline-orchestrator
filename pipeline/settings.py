from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # asyncpg DSN, e.g. postgresql+asyncpg://user:pass@host/db
    database_url: str = "postgresql+asyncpg://dataops:changeme@localhost/dataops"

    schedule_hours: int = Field(default=6, ge=1)
    metrics_port: int = Field(default=8080, ge=1, le=65535)
    http_timeout: float = Field(default=30.0, gt=0)

    log_level: str = "INFO"
