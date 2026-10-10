"""Configuration.

Every variable from 02-architecture.md §11. Fails loudly at startup on a
missing required value (pydantic-settings raises ValidationError naming the
missing field).
"""

from functools import lru_cache

from pydantic import ValidationError
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
    DATABASE_URL: str
    REDIS_URL: str
    GEMINI_API_KEY: str
    CLOUDMAILIN_SECRET: str

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


def _load_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        missing = [
            str(e["loc"][0]) for e in exc.errors() if e.get("type") == "missing"
        ]
        if missing:
            raise ConfigError(
                "Missing required environment variable(s): " + ", ".join(missing)
            ) from exc
        raise ConfigError(str(exc)) from exc


@lru_cache
def get_settings() -> Settings:
    return _load_settings()


# Module-level accessor. Importing this module with an incomplete environment
# raises ConfigError naming the missing variable(s).
try:  # pragma: no cover - exercised via tests with patched env
    settings = get_settings()
except ConfigError:
    settings = None  # type: ignore[assignment]
