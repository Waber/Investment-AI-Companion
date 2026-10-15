"""Load the application without a developer's ``.env`` for integration.

pytest imports this file before ``tests/conftest.py``. That second
file imports the application at module level, and ``Settings`` reads
``.env`` from the process working directory. When the command
selects the ``integration`` marker, the import below happens first,
from an empty temporary directory, so the file is never applied.
A test ``SECRET_KEY`` is set first so a later required-secret rule
does not crash that import.

The default SQLite command does not select that marker, so that
branch does not run. ``DATA_COLLECTOR`` and ``YF_DISABLE_CURL_CFFI``
are set below in every mode. ``tests/conftest.py`` is not modified
by the integration branch.
"""

import os
import sys
from pathlib import Path

import pytest

# Set before anything can import the app or yfinance. This file is the
# one place that does it, because it runs first in every selection mode
# (the integration branch below imports ``Settings`` before
# ``tests/conftest.py`` is loaded). Assignment, not setdefault: a
# developer shell must not turn the suite into an online run.
# - DATA_COLLECTOR=fake: fetch-company uses the offline collector.
# - YF_DISABLE_CURL_CFFI=1: yfinance falls back to ``requests``, which
#   opens Python sockets that the network guard sees. Its default,
#   curl_cffi (libcurl, written in C), would bypass the guard.
os.environ["DATA_COLLECTOR"] = "fake"
os.environ["YF_DISABLE_CURL_CFFI"] = "1"


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


@pytest.fixture(autouse=True)
def reset_cached_live_collector():
    """Drop the process-wide Yahoo wrapper around every test.

    ``get_collector()`` keeps one wrapped collector for the process, the
    same idea as a static field on a Java singleton. That object, its
    cache and its rate-limit window would otherwise survive into the
    next test. ``test_yahoo_near_empty_info_is_a_404_not_a_502`` used to
    see the wrapper left by
    ``test_yahoo_wrapper_reuses_the_cache_across_requests``.

    The import stays inside the fixture. This file must not import the
    application at module level, because the integration branch isolates
    ``.env`` before ``Settings`` is first constructed.
    """
    from app.api.data_collection import reset_cached_collector

    reset_cached_collector()
    yield
    reset_cached_collector()
