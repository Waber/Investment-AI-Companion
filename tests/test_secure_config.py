"""Secure defaults (#45) and the neutral database URL (#47).

DEBUG is off, SECRET_KEY is required, the process binds to loopback,
and a comma-separated CORS value parses. Tracked files do not contain
a local username or an absolute home or temporary path.
"""

import runpy
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

import main
from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[1]
TEST_SECRET = "unit-test-secret-key"


def _parsed_origins(settings):
    """List of origins, whether the code still exposes the raw field."""
    parsed = getattr(settings, "cors_origins", None)
    if parsed is not None:
        return parsed
    return settings.BACKEND_CORS_ORIGINS


def test_debug_defaults_to_false(monkeypatch):
    monkeypatch.delenv("DEBUG", raising=False)
    settings = Settings(_env_file=None, SECRET_KEY=TEST_SECRET)

    assert settings.DEBUG is False


def test_secret_key_is_required(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "value",
    ["your-secret-key-here", "replace-this-in-local-env", "", "   "],
)
def test_placeholder_secret_key_is_rejected(value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, SECRET_KEY=value)


def test_real_secret_key_is_accepted():
    settings = Settings(_env_file=None, SECRET_KEY=TEST_SECRET)

    assert settings.SECRET_KEY == TEST_SECRET


def test_allowed_hosts_default_is_loopback(monkeypatch):
    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)
    settings = Settings(_env_file=None, SECRET_KEY=TEST_SECRET)

    assert settings.ALLOWED_HOSTS == ["localhost", "127.0.0.1"]


@pytest.mark.asyncio
async def test_untrusted_host_header_is_rejected(client):
    response = await client.get("/", headers={"Host": "evil.example"})

    assert response.status_code == 400
    assert "evil.example" not in response.text


@pytest.mark.asyncio
async def test_loopback_host_with_port_is_accepted(client):
    """The test client and uvicorn send Host with a port. That stays valid."""
    response = await client.get("/", headers={"Host": "127.0.0.1:8000"})

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_test_config_is_hidden_when_debug_is_left_unset(
    client, monkeypatch
):
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.setattr(
        main,
        "settings",
        Settings(_env_file=None, SECRET_KEY=TEST_SECRET),
    )

    response = await client.get("/api/v1/test-config")

    assert response.status_code in (403, 404)


def test_main_binds_loopback(monkeypatch):
    import uvicorn

    captured = {}

    def fake_run(*args, **kwargs):
        captured["kwargs"] = kwargs

    monkeypatch.setattr(uvicorn, "run", fake_run)
    previous = sys.modules.get("__main__")
    try:
        runpy.run_path(str(ROOT / "main.py"), run_name="__main__")
    finally:
        if previous is not None:
            sys.modules["__main__"] = previous

    assert captured.get("kwargs", {}).get("host") == "127.0.0.1"


def test_comma_separated_cors_env_parses(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
    monkeypatch.setenv(
        "BACKEND_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    try:
        settings = Settings(_env_file=None)
    except Exception as exc:
        pytest.fail(
            "comma-separated BACKEND_CORS_ORIGINS raised "
            f"{type(exc).__name__}: {exc}"
        )

    assert [
        str(origin).rstrip("/") for origin in _parsed_origins(settings)
    ] == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_json_list_cors_env_parses(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
    monkeypatch.setenv(
        "BACKEND_CORS_ORIGINS",
        '["http://localhost:3000","http://127.0.0.1:3000"]',
    )

    settings = Settings(_env_file=None)

    assert [
        str(origin).rstrip("/") for origin in _parsed_origins(settings)
    ] == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_json_list_cors_string_parses():
    try:
        settings = Settings(
            _env_file=None,
            SECRET_KEY=TEST_SECRET,
            BACKEND_CORS_ORIGINS=(
                '["http://localhost:3000","http://127.0.0.1:3000"]'
            ),
        )
    except Exception as exc:
        pytest.fail(
            "JSON-list BACKEND_CORS_ORIGINS raised "
            f"{type(exc).__name__}: {exc}"
        )

    assert [
        str(origin).rstrip("/") for origin in _parsed_origins(settings)
    ] == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_invalid_cors_origin_fails_clearly():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            SECRET_KEY=TEST_SECRET,
            BACKEND_CORS_ORIGINS="http://localhost:3000,not-a-url",
        )


def test_cors_none_and_non_list_json_and_non_string_entries_fail():
    assert (
        Settings(
            _env_file=None,
            SECRET_KEY=TEST_SECRET,
            BACKEND_CORS_ORIGINS=None,
        ).cors_origins
        == []
    )
    for value in ('{"origin": "http://localhost:3000"}', "[1]"):
        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                SECRET_KEY=TEST_SECRET,
                BACKEND_CORS_ORIGINS=value,
            )


def test_broken_cors_json_fails_clearly():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            SECRET_KEY=TEST_SECRET,
            BACKEND_CORS_ORIGINS="[not-json",
        )


def test_database_url_default_is_neutral(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings(_env_file=None, SECRET_KEY=TEST_SECRET)

    assert settings.DATABASE_URL == (
        "postgresql://investment_ai@localhost:5432/investment_ai"
    )


def _personal_path_pattern() -> str:
    # Built from pieces so this file does not contain the needles.
    username = "przem" + "kowy"
    home = "/Use" + "rs/"
    temporary = "/private" + "/tmp"
    return f"{username}|{home}|{temporary}"


def test_tracked_files_have_no_personal_machine_paths():
    result = subprocess.run(
        ["git", "grep", "-n", "-E", _personal_path_pattern(), "--", "."],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.stdout == ""
