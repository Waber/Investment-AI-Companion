"""Safety checks for the PostgreSQL DSN. They do not open a connection.

Marked ``integration`` so ``python -m pytest`` deselects them with the
rest of the opt-in suite. ``-m integration`` runs them even when no
database is configured.
"""

import pytest

from app.core.config import Settings, settings
from tests.integration.postgres_dsn import (
    DATABASE_MESSAGE,
    HOST_MESSAGE,
    NAME_MESSAGE,
    REFUSE_MESSAGE,
    REQUIRE_MESSAGE,
    SCHEME_MESSAGE,
    SKIP_MESSAGE,
    database_identity,
    database_name_is_allowed,
    decide_test_dsn,
)

pytestmark = pytest.mark.integration

# The declared default in app/core/config.py. Read from the field
# so this file does not copy a role name. Tests that refuse this
# URL keep working when that default changes.
DEFAULT_DATABASE_URL = Settings.model_fields["DATABASE_URL"].default

SEPARATE_DATABASE_URL = (
    "postgresql://postgres:postgres@127.0.0.1:5432/investment_test"
)

# The CI service container. The database name is already allowed, so
# the job does not set TEST_POSTGRES_ALLOW_REMOTE.
CI_DATABASE_URL = SEPARATE_DATABASE_URL


def test_code_default_database_name_is_investment_ai():
    """The application default is the database the harness must refuse."""
    identity = database_identity(DEFAULT_DATABASE_URL)
    assert identity.database == "investment_ai"
    assert identity.driver == "postgresql"
    assert identity.host == "loopback"


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
    "name",
    [
        "test",
        "investment_test",
        "test_db",
        "foo_test_bar",
        "investment_ai_test",
        "Test",
    ],
)
def test_database_name_with_test_as_its_own_word_is_allowed(name):
    assert database_name_is_allowed(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "testing",
        "testdb",
        "contest",
        "latest",
        "mytest",
        "investment_ai",
        "testfoo",
        "",
    ],
)
def test_database_name_without_test_as_its_own_word_is_refused(name):
    assert database_name_is_allowed(name) is False


@pytest.mark.parametrize(
    "url",
    [
        DEFAULT_DATABASE_URL,
        "postgresql://user@localhost/investment_ai",
        "postgresql+psycopg2://user:secret@127.0.0.1:5432/investment_ai",
        "postgresql://other:secret@localhost:5432/Investment_AI",
        "postgresql:///investment_ai",
        "postgresql://user@[::1]:5432/investment_ai",
        "postgresql://user@localhost:5433/investment_ai",
        "postgresql://user@db.example.com:5432/investment_ai",
    ],
)
def test_name_without_test_as_its_own_word_is_refused(url):
    """The name check runs before the host check and before the app URL."""
    decision = decide_test_dsn(
        url,
        [DEFAULT_DATABASE_URL],
        require=False,
        allow_remote=True,
    )
    assert decision.action == "fail"
    assert decision.message == NAME_MESSAGE
    assert decision.dsn == ""
    assert "secret" not in decision.message
    assert url not in decision.message


def test_live_application_database_url_is_refused():
    """Whatever this process loaded for the app is not a test target."""
    application_urls = (
        Settings.model_fields["DATABASE_URL"].default,
        settings.DATABASE_URL,
    )
    for url in application_urls:
        decision = decide_test_dsn(url, application_urls, require=False)
        assert decision.action == "fail"
        assert decision.dsn == ""
        name = database_identity(url).database
        if database_name_is_allowed(name):
            assert decision.message == REFUSE_MESSAGE
        else:
            assert decision.message == NAME_MESSAGE


def test_application_database_is_refused_even_when_its_name_is_allowed():
    """A test-looking name that is DATABASE_URL is still the app database."""
    custom = "postgresql://postgres@127.0.0.1:5432/custom_app_test"
    decision = decide_test_dsn(
        custom, [DEFAULT_DATABASE_URL, custom], require=False
    )
    assert decision.action == "fail"
    assert decision.message == REFUSE_MESSAGE
    assert decision.dsn == ""


def test_ci_service_url_is_accepted():
    decision = decide_test_dsn(
        CI_DATABASE_URL, [DEFAULT_DATABASE_URL], require=True
    )
    assert decision.action == "use"
    assert decision.dsn == CI_DATABASE_URL


@pytest.mark.parametrize(
    "url",
    [
        SEPARATE_DATABASE_URL,
        "postgresql://user@localhost:5432/investment_ai_test",
        "postgresql://user@localhost/test",
        "postgresql://user@[::1]:5432/test_db",
        "postgresql:///investment_test",
        "postgresql://user@localhost:5432/Foo_Test_Bar",
    ],
)
def test_local_test_database_is_accepted(url):
    decision = decide_test_dsn(url, [DEFAULT_DATABASE_URL], require=True)
    assert decision.action == "use"
    assert decision.dsn == url


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://user@db.example.com:5432/investment_test",
        "postgresql://user@10.0.0.5:5432/test",
    ],
)
def test_remote_host_is_refused_unless_the_override_is_set(url):
    refused = decide_test_dsn(url, [DEFAULT_DATABASE_URL], require=False)
    assert refused.action == "fail"
    assert refused.message == HOST_MESSAGE
    assert url not in refused.message

    allowed = decide_test_dsn(
        url, [DEFAULT_DATABASE_URL], require=False, allow_remote=True
    )
    assert allowed.action == "use"
    assert allowed.dsn == url


def test_remote_override_does_not_bypass_the_name_rule():
    url = "postgresql://user@db.example.com:5432/investment_ai"
    decision = decide_test_dsn(
        url, [DEFAULT_DATABASE_URL], require=False, allow_remote=True
    )
    assert decision.action == "fail"
    assert decision.message == NAME_MESSAGE


def test_remote_override_does_not_bypass_the_application_database():
    url = "postgresql://user@db.example.com:5432/investment_test"
    decision = decide_test_dsn(
        url, [DEFAULT_DATABASE_URL, url], require=False, allow_remote=True
    )
    assert decision.action == "fail"
    assert decision.message == REFUSE_MESSAGE


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
