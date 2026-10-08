"""The PostgreSQL job fails when a test skips.

These tests call the hook helpers directly. They do not open a
database. They are marked ``integration`` so the default SQLite
command deselects them with the rest of this package.
"""

from types import SimpleNamespace

import pytest

from tests.integration import conftest as integration_conftest

pytestmark = pytest.mark.integration


class _Reporter:
    def __init__(self):
        self.lines = []

    def write_sep(self, sep, title):
        self.lines.append((sep, title))


def _session(exitstatus, reporter):
    pluginmanager = SimpleNamespace(get_plugin=lambda name: reporter)
    config = SimpleNamespace(pluginmanager=pluginmanager)
    return SimpleNamespace(exitstatus=exitstatus, config=config)


def test_a_skip_fails_the_session_when_postgres_is_required(monkeypatch):
    monkeypatch.setenv("REQUIRE_POSTGRES", "1")
    reporter = _Reporter()
    session = _session(0, reporter)
    integration_conftest.refuse_skips_when_postgres_is_required(
        session, ["tests/integration/test_postgres.py::test_example"]
    )
    assert session.exitstatus == pytest.ExitCode.TESTS_FAILED
    assert reporter.lines
    assert "REQUIRE_POSTGRES=1" in reporter.lines[0][1]


def test_a_clean_run_stays_green_when_postgres_is_required(monkeypatch):
    monkeypatch.setenv("REQUIRE_POSTGRES", "1")
    session = _session(0, _Reporter())
    integration_conftest.refuse_skips_when_postgres_is_required(session, [])
    assert session.exitstatus == 0


def test_an_existing_failure_is_left_unchanged(monkeypatch):
    monkeypatch.setenv("REQUIRE_POSTGRES", "1")
    session = _session(pytest.ExitCode.TESTS_FAILED, _Reporter())
    integration_conftest.refuse_skips_when_postgres_is_required(
        session, ["some::test"]
    )
    assert session.exitstatus == pytest.ExitCode.TESTS_FAILED


def test_skips_are_allowed_when_postgres_is_not_required(monkeypatch):
    monkeypatch.delenv("REQUIRE_POSTGRES", raising=False)
    session = _session(0, _Reporter())
    integration_conftest.refuse_skips_when_postgres_is_required(
        session, ["some::test"]
    )
    assert session.exitstatus == 0


def test_runtest_logreport_records_only_skips():
    before = len(integration_conftest._skipped_nodeids)
    try:
        integration_conftest.pytest_runtest_logreport(
            SimpleNamespace(skipped=True, nodeid="recorded::skip")
        )
        integration_conftest.pytest_runtest_logreport(
            SimpleNamespace(skipped=False, nodeid="recorded::pass")
        )
        integration_conftest.pytest_runtest_logreport(
            SimpleNamespace(
                skipped=True, nodeid="recorded::xfail", wasxfail="known"
            )
        )
        added = integration_conftest._skipped_nodeids[before:]
        assert added == ["recorded::skip"]
    finally:
        del integration_conftest._skipped_nodeids[before:]
