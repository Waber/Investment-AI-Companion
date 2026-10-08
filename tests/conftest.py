import os

# The app requires SECRET_KEY and rejects the old placeholders. CI does
# not set the variable. Set it before importing the app so collection
# does not depend on a developer .env file. A test that checks the
# missing-key failure deletes this name first.
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest")

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.database import Base, create_db_engine, get_db  # noqa: E402
from main import create_app  # noqa: E402


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
        base_url="http://testserver",
    ) as test_client:
        test_client.app = app
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
