"""Safety checks for the PostgreSQL DSN. They do not open a connection.

Marked ``integration`` so ``python -m pytest`` deselects them with the
rest of the opt-in suite. ``-m integration`` runs them even when no
database is configured.
"""

import pytest

from app.core.config import Settings, settings
from tests.integration.postgres_dsn import (
    DATABASE_MESSAGE,
    REFUSE_MESSAGE,
    REQUIRE_MESSAGE,
    SCHEME_MESSAGE,
    SKIP_MESSAGE,
    decide_test_dsn,
)

pytestmark = pytest.mark.integration

# The code default in app/core/config.py. Tests also read the live
# Settings field so a future edit of that default stays covered.
DEFAULT_DATABASE_URL = "postgresql://przemkowy@localhost:5432/investment_ai"

SEPARATE_DATABASE_URL = (
    "postgresql://postgres:postgres@127.0.0.1:5432/investment_test"
)


def test_code_default_matches_the_settings_field():
    """The copied default string stays equal to the class default."""
    assert Settings.model_fields["DATABASE_URL"].default == (
        DEFAULT_DATABASE_URL
    )


@pytest.mark.parametrize("raw", [None, "", "   ", "\n"])
def test_missing_dsn_skips_unless_the_run_requires_postgres(raw):
    skipped = decide_test_dsn(raw, [DEFAULT_DATABASE_URL], require=False)
    assert skipped.action == "skip"
    assert skipped.message == SKIP_MESSAGE
    assert skipped.dsn == ""

    required = decide_test_dsn(raw, [DEFAULT_DATABASE_URL], require=True)
    assert required.action == "fail"
    assert required.message == REQUIRE_MESSAGE


@pytest.mark.parametrize(
    "url",
    [
        DEFAULT_DATABASE_URL,
        "postgresql://przemkowy@localhost/investment_ai",
        "postgresql+psycopg2://przemkowy:secret@127.0.0.1:5432/investment_ai",
        "postgresql://other:secret@localhost:5432/Investment_AI",
        "postgresql:///investment_ai",
        "postgresql://przemkowy@[::1]:5432/investment_ai",
    ],
)
def test_application_database_is_refused(url):
    decision = decide_test_dsn(url, [DEFAULT_DATABASE_URL], require=False)
    assert decision.action == "fail"
    assert decision.message == REFUSE_MESSAGE
    assert decision.dsn == ""
    assert "secret" not in decision.message


def test_live_application_database_url_is_refused():
    """Whatever this process loaded for the app is not a test database."""
    application_urls = (
        Settings.model_fields["DATABASE_URL"].default,
        settings.DATABASE_URL,
    )
    for url in application_urls:
        decision = decide_test_dsn(url, application_urls, require=False)
        assert decision.action == "fail"
        assert decision.message == REFUSE_MESSAGE


def test_a_second_configured_url_is_refused_too():
    custom = "postgresql://postgres@127.0.0.1:5432/custom_app"
    decision = decide_test_dsn(
        custom, [DEFAULT_DATABASE_URL, custom], require=False
    )
    assert decision.action == "fail"


@pytest.mark.parametrize(
    "url",
    [
        SEPARATE_DATABASE_URL,
        "postgresql://przemkowy@localhost:5432/investment_ai_test",
        "postgresql://przemkowy@localhost:5433/investment_ai",
        "postgresql://przemkowy@db.example.com:5432/investment_ai",
        "postgresql:///investment_test",
    ],
)
def test_separate_database_is_accepted(url):
    decision = decide_test_dsn(url, [DEFAULT_DATABASE_URL], require=True)
    assert decision.action == "use"
    assert decision.dsn == url
    assert decision.message


def test_surrounding_space_is_stripped():
    decision = decide_test_dsn(
        f"  {SEPARATE_DATABASE_URL}\n",
        [DEFAULT_DATABASE_URL],
        require=False,
    )
    assert decision.action == "use"
    assert decision.dsn == SEPARATE_DATABASE_URL


def test_empty_application_urls_are_ignored():
    decision = decide_test_dsn(
        SEPARATE_DATABASE_URL, ["", None, "  "], require=False
    )
    assert decision.action == "use"


def test_non_postgresql_url_is_refused():
    decision = decide_test_dsn(
        "sqlite:///:memory:", [DEFAULT_DATABASE_URL], require=False
    )
    assert decision.action == "fail"
    assert decision.message == SCHEME_MESSAGE


def test_url_without_a_database_name_is_refused():
    decision = decide_test_dsn(
        "postgresql://postgres@127.0.0.1:5432",
        [DEFAULT_DATABASE_URL],
        require=False,
    )
    assert decision.action == "fail"
    assert decision.message == DATABASE_MESSAGE


def test_malformed_url_is_refused_without_echoing_it():
    raw = "postgresql://user@host:nope/dbname"
    decision = decide_test_dsn(raw, [DEFAULT_DATABASE_URL], require=False)
    assert decision.action == "fail"
    assert decision.message.endswith("(ValueError).")
    assert raw not in decision.message
