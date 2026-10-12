"""Application settings loaded from environment variables (and an optional ``.env`` file)."""

import logging
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

Environment = Literal["development", "test", "production"]

MIN_PRODUCTION_SECRET_KEY_LENGTH = 32
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
# Substrings found in the placeholder/example keys shipped in docs, .env.example and tests.
WEAK_SECRET_KEY_MARKERS: tuple[str, ...] = (
    "change",
    "your-",
    "secret-key",
    "example",
    "placeholder",
    "not-for-production",
)


class Settings(BaseSettings):
    """Typed application configuration.

    ``SECRET_KEY`` and ``DATABASE_URL`` are required. Third-party secrets default to an empty
    string so the app is importable in tests; :meth:`warn_missing_secrets` logs at startup when
    they are absent.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # App
    APP_NAME: str = "Assignment Roaster API"
    ENVIRONMENT: Environment = "development"
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str

    # Keys the HMAC that turns client IPs into daily-quota keys (raw IPs are never stored).
    SECRET_KEY: str = Field(min_length=1)

    # GitHub API (server token, read-only public access)
    GITHUB_API_TOKEN: str = ""

    # OpenAI (roast generation)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1-mini"

    # Roaster limits
    ROAST_DAILY_LIMIT: int = Field(default=5, ge=0)
    MAX_REPO_SIZE_MB: int = Field(default=50, gt=0)
    MAX_SAMPLED_FILES: int = Field(default=30, gt=0)
    # Retries allowed per submission after its first attempt (each also counts toward the quota).
    ROAST_MAX_RETRIES: int = Field(default=2, ge=0)
    # Pipelines (GitHub fetches + LLM call) allowed to run at once in this process.
    MAX_CONCURRENT_ROASTS: int = Field(default=3, gt=0)

    # URLs
    FRONTEND_URL: str = "http://localhost:5173"
    VITE_API_URL: str = "http://localhost:8000"

    @field_validator("DATABASE_URL")
    @classmethod
    def use_psycopg3_driver(cls, value: str) -> str:
        """Normalize plain ``postgresql://`` / ``postgres://`` URLs to the psycopg 3 driver.

        Args:
            value: Raw database URL from the environment.

        Returns:
            The URL with an explicit ``postgresql+psycopg://`` scheme when no driver is given.
        """
        for prefix in ("postgresql://", "postgres://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    @field_validator("FRONTEND_URL", "VITE_API_URL")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        """Remove a trailing slash so URLs can be joined and compared as CORS origins.

        Args:
            value: Raw URL from the environment.

        Returns:
            The URL without a trailing slash.
        """
        return value.rstrip("/")

    @model_validator(mode="after")
    def check_production_safety(self) -> "Settings":
        """Refuse to start in production with a weak ``SECRET_KEY`` or a non-HTTPS frontend.

        A placeholder key (for example the one in ``.env.example``) is public, so anyone could
        recompute the quota keys from IP addresses.

        Returns:
            The validated settings.

        Raises:
            ValueError: In production, when the key is shorter than
                :data:`MIN_PRODUCTION_SECRET_KEY_LENGTH`, contains a placeholder marker, or
                ``FRONTEND_URL`` is not ``https://`` (plain http is allowed only for a
                loopback host, so a local production-mode compose stack still starts).
        """
        if self.ENVIRONMENT != "production":
            return self
        key = self.SECRET_KEY.lower()
        if len(self.SECRET_KEY) < MIN_PRODUCTION_SECRET_KEY_LENGTH or any(
            marker in key for marker in WEAK_SECRET_KEY_MARKERS
        ):
            raise ValueError(
                "SECRET_KEY is weak or a placeholder; in production use at least "
                f"{MIN_PRODUCTION_SECRET_KEY_LENGTH} random characters "
                '(e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`).'
            )
        frontend = urlsplit(self.FRONTEND_URL)
        if frontend.scheme != "https" and frontend.hostname not in LOOPBACK_HOSTS:
            raise ValueError("FRONTEND_URL must use https:// in production.")
        return self

    @property
    def is_production(self) -> bool:
        """Return True when running in production."""
        return self.ENVIRONMENT == "production"

    @property
    def max_repo_size_kb(self) -> int:
        """Return the maximum repo size in KB (GitHub reports repo ``size`` in KB)."""
        return self.MAX_REPO_SIZE_MB * 1024

    def warn_missing_secrets(self) -> None:
        """Log a warning for each optional third-party secret that is not configured."""
        optional_secrets = {
            "GITHUB_API_TOKEN": self.GITHUB_API_TOKEN,
            "OPENAI_API_KEY": self.OPENAI_API_KEY,
        }
        for name, value in optional_secrets.items():
            if not value:
                logger.warning("%s is not set; related features will not work.", name)


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings (usable as a FastAPI dependency)."""
    return Settings()  # type: ignore[call-arg]


settings: Settings = get_settings()
