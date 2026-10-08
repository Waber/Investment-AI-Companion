"""Secure defaults (#45) and the neutral database URL (#47).

DEBUG is off, SECRET_KEY is required, the process binds to loopback,
and a comma-separated CORS value parses. Tracked files do not contain
a local username or an absolute home or temporary path.
"""

import re
import runpy
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

import main
from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[1]
TEST_SECRET = "unit-test-secret-key-0123456789abcd"


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


def test_missing_secret_key_explains_how_to_generate_one(monkeypatch):
    """A missing key must not stop at a bare 'Field required'."""
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None)

    message = str(caught.value)
    assert "token_urlsafe(32)" in message
    assert "Field required" not in message


def test_settings_errors_hide_other_secrets(monkeypatch):
    """A missing or rejected SECRET_KEY must not print the other settings.

    Pydantic's default error includes the whole input dict. That dict
    holds DATABASE_URL and API keys.
    """
    monkeypatch.delenv("SECRET_KEY", raising=False)
    marker = "S3cr3t-marker"
    database_url = f"postgresql://a:{marker}@h/d"

    with pytest.raises(ValidationError) as missing:
        Settings(
            _env_file=None,
            DATABASE_URL=database_url,
            OPENAI_API_KEY=marker,
        )

    assert marker not in str(missing.value)

    with pytest.raises(ValidationError) as invalid:
        Settings(
            _env_file=None,
            SECRET_KEY="your-secret-key-here",
            DATABASE_URL=database_url,
            OPENAI_API_KEY=marker,
        )

    assert marker not in str(invalid.value)


@pytest.mark.parametrize(
    "value",
    ["your-secret-key-here", "replace-this-in-local-env", "", "   "],
)
def test_placeholder_secret_key_is_rejected(value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, SECRET_KEY=value)


@pytest.mark.parametrize(
    "value",
    [
        "YOUR-SECRET-KEY-HERE",
        "Replace-This-In-Local-Env",
        "a" * 31,
    ],
)
def test_secret_key_case_and_short_values_are_rejected(value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, SECRET_KEY=value)


def test_secret_key_of_32_characters_is_accepted():
    value = "b" * 32
    settings = Settings(_env_file=None, SECRET_KEY=value)

    assert settings.SECRET_KEY == value


def test_real_secret_key_is_accepted():
    settings = Settings(_env_file=None, SECRET_KEY=TEST_SECRET)

    assert settings.SECRET_KEY == TEST_SECRET


def _hosts(settings):
    """Parsed host list, once the field stops being a raw JSON list."""
    parsed = getattr(settings, "allowed_hosts", None)
    if parsed is not None:
        return parsed
    return settings.ALLOWED_HOSTS


def test_allowed_hosts_default_is_loopback(monkeypatch):
    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)
    settings = Settings(_env_file=None, SECRET_KEY=TEST_SECRET)

    assert _hosts(settings) == ["localhost", "127.0.0.1"]


def test_comma_separated_allowed_hosts_env_parses(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
    monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1")
    try:
        settings = Settings(_env_file=None)
    except Exception as exc:
        pytest.fail(
            "comma-separated ALLOWED_HOSTS raised "
            f"{type(exc).__name__}: {exc}"
        )

    assert _hosts(settings) == ["localhost", "127.0.0.1"]


def test_json_list_allowed_hosts_env_parses(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
    monkeypatch.setenv("ALLOWED_HOSTS", '["localhost","127.0.0.1"]')

    settings = Settings(_env_file=None)

    assert _hosts(settings) == ["localhost", "127.0.0.1"]


@pytest.mark.parametrize(
    "value",
    [["*"], ["localhost:8000"], ["localhost", ""], ["localhost", "*"]],
)
def test_unsafe_allowed_hosts_are_rejected(value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, SECRET_KEY=TEST_SECRET, ALLOWED_HOSTS=value)


def test_star_allowed_host_from_env_is_rejected(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
    monkeypatch.setenv("ALLOWED_HOSTS", '["*"]')

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


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


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000/api",
        "http://user:secret@localhost:3000",
        "http://localhost:3000?x=1",
        "http://localhost:3000#frag",
        "http://*.example.com",
        "*",
        "ftp://localhost",
    ],
)
def test_cors_origin_must_be_a_bare_http_origin(origin):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            SECRET_KEY=TEST_SECRET,
            BACKEND_CORS_ORIGINS=origin,
        )


