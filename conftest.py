"""Load the application without a developer's ``.env`` for integration.

pytest imports this file before ``tests/conftest.py``. That second
file imports the application at module level, and ``Settings`` reads
``.env`` from the process working directory. When the command
selects the ``integration`` marker, the import below happens first,
from an empty temporary directory, so the file is never applied.
A test ``SECRET_KEY`` is set first so a later required-secret rule
does not crash that import.

The default SQLite command does not select that marker. This file
then does not import the application, and the SQLite suite is
unchanged. ``tests/conftest.py`` is not modified.
"""

import sys
from pathlib import Path

import pytest


def _isolate_when_integration_is_selected() -> None:
    root = str(Path(__file__).resolve().parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from tests.integration.env_isolation import (
        command_selects_integration,
        prepare_integration_environment,
    )

    if command_selects_integration(sys.argv):
        prepare_integration_environment()


def pytest_configure(config: pytest.Config) -> None:
    """Isolate late, or stop, if the early argv check missed the command.

    ``-qm integration``, ``-m ''``, and ``pytest.main`` are easy to
    miss from ``sys.argv`` alone. By configuration time pytest has
    the real marker expression. If Settings is already loaded from a
    ``.env`` file, continuing would hide that database URL.
    """
    from tests.integration.env_isolation import (
        DotenvIsolationError,
        ensure_isolated_when_dotenv_present,
        expression_selects_integration,
        isolation_completed,
        prepare_integration_environment,
    )

    selected = expression_selects_integration(config.option.markexpr)
    if not selected or isolation_completed():
        return
    dotenv_exists = (Path.cwd() / ".env").is_file()
    if "app.core.config" in sys.modules:
        try:
            ensure_isolated_when_dotenv_present(
                selected=True,
                isolated=False,
                dotenv_exists=dotenv_exists,
            )
        except DotenvIsolationError as exc:
            raise pytest.UsageError(str(exc)) from exc
        return
    prepare_integration_environment()


_isolate_when_integration_is_selected()
