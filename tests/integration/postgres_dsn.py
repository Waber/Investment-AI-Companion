"""Decide whether a PostgreSQL integration run may open a database.

The harness drops tables and truncates them. A denylist of the
application URL is not enough: any other name would be destroyed.
The database name must contain ``test`` as its own word, and the
host must be this machine, unless ``TEST_POSTGRES_ALLOW_REMOTE=1``.

Importing this module does not connect to anything.
"""

import os
import re
from collections.abc import Iterable, Mapping
from urllib.parse import parse_qsl, urlsplit

from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import ArgumentError

# ``investment_test`` matches. ``testing``, ``testdb``, and ``contest``
# do not: ``test`` has to be a whole word between underscores.
_TEST_DATABASE_NAME = re.compile(r"(^|_)test($|_)")

# Hosts that mean "this machine". A Unix-socket URL has no host, and
# that socket is the local server, same as localhost.
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_LOCAL_HOSTS = frozenset({"loopback", "local-socket"})

SKIP_MESSAGE = (
    "PostgreSQL integration tests need TEST_POSTGRES_DSN set to a "
    "local database whose name contains test as its own word, "
    "for example investment_test. The host must be localhost, "
    "127.0.0.1, ::1, or a Unix socket "
    "(TEST_POSTGRES_ALLOW_REMOTE=1 allows another host). "
    "Example: postgresql://postgres:postgres@127.0.0.1:5432/"
    "investment_test. "
    "python -m pytest leaves these tests deselected and does not "
    "need PostgreSQL."
)

REQUIRE_MESSAGE = (
    "TEST_POSTGRES_DSN is not set. REQUIRE_POSTGRES=1 means this run "
    "must execute the integration tests against PostgreSQL, not skip "
    "them."
)

REFUSE_MESSAGE = (
    "Refusing to run integration tests: TEST_POSTGRES_DSN points at "
    "the application's database. Use a separate database name, for "
    "example investment_test, and do not reuse DATABASE_URL."
)

SCHEME_MESSAGE = (
    "TEST_POSTGRES_DSN must be a PostgreSQL URL starting with "
    "postgresql://."
)

DATABASE_MESSAGE = (
    "TEST_POSTGRES_DSN must include a database name. "
    "An omitted name would use the server's default database."
)

NAME_MESSAGE = (
    "Refusing to run integration tests: the database name must "
    'contain "test" as its own word, separated by underscores '
    "(for example investment_test). Names such as investment_ai, "
    "testing, and testdb are refused. The harness drops and "
    "recreates tables in that database."
)

HOST_MESSAGE = (
    "Refusing to run integration tests: TEST_POSTGRES_DSN must "
    "use localhost, 127.0.0.1, ::1, or a Unix socket. Set "
    "TEST_POSTGRES_ALLOW_REMOTE=1 to allow another host. The "
    "harness drops and recreates tables in that database."
)

# libpq lets these query keys replace the database or the server
# after SQLAlchemy has read the path and the netloc.
_FORBIDDEN_QUERY_KEYS = frozenset(
    {"dbname", "database", "hostaddr", "service"}
)

QUERY_MESSAGE = (
    "Refusing to run integration tests: TEST_POSTGRES_DSN must "
    "not set dbname, database, hostaddr, or service in the query "
    "string. Those parameters override the URL and can select "
    "another database or server. The harness drops and recreates "
    "tables."
)

QUERY_HOST_MESSAGE = (
    "Refusing to run integration tests: every host query value "
    "must be localhost, 127.0.0.1, ::1, or an absolute socket "
    "path. The harness drops and recreates tables in that "
    "database."
)

ENV_HOST_MESSAGE = (
    "Refusing to run integration tests: TEST_POSTGRES_DSN has no "
    "host, so libpq would use PGHOST, PGHOSTADDR, or PGSERVICE. "
    "PGHOST must be localhost, 127.0.0.1, ::1, or an absolute "
    "socket path. PGHOSTADDR must be a loopback address. "
    "PGSERVICE is refused because a service file can name "
    "another server. The harness drops and recreates tables."
)