def test_ipv6_cors_origin_is_rejected_as_unsupported():
    """IPv6 origins are not supported. The error should say so."""
    with pytest.raises(ValidationError) as caught:
        Settings(
            _env_file=None,
            SECRET_KEY=TEST_SECRET,
            BACKEND_CORS_ORIGINS="http://[::1]:3000",
        )

    message = str(caught.value)
    assert "IPv6" in message
    assert "not supported" in message


def test_cors_userinfo_error_does_not_echo_the_password():
    """The startup error must not repeat user:password from the origin."""
    marker = "cors-password-marker"
    with pytest.raises(ValidationError) as caught:
        Settings(
            _env_file=None,
            SECRET_KEY=TEST_SECRET,
            BACKEND_CORS_ORIGINS=f"http://alice:{marker}@localhost:3000",
        )

    assert marker not in str(caught.value)


def test_cors_root_path_is_accepted_without_keeping_the_slash():
    settings = Settings(
        _env_file=None,
        SECRET_KEY=TEST_SECRET,
        BACKEND_CORS_ORIGINS="https://example.com/",
    )

    assert [str(origin).rstrip("/") for origin in settings.cors_origins] == [
        "https://example.com"
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


def test_documented_commands_expand_tmpdir_and_home():
    """A copied command must expand $TMPDIR and ~. Single quotes do not."""
    documents = [ROOT / "README.md", ROOT / "DATABASE_SETUP.md"]
    documents.extend((ROOT / "docs").rglob("*.md"))
    single_quoted = re.compile(r"'[^'\n]*'")
    frozen = []
    for path in documents:
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            for match in single_quoted.finditer(line):
                chunk = match.group(0)
                if "$TMPDIR" in chunk or "~/" in chunk:
                    frozen.append(f"{path.relative_to(ROOT)}:{lineno}:{chunk}")
    assert frozen == []


def test_operator_guides_name_the_shared_checkout():
    """Guides name one checkout and tell the reader to use their own temp dir."""
    checkout = "~/IdeaProjects/Investment-AI-Companion"
    old_checkout = "~/projects/"
    paths = (
        ROOT / "docs" / "ide-startup.md",
        ROOT / "docs" / "api-demo.md",
        ROOT / "docs" / "demo-data.md",
    )
    for path in paths:
        text = path.read_text()
        assert checkout in text, path.name
        assert old_checkout not in text, path.name
    demo = (ROOT / "docs" / "api-demo.md").read_text()
    assert "Substitute your own `$TMPDIR` path" in demo


def test_ide_startup_mentions_secret_key_length():
    """A short SECRET_KEY is a settings error, not a database error."""
    guide = (ROOT / "docs" / "ide-startup.md").read_text().splitlines()
    settings = [
        line for line in guide if line.startswith("- Settings errors:")
    ]
    assert len(settings) == 1
    assert "SECRET_KEY" in settings[0]
    assert "at least 32 characters" in settings[0]


def test_docs_say_an_unknown_host_is_rejected():
    """Operators need to see that ALLOWED_HOSTS is actually enforced."""
    needle = "Invalid host header"
    readme = (ROOT / "README.md").read_text()
    example = (ROOT / ".env.example").read_text()
    assert "ALLOWED_HOSTS" in readme and needle in readme
    assert "ALLOWED_HOSTS" in example and needle in example


def test_tracked_files_have_no_personal_machine_paths():
    result = subprocess.run(
        ["git", "grep", "-n", "-E", _personal_path_pattern(), "--", "."],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.stdout == ""
