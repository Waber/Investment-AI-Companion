"""The PostgreSQL job fails when a test skips.

These tests call the hook helpers directly. They do not open a
database. They are marked ``integration`` so the default SQLite
command deselects them with the rest of this package.
"""

import os
import subprocess
import sys
from pathlib import Path
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
    banner = reporter.lines[0][1]
    assert "REQUIRE_POSTGRES=1" in banner
    assert "test_example" in banner


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


def test_collectreport_records_a_module_level_skip():
    """pytest.skip(allow_module_level=True) is a collection report."""
    before = len(integration_conftest._skipped_nodeids)
    try:
        integration_conftest.pytest_collectreport(
            SimpleNamespace(
                skipped=True, nodeid="tests/integration/test_mod.py"
            )
        )
        integration_conftest.pytest_collectreport(
            SimpleNamespace(
                skipped=False, nodeid="tests/integration/test_ok.py"
            )
        )
        integration_conftest.pytest_collectreport(
            SimpleNamespace(
                skipped=True,
                nodeid="tests/integration/test_mod.py",
                wasxfail=False,
            )
        )
        added = integration_conftest._skipped_nodeids[before:]
        assert added == ["tests/integration/test_mod.py"]
    finally:
        del integration_conftest._skipped_nodeids[before:]


def test_banner_names_the_first_three_skips():
    banner = integration_conftest._skip_banner(
        ["a.py", "b.py", "c.py", "d.py"]
    )
    assert "4 skipped: a.py, b.py, c.py, and 1 more" in banner


def test_module_level_skip_fails_when_postgres_is_required(tmp_path):
    """The real hooks see a module skip and fail the child process."""
    root = Path(__file__).resolve().parents[2]
    (tmp_path / "conftest.py").write_text(
        "from tests.integration.conftest import (\n"
        "    pytest_collectreport,\n"
        "    pytest_runtest_logreport,\n"
        "    pytest_sessionfinish,\n"
        ")\n",
        encoding="utf-8",
    )
    (tmp_path / "test_mod.py").write_text(
        "import pytest\n"
        "pytest.skip('module off', allow_module_level=True)\n"
        "\n"
        "def test_hidden():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    (tmp_path / "test_ok.py").write_text(
        "def test_visible():\n    assert True\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["REQUIRE_POSTGRES"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(root), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            str(tmp_path),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "1 skipped: test_mod.py" in completed.stdout
    assert "1 passed" in completed.stdout