class DsnDecision:
    """What the harness should do with ``TEST_POSTGRES_DSN``.

    ``action`` is ``"use"``, ``"skip"``, or ``"fail"``. ``dsn`` is set
    only for ``"use"``, and it is the stripped URL.
    """

    def __init__(self, action: str, message: str, dsn: str = "") -> None:
        self.action = action
        self.message = message
        self.dsn = dsn


class DatabaseIdentity:
    """The parts of a URL that name one database, ignoring the role."""

    def __init__(
        self, driver: str, host: str, port: int | None, database: str
    ) -> None:
        self.driver = driver
        self.host = host
        self.port = port
        self.database = database

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DatabaseIdentity):
            return NotImplemented
        return (
            self.driver == other.driver
            and self.port == other.port
            and self.database == other.database
            and _same_host(self.host, other.host)
        )

    def __hash__(self) -> int:
        host = "local" if self.host in _LOCAL_HOSTS else self.host
        return hash((self.driver, host, self.port, self.database))


def _same_host(left: str, right: str) -> bool:
    if left == right:
        return True
    return left in _LOCAL_HOSTS and right in _LOCAL_HOSTS


def database_identity(url: str) -> DatabaseIdentity:
    """Return the driver, host, port, and database name for ``url``.

    ``postgresql+psycopg2://`` and ``postgresql://`` are the same
    driver. An omitted PostgreSQL port is 5432. The role and the
    password are not part of the identity: two roles can own the
    same database.
    """
    parsed = make_url(url)
    driver = parsed.drivername.split("+", 1)[0]
    raw_host = (parsed.host or "").lower()
    if raw_host in _LOOPBACK_HOSTS:
        host = "loopback"
    elif raw_host == "":
        host = "local-socket"
    else:
        host = raw_host
    port = parsed.port
    if port is None and driver == "postgresql":
        port = 5432
    database = (parsed.database or "").lower()
    return DatabaseIdentity(driver, host, port, database)


def same_database(left: str, right: str) -> bool:
    """Return whether both URLs name the same database."""
    return database_identity(left) == database_identity(right)


def database_name_is_allowed(name: str) -> bool:
    """Return whether ``name`` contains ``test`` as its own word.

    The check is case-insensitive. ``investment_test``, ``test``,
    and ``test_db`` pass. ``testing`` and ``testdb`` do not, because
    the letters after ``test`` are not an underscore or the end of
    the name.
    """
    return _TEST_DATABASE_NAME.search(name.lower()) is not None


def _matches_application_database(
    test_url: str, application_urls: Iterable[str | None]
) -> bool:
    for application_url in application_urls:
        if application_url is None:
            continue
        candidate = application_url.strip()
        if not candidate:
            continue
        if test_url == candidate:
            return True
        try:
            if same_database(test_url, candidate):
                return True
        except (ArgumentError, ValueError):
            # An unparseable application URL can still match exactly,
            # which was checked above. ValueError is a bad port.
            continue
    return False


def allow_remote_requested(environ: Mapping[str, str]) -> bool:
    """Return whether the host allowlist may accept a remote URL.

    Only the exact value ``1`` opts in. ``true``, ``yes``, and an
    empty string stay on the local-host rule.
    """
    return environ.get("TEST_POSTGRES_ALLOW_REMOTE") == "1"


def dotenv_database_url(directory: str | None = None) -> str | None:
    """Return ``DATABASE_URL`` from a ``.env`` file, without applying it.

    The integration session imports ``Settings`` from an empty
    directory, so the file is not part of ``settings.DATABASE_URL``.
    libpq would still open whatever ``TEST_POSTGRES_DSN`` names, and
    that name might be the database in the file. The caller adds
    this value to the application-database denylist.
    """
    folder = os.getcwd() if directory is None else directory
    path = os.path.join(folder, ".env")
    if not os.path.isfile(path):
        return None
    # Imported here so this module can be read without loading
    # pydantic. python-dotenv is already an application dependency.
    from dotenv import dotenv_values

    values = dotenv_values(path)
    if not values:
        return None
    raw = values.get("DATABASE_URL")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _query_pairs(url: str) -> list[tuple[str, str]]:
    """Every query pair, including repeated keys and empty values."""
    return parse_qsl(urlsplit(url).query, keep_blank_values=True)


