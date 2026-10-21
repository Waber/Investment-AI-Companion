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
