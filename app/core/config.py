import json
from typing import List, Optional

from pydantic import AnyHttpUrl, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# These strings used to be defaults. They are rejected so a copied
# example cannot boot the app with a known key.
_REJECTED_SECRET_KEYS = frozenset(
    {
        "your-secret-key-here",
        "replace-this-in-local-env",
    }
)


def _cors_origin_parts(value: object) -> List[str]:
    """Split a CORS setting into validated origin strings.

    pydantic-settings 2.1 JSON-decodes ``list`` fields before any
    validator runs, so a comma-separated env value crashed startup.
    Callers therefore keep the raw text in a ``str`` field and parse it
    here. A comma-separated string and a JSON list are both accepted.
    """
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "BACKEND_CORS_ORIGINS JSON list could not be parsed"
                ) from exc
            if not isinstance(parsed, list):
                raise ValueError(
                    "BACKEND_CORS_ORIGINS JSON value must be a list"
                )
            raw_items = parsed
        else:
            raw_items = [
                part.strip() for part in text.split(",") if part.strip()
            ]
    elif isinstance(value, (list, tuple)):
        raw_items = list(value)
    else:
        raise ValueError(
            "BACKEND_CORS_ORIGINS must be a comma-separated string "
            "or a JSON list"
        )

    origins: List[str] = []
    for item in raw_items:
        if not isinstance(item, str):
            raise ValueError("BACKEND_CORS_ORIGINS entries must be strings")
        try:
            url = AnyHttpUrl(item.strip())
        except ValidationError as exc:
            raise ValueError(
                "BACKEND_CORS_ORIGINS entry is not an http(s) URL: "
                f"{item!r}"
            ) from exc
        # AnyHttpUrl's string form has a trailing slash. Store that so
        # cors_origins can rebuild the same objects.
        origins.append(str(url))
    return origins


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Investment AI Companion"

    # Raw env text, not a list. See _cors_origin_parts. cors_origins is
    # the parsed list the rest of the app should read.
    BACKEND_CORS_ORIGINS: str = ""

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, value: object) -> str:
        return ",".join(_cors_origin_parts(value))

    @property
    def cors_origins(self) -> List[AnyHttpUrl]:
        """HTTP origins from BACKEND_CORS_ORIGINS, or an empty list."""
        if not self.BACKEND_CORS_ORIGINS:
            return []
        return [
            AnyHttpUrl(part) for part in self.BACKEND_CORS_ORIGINS.split(",")
        ]

    # Neutral login. Tests and the demo pass their own SQLite URL.
    DATABASE_URL: str = (
        "postgresql://investment_ai@localhost:5432/investment_ai"
    )
    REDIS_URL: str = "redis://localhost:6379/0"
    ELASTICSEARCH_URL: Optional[str] = None

    # API Keys
    OPENAI_API_KEY: str = ""  # Required, but empty by default
    NEWS_API_KEY: Optional[str] = None
    TWITTER_API_KEY: Optional[str] = None
    TWITTER_API_SECRET: Optional[str] = None
    TWITTER_ACCESS_TOKEN: Optional[str] = None
    TWITTER_ACCESS_TOKEN_SECRET: Optional[str] = None

    # Off unless a local .env turns it on. /test-config checks this flag.
    DEBUG: bool = False
    # No default. A missing value or a known placeholder fails startup.
    SECRET_KEY: str
    # Enforced by TrustedHostMiddleware in main.py. The test client
    # sends Host: 127.0.0.1, which is in this list. Starlette strips
    # the port before comparing.
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1"]

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_real(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or cleaned in _REJECTED_SECRET_KEYS:
            raise ValueError(
                "SECRET_KEY is required. Set a long random value in the "
                "environment. Known placeholders are rejected."
            )
        return cleaned

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # hide_input_in_errors stops a missing SECRET_KEY from printing the
    # whole settings dict (database URL, API keys) in the traceback.
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        hide_input_in_errors=True,
    )


settings = Settings()
