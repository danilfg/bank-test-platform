from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    project_name: str = "demo-bank"
    training_mode: bool = True
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://demobank:demobank@postgres:5432/demobank"
    redis_url: str = "redis://redis:6379/0"
    kafka_bootstrap_servers: str = "kafka:9092"

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_expires_minutes: int = 15
    jwt_refresh_expires_days: int = 7

    elasticsearch_url: str = "http://elasticsearch:9200"
    jaeger_endpoint: str = "http://jaeger:4318"


@lru_cache
def get_settings() -> Settings:
    return Settings()
