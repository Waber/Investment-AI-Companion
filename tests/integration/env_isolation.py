"""Import the application without reading a developer's ``.env`` file.

``Settings`` uses ``env_file=".env"``. Pydantic resolves that path
from the process working directory, not from the repository root.
pytest loads the repository ``conftest.py`` before
``tests/conftest.py``, and ``tests/conftest.py`` imports the
application at module level. When the command selects the
``integration`` marker, the root conftest calls
``import_application_without_dotenv`` first, from an empty
temporary directory. The later import reuses that module, so the
``.env`` next to the original directory is never applied.

A ``DATABASE_URL`` exported in the shell is still visible. That is
an explicit process environment, not a file the harness happened
to find. The default SQLite command does not select the marker, so
this function does not run and that suite is unchanged.

Importing this module does not import the application.
"""

import os
import shlex
import shutil
import sys
import tempfile
from collections.abc import Mapping, Sequence

from _pytest.mark.expression import Expression


def command_selects_integration(
    argv: Sequence[str], environ: Mapping[str, str] | None = None
) -> bool:
    """Return whether this command would run ``integration`` tests.

    pytest replaces the ``addopts`` marker expression with ``-m`` on
    the command line. ``PYTEST_ADDOPTS`` is used only when the
    command itself has no ``-m``. When neither is set, this
    repository's ``addopts`` is ``-m "not integration"``, so the
    answer is false.

    The check asks pytest's own marker grammar whether a test marked
    only ``integration`` would be selected. Other marker names count
    as absent, so ``not slow`` still selects these tests and
    ``not integration`` does not. The last ``-m`` wins.
    """
    env = os.environ if environ is None else environ
    expression = _last_markexpr(argv)
    if expression is None:
        expression = _last_markexpr(shlex.split(env.get("PYTEST_ADDOPTS", "")))
    if expression is None:
        return False
    try:
        compiled = Expression.compile(expression)
    except SyntaxError:
        return False
    return compiled.evaluate(lambda name, **kwargs: name == "integration")


def _last_markexpr(args: Sequence[str]) -> str | None:
    """Return the last ``-m`` value, or ``None`` when ``-m`` is absent.

    ``-m integration`` and ``-mintegration`` are both accepted.
    ``--maxfail`` is not an ``-m`` expression.
    """
    found = None
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "-m" and index + 1 < len(args):
            found = args[index + 1]
            index += 2
            continue
        if arg.startswith("-m") and not arg.startswith("--") and arg != "-m":
            found = arg[2:]
            index += 1
            continue
        index += 1
    return found


def import_application_without_dotenv() -> None:
    """Import settings from a directory that contains no ``.env`` file.

    If ``app.core.config`` is already imported, ``Settings`` was
    already built and this function does not rebuild it. Call it
    before any other test module imports the application.

    The process environment is left as the shell set it. Only the
    working directory changes, and only for the duration of the
    import.
    """
    if "app.core.config" in sys.modules:
        return
    original = os.getcwd()
    temporary = tempfile.mkdtemp(prefix="iac-integration-import-")
    try:
        os.chdir(temporary)
        import app.core.config  # noqa: F401
        import app.core.database  # noqa: F401
        import main  # noqa: F401
    finally:
        os.chdir(original)
        shutil.rmtree(temporary, ignore_errors=True)
