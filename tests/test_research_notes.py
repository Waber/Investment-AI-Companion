"""Notes and theses on SQLite.

PostgreSQL runs the same cases in
``tests/integration/test_postgres_research_notes.py``.
"""

import pytest
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.database import Base, create_db_engine
from tests.research_cases import ResearchBehavior


class TestResearchNotesSqlite(ResearchBehavior):
    """The shared cases, against an in-memory SQLite database."""


@pytest.fixture
def session():
    engine = create_db_engine(
        "sqlite+pysqlite:///:memory:",
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_revision_0033_is_the_only_head_and_follows_0001():
    """Master's head is 0001. This branch adds 0033 on top of it.

    0033 is the issue number. Open revisions named 0002 belong to
    other pull requests and are not on this branch.
    """
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    assert script.get_current_head() == "0033"
    revision = script.get_revision("0033")
    assert revision.down_revision == "0001"


def test_sqlite_session_enforces_foreign_keys(session):
    from sqlalchemy import text

    assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1
