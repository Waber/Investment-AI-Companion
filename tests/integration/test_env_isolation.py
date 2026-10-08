"""The integration import must ignore a ``.env`` in the working directory.

Marked ``integration`` so the default SQLite suite does not run
these checks. They do not open a database connection.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from app.core.config import Settings
from tests.integration.env_isolation import (
    PYTEST_SECRET_KEY,
    DotenvIsolationError,
    command_selects_integration,
    ensure_isolated_when_dotenv_present,
)

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
SCARY_URL = "postgresql://real:secret@db.example.com:5432/investment_ai"
SCARY_SECRET = "from-dotenv-should-be-ignored-not-a-real-secret"
DEFAULT_URL = Settings.model_fields["DATABASE_URL"].default
DEFAULT_SECRET = Settings.model_fields["SECRET_KEY"].default


def test_default_command_does_not_select_integration():
    assert command_selects_integration(["pytest"], environ={}) is False


def test_not_integration_does_not_select_the_marker():
    argv = ["pytest", "-m", "not integration"]
    assert command_selects_integration(argv, environ={}) is False


def test_integration_marker_is_selected():
    argv = ["pytest", "-m", "integration"]
    assert command_selects_integration(argv, environ={}) is True


def test_not_slow_still_selects_integration_tests():
    """A test marked only integration is not slow, so it would run."""
    argv = ["pytest", "-m", "not slow"]
    assert command_selects_integration(argv, environ={}) is True


def test_last_mark_expression_wins_over_pytest_addopts():
    selected = command_selects_integration(
        ["pytest", "-m", "integration"],
        environ={"PYTEST_ADDOPTS": "-m 'not integration'"},
    )
    assert selected is True

    deselected = command_selects_integration(
        ["pytest", "-m", "not integration"],
        environ={"PYTEST_ADDOPTS": "-m integration"},
    )
    assert deselected is False


def test_clustered_short_option_selects_integration():
    """pytest reads ``-qm integration`` as quiet plus ``-m integration``."""
    argv = ["pytest", "-qm", "integration"]
    assert command_selects_integration(argv, environ={}) is True


def test_empty_mark_expression_selects_every_test():
    """``-m ''`` replaces addopts and disables marker filtering."""
    argv = ["pytest", "-m", ""]
    assert command_selects_integration(argv, environ={}) is True


def test_dotenv_without_isolation_is_refused():
    with pytest.raises(DotenvIsolationError):
        ensure_isolated_when_dotenv_present(
            selected=True, isolated=False, dotenv_exists=True
        )
    ensure_isolated_when_dotenv_present(
        selected=True, isolated=True, dotenv_exists=True
    )
    ensure_isolated_when_dotenv_present(
        selected=False, isolated=False, dotenv_exists=True
    )


def test_pytest_addopts_is_used_when_the_command_has_no_mark_expression():
    selected = command_selects_integration(
        ["pytest", "-q"],
        environ={"PYTEST_ADDOPTS": "-m integration"},
    )
    assert selected is True
    deselected = command_selects_integration(
        ["pytest"],
        environ={"PYTEST_ADDOPTS": '-m "not integration"'},
    )
    assert deselected is False


def _python(script: str, cwd: Path) -> str:
    """Run ``script`` in a fresh interpreter so Settings is built there."""
    env = os.environ.copy()
    # A shell DATABASE_URL would hide the .env file. The proof needs
    # the file to be the only source of that variable.
    env.pop("DATABASE_URL", None)
    env.pop("SECRET_KEY", None)
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def test_stray_dotenv_is_loaded_without_the_helper(tmp_path):
    """A plain Settings() in that directory reads the scary file."""
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        f"DATABASE_URL={SCARY_URL}\nSECRET_KEY={SCARY_SECRET}\n",
        encoding="utf-8",
    )
    script = textwrap.dedent("""
        from app.core.config import settings
        print(settings.DATABASE_URL)
        print(settings.SECRET_KEY)
        """)
    output = _python(script, tmp_path)
    assert SCARY_URL in output
    assert SCARY_SECRET in output


def test_stray_dotenv_database_url_is_ignored(tmp_path):
    """The root conftest path leaves the scary DATABASE_URL unread.

    The subprocess starts in the directory that holds ``.env``, then
    loads the repository conftest the way pytest does, with ``-m
    integration`` on ``sys.argv``. The printed settings are the code
    defaults.
    """
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        f"DATABASE_URL={SCARY_URL}\nSECRET_KEY={SCARY_SECRET}\n",
        encoding="utf-8",
    )
    script = textwrap.dedent(f"""
        import os
        import sys

        os.chdir({str(tmp_path)!r})
        sys.argv = ["pytest", "-m", "integration"]
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "conftest", {str(REPO_ROOT / "conftest.py")!r}
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        from app.core.config import settings
        print(settings.DATABASE_URL)
        print(settings.SECRET_KEY)
        """)
    output = _python(script, tmp_path)
    assert SCARY_URL not in output
    assert SCARY_SECRET not in output
    assert DEFAULT_URL in output
    assert PYTEST_SECRET_KEY in output
    # An empty code default is a substring of every string, so it
    # cannot prove which secret was loaded. The harness key above
    # is that proof. A non-empty default must still be absent.
    if isinstance(DEFAULT_SECRET, str) and DEFAULT_SECRET:
        assert DEFAULT_SECRET not in output


def test_pytest_main_ignores_a_stray_dotenv():
    """``pytest.main`` and ``-qm`` do not read a repository ``.env``.

    Those forms do not put ``-m integration`` on ``sys.argv`` as two
    tokens. The root conftest reads the marker expression pytest
    already parsed and imports Settings from an empty directory.
    """
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        pytest.skip("repository already has a .env file")
    env_path.write_text(
        f"DATABASE_URL={SCARY_URL}\nSECRET_KEY={SCARY_SECRET}\n",
        encoding="utf-8",
    )
    script = textwrap.dedent(f"""
        import os
        import pytest

        os.chdir({str(REPO_ROOT)!r})
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("SECRET_KEY", None)
        pytest.main([
            "-qm", "integration",
            "--collect-only", "-q", "-p", "no:cacheprovider",
            "tests/integration/test_env_isolation.py::"
            "test_default_command_does_not_select_integration",
        ])
        from app.core.config import settings
        print(settings.DATABASE_URL)
        print(settings.SECRET_KEY)
        """)
    try:
        output = _python(script, REPO_ROOT)
    finally:
        env_path.unlink(missing_ok=True)
    assert SCARY_URL not in output
    assert SCARY_SECRET not in output
    assert DEFAULT_URL in output
    assert PYTEST_SECRET_KEY in output
