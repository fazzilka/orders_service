import json
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_title: str = "Orders Service"
    api_version: str = "0.1.0"
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    database_url: str = Field(validation_alias="DATABASE_URL")
    redis_url: str = Field(validation_alias="REDIS_URL")
    rabbitmq_url: str = Field(validation_alias="RABBITMQ_URL")

    jwt_secret_key: str = Field(validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=30, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    refresh_token_expire_days: int = Field(default=7, validation_alias="REFRESH_TOKEN_EXPIRE_DAYS")

    cors_origins_raw: str = Field(default="", validation_alias="CORS_ORIGINS")

    rate_limit_storage_uri: str | None = Field(
        default=None, validation_alias="RATE_LIMIT_STORAGE_URI"
    )
    rate_limit_token: str = Field(default="5/minute", validation_alias="RATE_LIMIT_TOKEN")
    rate_limit_orders: str = Field(default="20/minute", validation_alias="RATE_LIMIT_ORDERS")

    rabbit_exchange: str = Field(default="orders.events", validation_alias="RABBIT_EXCHANGE")
    rabbit_queue: str = Field(default="orders.new_order", validation_alias="RABBIT_QUEUE")
    rabbit_routing_key: str = Field(default="new_order", validation_alias="RABBIT_ROUTING_KEY")

    celery_broker_url: str = Field(validation_alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(validation_alias="CELERY_RESULT_BACKEND")

    cache_ttl_seconds: int = Field(default=300, validation_alias="CACHE_TTL_SECONDS")

    @property
    def cors_origins(self) -> list[str]:
        raw = (self.cors_origins_raw or "").strip()
        if not raw:
            return []

        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None

            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]

        return [item.strip() for item in raw.split(",") if item.strip()]


settings = Settings()  # type: ignore[call-arg]


@lru_cache
def get_settings() -> Settings:
    return settings
