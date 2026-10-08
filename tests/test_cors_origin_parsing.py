"""Settings.BACKEND_CORS_ORIGINS accepts JSON lists and comma strings."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_comma_separated_origins_are_split_and_trimmed():
    settings = Settings(
        _env_file=None,
        BACKEND_CORS_ORIGINS="http://localhost:3000, http://127.0.0.1:3000",
    )

    assert [str(url) for url in settings.BACKEND_CORS_ORIGINS] == [
        "http://localhost:3000/",
        "http://127.0.0.1:3000/",
    ]


def test_list_origins_are_kept():
    settings = Settings(
        _env_file=None,
        BACKEND_CORS_ORIGINS=["http://localhost:3000"],
    )

    assert [str(url) for url in settings.BACKEND_CORS_ORIGINS] == [
        "http://localhost:3000/"
    ]


def test_non_string_non_list_origins_are_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, BACKEND_CORS_ORIGINS=42)
