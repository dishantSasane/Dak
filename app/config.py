"""Configuration.

Every variable from 02-architecture.md §11. Fails loudly at startup on a
missing required value (pydantic-settings raises ValidationError naming the
missing field).
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Required (no defaults) -------------------------------------------
    DATABASE_URL: str = Field(min_length=1)
    REDIS_URL: str = Field(min_length=1)
    GEMINI_API_KEY: str = ""
    CLOUDMAILIN_SECRET: str = ""

    # --- Hosted demo access ------------------------------------------------
    APP_ENV: Literal["development", "production"] = "development"
    APP_ROLE: Literal["development", "web", "worker"] = "development"
    DASHBOARD_PASSWORD: str = ""
    RUN_INLINE_WORKER: bool = False

    # --- Models ------------------------------------------------------------
    GEMINI_MODEL_TRIAGE: str = "gemini-3.1-flash-lite"
    GEMINI_MODEL_DRAFT: str = "gemini-3-flash"

    # --- Tracing -----------------------------------------------------------
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # --- Thresholds and limits (all configuration, never literals in code) -
    CONFIDENCE_THRESHOLD: float = 0.70
    AUTO_SEND_ENABLED: bool = False
    AUTO_SEND_MIN_CONFIDENCE: float = 0.90
    SEMANTIC_CACHE_THRESHOLD: float = 0.95
    CORPUS_VERSION: int = 1
    MAX_VALIDATOR_RETRIES: int = 1
    MAX_REROUTES: int = 1
    WORKER_CONCURRENCY: int = 2
    RPM_LIMIT: int = 10

    # --- Branding / behaviour ----------------------------------------------
    INSURER_NAME: str = "Vantara General Insurance"
    ALLOW_UNSIGNED_WEBHOOK: bool = False

    # --- Retrieval ----------------------------------------------------------
    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_SCORE_FLOOR: float = 0.30

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def use_asyncpg_driver(cls, value: str) -> str:
        """Render exposes standard PostgreSQL URLs; SQLAlchemy needs asyncpg."""
        if value.startswith("postgres://"):
            return "postgresql+asyncpg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value.removeprefix("postgresql://")
        return value

    @model_validator(mode="after")
    def production_access_is_configured(self) -> "Settings":
        if self.APP_ENV == "production":
            if self.APP_ROLE == "development":
                raise ValueError("Production requires APP_ROLE=web or APP_ROLE=worker")
            if self.ALLOW_UNSIGNED_WEBHOOK:
                raise ValueError("ALLOW_UNSIGNED_WEBHOOK must be false in production")
            if self.ALLOW_UNSIGNED_WEBHOOK:
                raise ValueError("ALLOW_UNSIGNED_WEBHOOK must be false in production")
        if self.APP_ENV == "production" and self.APP_ROLE == "web":
            if self.DASHBOARD_PASSWORD and len(self.DASHBOARD_PASSWORD) < 16:
                raise ValueError(
                    "DASHBOARD_PASSWORD must be at least 16 characters when configured"
                )
            if not self.CLOUDMAILIN_SECRET:
                raise ValueError("Production web role requires CLOUDMAILIN_SECRET")
        if self.APP_ENV == "production" and self.APP_ROLE == "worker" and not self.GEMINI_API_KEY:
            raise ValueError("Production worker role requires GEMINI_API_KEY")
        if (
            self.APP_ENV == "production"
            and self.APP_ROLE == "web"
            and self.RUN_INLINE_WORKER
            and not self.GEMINI_API_KEY
        ):
            raise ValueError("Production inline worker requires GEMINI_API_KEY")
        return self


def _load_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        missing = [str(e["loc"][0]) for e in exc.errors() if e.get("type") == "missing"]
        if missing:
            raise ConfigError(
                "Missing required environment variable(s): " + ", ".join(missing)
            ) from exc
        raise ConfigError(str(exc)) from exc


@lru_cache
def get_settings() -> Settings:
    return _load_settings()


settings = get_settings()
