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

# Longer than 32 characters and not one of the placeholders the
# secure-config work rejects. setdefault keeps a secret the shell
# already exported.
PYTEST_SECRET_KEY = "test-secret-key-for-pytest-harness"

_isolated = False


class DotenvIsolationError(RuntimeError):
    """Integration was selected, ``.env`` exists, and isolation did not run."""


def isolation_completed() -> bool:
    """Return whether the application was imported from an empty directory."""
    return _isolated


def expression_selects_integration(expression: str) -> bool:
    """Return whether ``expression`` would run a test marked only integration.

    An empty expression is pytest's "no marker filter": ``-m ''``
    replaces addopts and collects every test, including these.
    Any other expression uses pytest's grammar. A test marked only
    ``integration`` is the subject. Other marker names count as
    absent, so ``not slow`` still selects these tests.
    """
    if expression == "":
        return True
    try:
        compiled = Expression.compile(expression)
    except SyntaxError:
        return False
    return compiled.evaluate(lambda name, **kwargs: name == "integration")


def ensure_isolated_when_dotenv_present(
    *, selected: bool, isolated: bool, dotenv_exists: bool
) -> None:
    """Fail when integration would run against a developer's ``.env``.

    A command that selects the marker but did not import Settings
    from an empty directory must stop if ``.env`` is in the working
    directory. Otherwise ``DATABASE_URL`` in that file becomes the
    application database after the import.
    """
    if selected and dotenv_exists and not isolated:
        raise DotenvIsolationError(
            "Integration tests are selected and a .env file exists, "
            "but Settings was not imported in isolation. Refusing to "
            "continue because that file would supply DATABASE_URL."
        )


def command_selects_integration(
    argv: Sequence[str], environ: Mapping[str, str] | None = None
) -> bool:
    """Return whether this command would run ``integration`` tests.

    When ``argv`` is this process's ``sys.argv``, the check reads the
    marker expression pytest already parsed, including ``-qm
    integration`` and ``pytest.main``. A caller-supplied argument
    list is parsed here so tests can cover one command without
    starting pytest.

    pytest replaces the ``addopts`` marker expression with ``-m`` on
    the command line. ``PYTEST_ADDOPTS`` is used only when the
    command itself has no ``-m``. When neither is set, this
    repository's ``addopts`` is ``-m "not integration"``, so the
    answer is false. The last ``-m`` wins.
    """
    if _is_process_argv(argv):
        parsed = _markexpr_from_initial_conftests()
        if parsed is not None:
            return expression_selects_integration(parsed)
    env = os.environ if environ is None else environ
    expression = _last_markexpr(argv)
    if expression is None:
        expression = _last_markexpr(shlex.split(env.get("PYTEST_ADDOPTS", "")))
    if expression is None:
        return False
    return expression_selects_integration(expression)


def _is_process_argv(argv: Sequence[str]) -> bool:
    return argv is sys.argv or list(argv) == list(sys.argv)


def _markexpr_from_initial_conftests() -> str | None:
    """The marker expression pytest parsed before loading this conftest.

    ``pytest.main`` does not put its arguments on ``sys.argv``. They
    are on ``early_config`` while the root conftest is imported.
    """
    frame = sys._getframe()
    while frame is not None:
        early = frame.f_locals.get("early_config")
        namespace = getattr(early, "known_args_namespace", None)
        markexpr = getattr(namespace, "markexpr", None)
        if isinstance(markexpr, str):
            return markexpr
        frame = frame.f_back
    return None


def _last_markexpr(args: Sequence[str]) -> str | None:
    """Return the last ``-m`` value, or ``None`` when ``-m`` is absent.

    ``-m integration``, ``-mintegration``, ``-m=integration``, and
    ``-qm integration`` are all accepted. ``--maxfail`` is not an
    ``-m`` expression. An explicit empty value is ``""``, which
    pytest treats as no marker filter.
    """
    found: str | None = None
    saw = False
    index = 0
    tokens = list(args)
    while index < len(tokens):
        arg = tokens[index]
        if arg == "--":
            break
        kind, attached = _mark_option(arg)
        if kind == "next":
            saw = True
            if index + 1 < len(tokens):
                found = tokens[index + 1]
                index += 2
                continue
            found = ""
            index += 1
            continue
        if kind == "attached":
            saw = True
            found = attached
        index += 1
    if not saw:
        return None
    return "" if found is None else found


def _mark_option(arg: str) -> tuple[str, str]:
    """Classify one argv token as ``next``, ``attached``, or ``none``.

    ``next`` means the expression is the following token (``-m`` and
    ``-qm``). ``attached`` means it is inside this token
    (``-mintegration``, ``-m=integration``, ``-mq``).
    """
    if not arg.startswith("-") or arg.startswith("--"):
        return "none", ""
    body = arg[1:]
    if body == "m":
        return "next", ""
    marker = body.find("m")
    if marker < 0:
        return "none", ""
    prefix = body[:marker]
    if prefix and not prefix.isalpha():
        return "none", ""
    start = marker + 1
    rest = body[start:]
    if rest == "":
        if prefix:
            return "next", ""
        return "none", ""
    if rest.startswith("="):
        return "attached", rest[1:]
    return "attached", rest


def prepare_integration_environment() -> None:
    """Set a test secret, then import Settings away from ``.env``.

    ``setdefault`` keeps a ``SECRET_KEY`` the shell already
    exported. The value is long enough for a later rule that
    rejects short secrets, and it is not a known placeholder.
    """
    os.environ.setdefault("SECRET_KEY", PYTEST_SECRET_KEY)
    import_application_without_dotenv()


def import_application_without_dotenv() -> None:
    """Import settings from a directory that contains no ``.env`` file.

    If ``app.core.config`` is already imported, ``Settings`` was
    already built and this function does not rebuild it. Call it
    before any other test module imports the application.

    The process environment is left as the shell set it, apart from
    the secret ``prepare_integration_environment`` may have filled
    in. Only the working directory changes, and only for the
    duration of the import.
    """
    global _isolated
    if "app.core.config" in sys.modules:
        return
    original = os.getcwd()
    temporary = tempfile.mkdtemp(prefix="iac-integration-import-")
    try:
        os.chdir(temporary)
        import app.core.config  # noqa: F401
        import app.core.database  # noqa: F401
        import main  # noqa: F401

        _isolated = True
    finally:
        os.chdir(original)
        shutil.rmtree(temporary, ignore_errors=True)