def _host_token_is_local(token: str, *, allow_socket: bool) -> bool:
    text = token.strip()
    lowered = text.lower()
    if lowered in _LOOPBACK_HOSTS or lowered == "[::1]":
        return True
    if allow_socket and text.startswith("/") and text != "/":
        return True
    return False


def _query_problem(pairs: list[tuple[str, str]]) -> str | None:
    for key, _value in pairs:
        if key.lower() in _FORBIDDEN_QUERY_KEYS:
            return QUERY_MESSAGE
    for key, value in pairs:
        if key.lower() != "host":
            continue
        for token in value.split(","):
            if not _host_token_is_local(token, allow_socket=True):
                return QUERY_HOST_MESSAGE
    return None


def _url_specifies_host(
    identity: DatabaseIdentity, pairs: list[tuple[str, str]]
) -> bool:
    if identity.host != "local-socket":
        return True
    return any(key.lower() == "host" for key, _value in pairs)


def _env_host_problem(environ: Mapping[str, str]) -> str | None:
    service = (environ.get("PGSERVICE") or "").strip()
    if service:
        return ENV_HOST_MESSAGE
    hostaddr = environ.get("PGHOSTADDR")
    if hostaddr is not None and hostaddr.strip():
        for token in hostaddr.split(","):
            if not _host_token_is_local(token, allow_socket=False):
                return ENV_HOST_MESSAGE
    host = environ.get("PGHOST")
    if host is not None and host.strip():
        for token in host.split(","):
            if not _host_token_is_local(token, allow_socket=True):
                return ENV_HOST_MESSAGE
    return None


def decide_test_dsn(
    test_dsn: str | None,
    application_urls: Iterable[str | None],
    require: bool,
    *,
    allow_remote: bool = False,
    environ: Mapping[str, str] | None = None,
) -> DsnDecision:
    """Choose skip, fail, or use for one integration run.

    Missing configuration skips, unless ``require`` is true (the CI
    job). A present URL is allowed only when all of these hold:

    - the database name contains ``test`` as its own word
    - the host is loopback or a Unix socket, unless ``allow_remote``
    - query parameters do not override that database or server
    - a URL with no host does not inherit a remote ``PGHOST``,
      ``PGHOSTADDR``, or ``PGSERVICE``
    - the URL is not the application's own database

    ``environ`` defaults to the process environment. Tests pass a
    mapping so a developer's ``PGHOST`` is not part of the example.

    The tests drop and recreate their tables, so a URL that fails
    any of those checks fails closed and does not connect.
    ``allow_remote`` does not relax the query-parameter or
    environment checks.
    """
    env = os.environ if environ is None else environ
    raw = "" if test_dsn is None else test_dsn.strip()
    if not raw:
        if require:
            return DsnDecision("fail", REQUIRE_MESSAGE)
        return DsnDecision("skip", SKIP_MESSAGE)
    if not raw.lower().startswith("postgres"):
        return DsnDecision("fail", SCHEME_MESSAGE)
    try:
        identity = database_identity(raw)
    except (ArgumentError, ValueError) as exc:
        # ArgumentError is a bad URL shape. ValueError is a port that
        # is not an integer. The message names the type only: the
        # parser's own text repeats the URL, which may contain a
        # password.
        return DsnDecision(
            "fail",
            "TEST_POSTGRES_DSN is not a valid database URL "
            f"({type(exc).__name__}).",
        )
    pairs = _query_pairs(raw)
    query_problem = _query_problem(pairs)
    if query_problem is not None:
        return DsnDecision("fail", query_problem)
    if identity.database == "":
        return DsnDecision("fail", DATABASE_MESSAGE)
    if not database_name_is_allowed(identity.database):
        return DsnDecision("fail", NAME_MESSAGE)
    if not _url_specifies_host(identity, pairs):
        env_problem = _env_host_problem(env)
        if env_problem is not None:
            return DsnDecision("fail", env_problem)
    if identity.host not in _LOCAL_HOSTS and not allow_remote:
        return DsnDecision("fail", HOST_MESSAGE)
    if _matches_application_database(raw, application_urls):
        return DsnDecision("fail", REFUSE_MESSAGE)
    return DsnDecision(
        "use",
        "TEST_POSTGRES_DSN is an allowed test database.",
        raw,
    )
