import json
from typing import List, Optional
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# These strings used to be defaults. They are rejected so a copied
# example cannot boot the app with a known key. Comparison is
# case-insensitive: YOUR-SECRET-KEY-HERE is the same placeholder.
_REJECTED_SECRET_KEYS = frozenset(
    {
        "your-secret-key-here",
        "replace-this-in-local-env",
    }
)
# token_urlsafe(32) is 43 characters. 32 is the shortest value we accept.
_MIN_SECRET_KEY_LENGTH = 32


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
        origins.append(_bare_http_origin(item))
    return origins


def _bare_http_origin(item: str) -> str:
    """Accept only ``scheme://host[:port]`` with an optional root path.

    A path, userinfo, query, fragment, or wildcard is not an origin a
    browser sends. ``http://localhost:3000/`` is the same origin as
    ``http://localhost:3000`` and is stored without the slash.

    IPv6 origins are not supported for now. ``urlsplit`` returns the
    host without brackets, and ``AnyHttpUrl`` cannot accept that
    form, so ``http://[::1]:3000`` is rejected instead of rebuilt.
    """
    text = item.strip()
    if "*" in text:
        raise ValueError(
            "BACKEND_CORS_ORIGINS entry must not contain '*': " f"{item!r}"
        )
    parts = urlsplit(text)
    if parts.scheme not in {"http", "https"}:
        raise ValueError(
            "BACKEND_CORS_ORIGINS entry is not an http(s) URL: " f"{item!r}"
        )
    if parts.username or parts.password:
        # Do not include the origin. It contains the username and password.
        raise ValueError(
            "BACKEND_CORS_ORIGINS entry must not include userinfo"
        )
    if parts.query or parts.fragment:
        raise ValueError(
            "BACKEND_CORS_ORIGINS entry must not include a query "
            f"or fragment: {item!r}"
        )
    if parts.path not in ("", "/"):
        raise ValueError(
            "BACKEND_CORS_ORIGINS entry must not include a path: " f"{item!r}"
        )
    host = parts.hostname
    if not host:
        raise ValueError(
            "BACKEND_CORS_ORIGINS entry is not an http(s) URL: " f"{item!r}"
        )
    # An IPv6 hostname contains ":". Re-bracketing it never ran:
    # AnyHttpUrl below is built without brackets and rejects "::1".
    if ":" in host:
        raise ValueError(
            "IPv6 origins are not supported in BACKEND_CORS_ORIGINS "
            f"yet: {item!r}"
        )
    try:
        # Reject a host AnyHttpUrl does not consider an HTTP URL.
        AnyHttpUrl(f"{parts.scheme}://{host}")
    except ValidationError as exc:
        raise ValueError(
            "BACKEND_CORS_ORIGINS entry is not an http(s) URL: " f"{item!r}"
        ) from exc
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{host}{port}"


def _allowed_host_parts(value: object) -> List[str]:
    """Split ALLOWED_HOSTS into hostnames with no port and no wildcard.

    pydantic-settings 2.1 JSON-decodes a ``list`` field before any
    validator, so ``localhost,127.0.0.1`` crashed startup. The field
    stays a string. Starlette removes the port from the Host header
    before it compares, so a configured host that includes a port
    would never match. ``*`` would accept every Host header.
    """
    if value is None:
        raise ValueError("ALLOWED_HOSTS must list at least one host")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("ALLOWED_HOSTS must list at least one host")
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "ALLOWED_HOSTS JSON list could not be parsed"
                ) from exc
            if not isinstance(parsed, list):
                raise ValueError("ALLOWED_HOSTS JSON value must be a list")
            raw_items = parsed
        else:
            # Keep empty pieces so "localhost,,127.0.0.1" is rejected.
            raw_items = [part.strip() for part in text.split(",")]
    elif isinstance(value, (list, tuple)):
        raw_items = list(value)
    else:
        raise ValueError(
            "ALLOWED_HOSTS must be a comma-separated string or a JSON list"
        )

    hosts: List[str] = []
    for item in raw_items:
        if not isinstance(item, str):
            raise ValueError("ALLOWED_HOSTS entries must be strings")
        host = item.strip()
        if not host:
            raise ValueError("ALLOWED_HOSTS entries must not be empty")
        if "*" in host:
            raise ValueError("ALLOWED_HOSTS must not contain '*'")
        if ":" in host:
            raise ValueError(
                "ALLOWED_HOSTS entries must not include a port: " f"{host!r}"
            )
        hosts.append(host)
    if not hosts:
        raise ValueError("ALLOWED_HOSTS must list at least one host")
    return hosts


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
    # Empty default so a missing value reaches the validator. Without
    # it, pydantic stops at "Field required" and never shows how to
    # generate a key. validate_default runs that check on the "".
    SECRET_KEY: str = Field(default="", validate_default=True)
    # Raw env text. allowed_hosts is the list TrustedHostMiddleware
    # reads. See _allowed_host_parts. The test client sends
    # Host: 127.0.0.1. Starlette strips the port before comparing,
    # so this list must not include ports.
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def assemble_allowed_hosts(cls, value: object) -> str:
        return ",".join(_allowed_host_parts(value))

    @property
    def allowed_hosts(self) -> List[str]:
        """Hostnames from ALLOWED_HOSTS."""
        if not self.ALLOWED_HOSTS:
            return []
        return [part for part in self.ALLOWED_HOSTS.split(",") if part]

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_real(cls, value: str) -> str:
        cleaned = value.strip()
        if (
            len(cleaned) < _MIN_SECRET_KEY_LENGTH
            or cleaned.casefold() in _REJECTED_SECRET_KEYS
        ):
            raise ValueError(
                "SECRET_KEY is required. Set a random value of at least "
                f"{_MIN_SECRET_KEY_LENGTH} characters. Known placeholders "
                "are rejected in any case. Generate one with "
                'python -c "import secrets; print(secrets.token_urlsafe(32))".'
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
