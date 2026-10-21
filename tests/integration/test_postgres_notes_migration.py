"""Revision 0033 on PostgreSQL, in a schema the other tests do not use.

The public schema stays on create_all. This test drops its own schema
when it finishes, including the Alembic version table.
"""

import pytest
from sqlalchemy import inspect, text

from alembic import command
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

pytestmark = pytest.mark.integration

SCHEMA = "notes_migration"


def test_upgrade_creates_notes_and_downgrade_removes_them(postgres_engine):
    with postgres_engine.connect() as public:
        public.execute(text("SET search_path TO public"))
        public.commit()
        from_model = research_schema(public)

    with postgres_engine.connect() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))
        connection.execute(text(f"SET search_path TO {SCHEMA}"))
        connection.commit()
        try:
            connection.execute(text(LEGACY_COMPANIES))
            connection.execute(text(LEGACY_METRICS))
            connection.commit()
            upgrade_head(connection)
            connection.execute(text(f"SET search_path TO {SCHEMA}"))
            assert research_schema(connection) == from_model
            assert_declared_lengths(connection)
            exercise_migrated_research(connection)
            connection.execute(text(f"SET search_path TO {SCHEMA}"))

            command.downgrade(_config(connection), "0001")
            connection.execute(text(f"SET search_path TO {SCHEMA}"))
            tables = set(inspect(connection).get_table_names())
            assert "notes" not in tables
            assert "theses" not in tables
            columns = set(
                connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = :schema "
                        "AND table_name = 'companies'"
                    ),
                    {"schema": SCHEMA},
                ).scalars()
            )
            assert "instrument_type" in columns

            command.downgrade(_config(connection), "base")
            connection.execute(text(f"SET search_path TO {SCHEMA}"))
            columns = set(
                connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = :schema "
                        "AND table_name = 'companies'"
                    ),
                    {"schema": SCHEMA},
                ).scalars()
            )
            assert "instrument_type" not in columns
            assert "isin" not in columns
        finally:
            connection.rollback()
            connection.execute(text("SET search_path TO public"))
            connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
            connection.commit()
