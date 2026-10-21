"""Revision 0005 on PostgreSQL, in a schema the other tests do not use.

The public schema stays on create_all. This test drops its own schema
when it finishes, including the Alembic version table.
"""

import pytest
from sqlalchemy import inspect, text

from alembic import command
from app.core.database import Base
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

            command.downgrade(_config(connection), "0004")
            connection.execute(text(f"SET search_path TO {SCHEMA}"))
            tables = set(inspect(connection).get_table_names())
            assert "notes" not in tables
            assert "theses" not in tables
            assert "price_bars" in tables
            assert "watchlist_items" in tables

            upgrade_head(connection)
            connection.execute(text(f"SET search_path TO {SCHEMA}"))
            tables = set(inspect(connection).get_table_names())
            assert "notes" in tables
            assert "theses" in tables
            assert research_schema(connection) == from_model
        finally:
            connection.rollback()
            connection.execute(text("SET search_path TO public"))
            connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
            connection.commit()


def test_autogenerate_against_postgresql_notes_is_empty(postgres_engine):
    """Same empty ``compare_metadata`` check, on a scratch schema.

    ``public`` is the schema the other PostgreSQL tests share. This
    one builds a full model there is no reason to share, drops
    ``notes`` and ``theses``, stamps ``0004``, and upgrades. Price
    bars and the watchlist from ``create_all`` stay in place. The
    schema is removed afterwards, including the Alembic version
    table.
    """
    schema = "notes_autogen"
    with postgres_engine.connect() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        connection.execute(text(f"CREATE SCHEMA {schema}"))
        connection.execute(text(f"SET search_path TO {schema}"))
        connection.commit()
        try:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("DROP TABLE theses"))
            connection.execute(text("DROP TABLE notes"))
            connection.commit()
            config = _config(connection)
            command.stamp(config, "0004")
            upgrade_head(connection)
            connection.execute(text(f"SET search_path TO {schema}"))
            assert_compare_metadata_is_empty(connection)
        finally:
            connection.rollback()
            connection.execute(text("SET search_path TO public"))
            connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            connection.commit()
