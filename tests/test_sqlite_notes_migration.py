"""Revision 0033 on a legacy SQLite file.

PostgreSQL is covered by
tests/integration/test_postgres_notes_migration.py.
"""

from sqlalchemy import inspect, text

from alembic import command
from app.core.database import Base, create_db_engine
from tests.company_migration import (
    LEGACY_COMPANIES,
    LEGACY_METRICS,
    _config,
    upgrade_head,
)
from tests.research_migration import (
    assert_compare_metadata_is_empty,
    assert_declared_lengths,
    exercise_migrated_research,
    research_schema,
)


def test_upgrade_creates_notes_and_downgrade_removes_them(tmp_path):
    model_engine = create_db_engine(f"sqlite:///{tmp_path / 'model.db'}")
    Base.metadata.create_all(model_engine)
    with model_engine.connect() as connection:
        from_model = research_schema(connection)
    model_engine.dispose()

    engine = create_db_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(text(LEGACY_COMPANIES))
        connection.execute(text(LEGACY_METRICS))
    with engine.connect() as connection:
        upgrade_head(connection)
        assert research_schema(connection) == from_model
        assert_declared_lengths(connection)
        exercise_migrated_research(connection)

        command.downgrade(_config(connection), "0001")
        tables = set(inspect(connection).get_table_names())
        assert "notes" not in tables
        assert "theses" not in tables
        columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(companies)"))
        }
        assert "instrument_type" in columns

        command.downgrade(_config(connection), "base")
        columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(companies)"))
        }
        assert "instrument_type" not in columns
        assert "isin" not in columns
    engine.dispose()


def test_autogenerate_against_sqlite_notes_is_empty(tmp_path):
    """create_all, then let revision 0033 rebuild notes and theses.

    ``compare_metadata`` is empty only when every table matches the
    models. A legacy companies table would still show diffs, so this
    database is built with ``create_all``. Dropping the research
    tables and stamping ``0002`` makes revision 0033 create them
    again. Price bars stay, because that revision already ran on
    master. An empty diff means 0033 matches ``NoteDB`` and
    ``ThesisDB``.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'full.db'}")
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE theses"))
        connection.execute(text("DROP TABLE notes"))
    with engine.connect() as connection:
        config = _config(connection)
        command.stamp(config, "0002")
        upgrade_head(connection)
        assert_compare_metadata_is_empty(connection)
    engine.dispose()
