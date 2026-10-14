import os

# The app requires SECRET_KEY and rejects the old placeholders. CI does
# not set the variable. Set it before importing the app so collection
# does not depend on a developer .env file. A test that checks the
# missing-key failure deletes this name first.
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-0123456789")

# DATA_COLLECTOR=fake and YF_DISABLE_CURL_CFFI are set in the root
# conftest.py, which pytest imports first (see the comment there).

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api.data_collection import reset_collector  # noqa: E402
from app.core.database import Base, create_db_engine, get_db  # noqa: E402
from main import create_app  # noqa: E402
from tests import network_guard  # noqa: E402


@pytest.fixture(autouse=True)
def block_network(request, monkeypatch):
    """Fail a test that reaches a non-loopback address or host name.

    Loopback and Unix sockets stay allowed. The guard patches Python's
    ``socket`` module only, so it cannot see C clients such as libpq.
    Tests marked ``integration`` are exempt because they connect to a
    PostgreSQL server that the developer chooses (``TEST_POSTGRES_DSN``),
    which may not be on this machine.

    The fixture yields the list of blocked attempts. Code under test can
    swallow the error, so a non-empty list fails the test at teardown. A
    test that blocks on purpose calls ``attempts.clear()``.
    """
    if request.node.get_closest_marker("integration") is not None:
        yield []
        return
    network_guard.install(monkeypatch)
    yield network_guard.ATTEMPTS
    attempts = list(network_guard.ATTEMPTS)
    network_guard.ATTEMPTS.clear()
    assert not attempts, f"Network access was attempted: {attempts}"


@pytest.fixture(autouse=True)
def fresh_shared_collector():
    """Each test starts and ends without the shared Yahoo collector.

    It lives at module level, so the cache or rate-limit state of one
    test would otherwise leak into the next.
    """
    reset_collector()
    yield
    reset_collector()


@pytest_asyncio.fixture()
async def client():
    # The same SQLite foreign-key hook as the application engine.
    # StaticPool keeps one connection for the in-memory database.
    engine = create_db_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app = create_app(init_database_on_startup=False)
    app.state.testing_session_local = testing_session_local
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://127.0.0.1",
    ) as test_client:
        test_client.app = app
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
