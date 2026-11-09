import logging
import secrets
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)


class Settings(BaseSettings):
    app_name: str = "SkillPath Navigator"
    environment: Literal["development", "production"] = "development"
    secret_key: str = ""
    access_token_expire_minutes: int = 120
    database_url: str = "sqlite:///./skillpath.db"

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_fast_model: str = "openai/gpt-oss-20b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    ai_timeout_seconds: float = 45
    ai_max_retries: int = 2

    frontend_origins: str = "http://127.0.0.1:5500,http://localhost:5500"
    serve_frontend: bool = True
    seed_demo_user: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def signing_key() -> str:
    """The JWT signing key.

    Production refuses to start without an explicit key. In development a random per-process key is used,
    which means sessions end whenever the server restarts; set SECRET_KEY to keep them.
    """
    settings = get_settings()
    if settings.secret_key:
        if len(settings.secret_key) < 32:
            raise RuntimeError("SECRET_KEY must be at least 32 characters.")
        return settings.secret_key
    if settings.environment == "production":
        raise RuntimeError("SECRET_KEY is required when ENVIRONMENT=production.")
    log.warning("SECRET_KEY not set: using a temporary key, logins will not survive a restart.")
    return secrets.token_urlsafe(48)


settings = get_settings()
