"""PostgreSQL fixtures for tests marked ``integration``.

``tests/conftest.py`` is the SQLite ``client`` fixture. This file does
not replace that fixture and does not open a connection on import.

The engine here is built only from ``TEST_POSTGRES_DSN``. It is not
``app.core.database.engine``, which is created from
``settings.DATABASE_URL`` when the application is imported.

When the command selects the ``integration`` marker, the repository
root ``conftest.py`` imports the application first, from a directory
with no ``.env`` file. The imports below then reuse that already
built ``Settings``. The default SQLite command does not select the
marker, so it never takes that path.

Tables are created with ``Base.metadata.create_all``. Alembic is not
used: the baseline revision is issue #8, and ``alembic.ini`` still has
a ``version_num_format`` value that crashes Alembic commands.
"""

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, settings
from app.core.database import Base, create_db_engine, get_db
from main import create_app
from tests.integration.postgres_dsn import decide_test_dsn


def _dsn_decision():
    """Read the environment at fixture time, not at import time."""
    require = os.environ.get("REQUIRE_POSTGRES") == "1"
    # "1" is the only override. An empty value or any other string
    # keeps the host allowlist, which is the safe default.
    allow_remote = os.environ.get("TEST_POSTGRES_ALLOW_REMOTE") == "1"
    default_url = Settings.model_fields["DATABASE_URL"].default
    return decide_test_dsn(
        os.environ.get("TEST_POSTGRES_DSN"),
        (settings.DATABASE_URL, default_url),
        require,
        allow_remote=allow_remote,
    )


def _stop_unless_usable(decision):
    if decision.action == "skip":
        pytest.skip(decision.message)
    if decision.action == "fail":
        pytest.fail(decision.message)


def _use_warsaw_timezone(connection):
    """Set the session time zone at the start of each transaction.

    A manual check used PostgreSQL 16 with ``Europe/Warsaw``. December
    is UTC+1 there and June is UTC+2, so a value that was shifted into
    the session zone does not read back as the UTC instant.

    ``SET TIME ZONE`` stays in effect after COMMIT. Only ROLLBACK
    reverts it. The ``begin`` event sets ``Europe/Warsaw`` on every
    transaction, including after a constraint error, so a rolled-back
    test cannot leave the pooled connection on the server default.
    The server default can stay UTC.
    """
    connection.exec_driver_sql("SET TIME ZONE 'Europe/Warsaw'")


def _prepare_schema(engine):
    # Drop first so a crashed earlier run cannot leave a stale shape.
    # This is safe only because the DSN check refused the application
    # database before this engine existed.
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def empty_application_tables(engine):
    """Delete rows from the application tables and restart ids."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE financial_metrics, companies "
                "RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture(scope="session")
def postgres_engine():
    """One engine for the integration session, or a skip/fail.

    Skip when ``TEST_POSTGRES_DSN`` is unset. Fail when the database
    name does not contain ``test`` as its own word, when the host is
    not this machine and ``TEST_POSTGRES_ALLOW_REMOTE`` is not ``1``,
    when the URL is the application database, when
    ``REQUIRE_POSTGRES=1`` and the variable is unset, or when the
    server rejects the connection.
    """
    decision = _dsn_decision()
    _stop_unless_usable(decision)
    engine = create_db_engine(decision.dsn)
    event.listen(engine, "begin", _use_warsaw_timezone)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        _prepare_schema(engine)
    except Exception as exc:
        engine.dispose()
        pytest.fail(
            "Could not prepare the PostgreSQL test database "
            f"({type(exc).__name__}: {exc}). "
            "TEST_POSTGRES_DSN must reach a server and a database "
            "where this role can create tables."
        )
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def postgres_session_factory(postgres_engine):
    """A session factory and an empty pair of application tables."""
    factory = sessionmaker(
        autocommit=False, autoflush=False, bind=postgres_engine
    )
    empty_application_tables(postgres_engine)
    yield factory
    empty_application_tables(postgres_engine)


@pytest_asyncio.fixture()
async def postgres_client(postgres_session_factory):
    """HTTP client whose database sessions use the PostgreSQL factory.

    Startup does not call ``init_db``. That helper uses the application
    engine and would open ``settings.DATABASE_URL``.
    """

    def override_get_db():
        db = postgres_session_factory()
        try:
            yield db
        finally:
            db.close()

    app = create_app(init_database_on_startup=False)
    app.state.testing_session_local = postgres_session_factory
    app.dependency_overrides[get_db] = override_get_db

    # Host 127.0.0.1 is in ALLOWED_HOSTS. TrustedHostMiddleware
    # rejects the name "testserver" with HTTP 400, which would fail
    # every API-level PostgreSQL test once that middleware is on.
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://127.0.0.1",
    ) as test_client:
        test_client.app = app
        yield test_client

    app.dependency_overrides.clear()
