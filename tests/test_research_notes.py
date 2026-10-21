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
from app.models.database_models import CompanyDB, NoteDB, ThesisDB
from app.repositories.note_repository import NoteRepository
from app.repositories.thesis_repository import ThesisRepository
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


def test_revision_0033_is_the_only_head_and_follows_0002():
    """0033 sits on the price-bar revision. The id stays 0033.

    Master's head is 0002. This branch does not rename 0033 to
    the next integer. A later migration from another pull request
    has to be linked by ``down_revision`` after it merges.
    """
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    assert script.get_current_head() == "0033"
    revision = script.get_revision("0033")
    assert revision.down_revision == "0002"


def test_sqlite_loads_a_stored_row_the_write_models_would_reject(session):
    """Read models do not re-run write validation.

    SQLite will store a NUL and a title longer than 200 characters.
    PostgreSQL would reject both at insert time, so this case stays
    on the SQLite suite. ``list_for_company`` and ``get`` must return
    the row. One bad body must not fail the whole list.
    """
    company = CompanyDB(name="Acme", ticker="RAW")
    session.add(company)
    session.commit()
    session.add(NoteDB(company_id=company.id, body="bad\x00body"))
    session.add(
        ThesisDB(
            company_id=company.id,
            title="t" * 201,
            body="bad\x00body",
            thesis_breakers="",
            status="active",
        )
    )
    session.commit()

    notes = NoteRepository(session)
    listed_notes = notes.list_for_company(company.id)
    assert len(listed_notes) == 1
    assert listed_notes[0].body == "bad\x00body"
    assert notes.get(company.id, listed_notes[0].id).body == "bad\x00body"

    theses = ThesisRepository(session)
    listed = theses.list_for_company(company.id)
    assert len(listed) == 1
    assert listed[0].title == "t" * 201
    assert listed[0].body == "bad\x00body"
    loaded = theses.get(company.id, listed[0].id)
    assert loaded.title == "t" * 201
    assert loaded.body == "bad\x00body"


def test_sqlite_session_enforces_foreign_keys(session):
    from sqlalchemy import text

    assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1
