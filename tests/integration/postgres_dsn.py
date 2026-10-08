"""Decide whether a PostgreSQL integration run may open a database.

The application default is ``settings.DATABASE_URL``. That value comes
from the environment, a ``.env`` file, or the code default in
``app/core/config.py``. The harness must not open that database.
Importing this module does not connect to anything.
"""

from collections.abc import Iterable

from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import ArgumentError

# Hosts that mean "this machine". A Unix-socket URL has no host, and
# that socket is the local server, same as localhost.
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_LOCAL_HOSTS = frozenset({"loopback", "local-socket"})

SKIP_MESSAGE = (
    "PostgreSQL integration tests need TEST_POSTGRES_DSN set to a "
    "database that is not the application's DATABASE_URL. "
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


def decide_test_dsn(
    test_dsn: str | None,
    application_urls: Iterable[str | None],
    require: bool,
) -> DsnDecision:
    """Choose skip, fail, or use for one integration run.

    Missing configuration skips, unless ``require`` is true (the CI
    job). A URL that names the application's database fails closed:
    the tests drop and recreate their tables.
    """
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
    if identity.database == "":
        return DsnDecision("fail", DATABASE_MESSAGE)
    if _matches_application_database(raw, application_urls):
        return DsnDecision("fail", REFUSE_MESSAGE)
    return DsnDecision("use", "TEST_POSTGRES_DSN is a separate database.", raw)
