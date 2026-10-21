"""Revision 0002 candle checks on PostgreSQL.

The public schema stays on create_all. This test uses its own schema
and drops it, including the Alembic version table.
"""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.models.database_models import PriceBarDB
from tests.company_migration import (
    LEGACY_COMPANIES,
    LEGACY_METRICS,
    downgrade_base,
    upgrade_head,
)
from tests.price_bar_checks import (
    CANDLE_CHECK_NAMES,
    CANDLE_VIOLATIONS,
    NULL_BAR_SQL,
    check_names,
    model_check_names,
    price_bar_structure,
    violation_sql,
)

pytestmark = pytest.mark.integration

SCHEMA = "price_bar_migration"


def _scratch(connection):
    connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))
    connection.execute(text(f"SET search_path TO {SCHEMA}"))
    connection.commit()


def _drop(connection):
    connection.rollback()
    connection.execute(text("SET search_path TO public"))
    connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    connection.commit()


def test_migrated_postgres_price_bars_match_the_model(postgres_engine):
    """The public create_all table and revision 0002 agree.

    Volume is BIGINT, the foreign key cascades, and the redundant
    indexes are absent. That is an empty autogenerate diff for
    ``price_bars``.
    """
    with postgres_engine.connect() as public:
        public.execute(text("SET search_path TO public"))
        from_model = price_bar_structure(public)
    with postgres_engine.connect() as connection:
        _scratch(connection)
        try:
            connection.execute(text(LEGACY_COMPANIES))
            connection.execute(text(LEGACY_METRICS))
            connection.commit()
            upgrade_head(connection)
            from_migration = price_bar_structure(connection)
            assert from_migration == from_model
            volume = dict(
                (name, (kind, nullable))
                for name, kind, nullable in from_migration["columns"]
            )
            assert volume["volume"][0] == "BIGINT"
            assert "ix_price_bars_id" not in from_migration["indexes"]
            assert (
                "ix_price_bars_instrument_id" not in from_migration["indexes"]
            )
            assert from_migration["foreign_keys"][0][2].upper() == "CASCADE"
        finally:
            _drop(connection)


def test_postgres_cascade_deletes_bars_with_the_company(postgres_engine):
    with postgres_engine.connect() as connection:
        _scratch(connection)
        try:
            connection.execute(text(LEGACY_COMPANIES))
            connection.execute(text(LEGACY_METRICS))
            connection.execute(
                text(
                    "INSERT INTO companies (id, name, ticker) "
                    "VALUES (1, 'Apple', 'AAPL')"
                )
            )
            connection.commit()
            upgrade_head(connection)
            connection.execute(text(NULL_BAR_SQL))
            connection.commit()
            connection.execute(text("DELETE FROM companies WHERE id = 1"))
            connection.commit()
            remaining = connection.execute(
                text("SELECT COUNT(*) FROM price_bars")
            ).scalar()
            assert remaining == 0
            downgrade_base(connection)
            assert "price_bars" not in inspect(connection).get_table_names()
        finally:
            _drop(connection)


def test_upgrade_adds_candle_checks_and_downgrade_drops_them(postgres_engine):
    with postgres_engine.connect() as public:
        public.execute(text("SET search_path TO public"))
        from_model_db = check_names(public)

    with postgres_engine.connect() as connection:
        _scratch(connection)
        try:
            connection.execute(text(LEGACY_COMPANIES))
            connection.execute(text(LEGACY_METRICS))
            connection.execute(
                text(
                    "INSERT INTO companies (id, name, ticker) "
                    "VALUES (1, 'Apple', 'AAPL')"
                )
            )
            connection.commit()
            upgrade_head(connection)
            assert "price_bars" in inspect(connection).get_table_names()
            migrated = check_names(connection)
            assert migrated == set(CANDLE_CHECK_NAMES)
            assert migrated == from_model_db
            assert model_check_names(PriceBarDB) == set(CANDLE_CHECK_NAMES)
            connection.execute(text(NULL_BAR_SQL))
            connection.commit()
            downgrade_base(connection)
            assert "price_bars" not in inspect(connection).get_table_names()
            assert (
                connection.execute(
                    text("SELECT ticker FROM companies WHERE id = 1")
                ).scalar()
                == "AAPL"
            )
        finally:
            _drop(connection)


@pytest.mark.parametrize(
    ("columns", "values", "constraint"),
    CANDLE_VIOLATIONS,
)
def test_upgraded_postgres_rejects_each_candle_violation(
    postgres_engine, columns, values, constraint
):
    with postgres_engine.connect() as connection:
        _scratch(connection)
        try:
            connection.execute(text(LEGACY_COMPANIES))
            connection.execute(text(LEGACY_METRICS))
            connection.execute(
                text(
                    "INSERT INTO companies (id, name, ticker) "
                    "VALUES (1, 'Apple', 'AAPL')"
                )
            )
            connection.commit()
            upgrade_head(connection)
            with pytest.raises(IntegrityError) as caught:
                connection.execute(text(violation_sql(columns, values)))
            assert constraint in str(caught.value)
            connection.rollback()
            connection.execute(text(f"SET search_path TO {SCHEMA}"))
            connection.execute(text(NULL_BAR_SQL))
            connection.commit()
            downgrade_base(connection)
            assert "price_bars" not in inspect(connection).get_table_names()
            assert (
                connection.execute(
                    text("SELECT ticker FROM companies WHERE id = 1")
                ).scalar()
                == "AAPL"
            )
        finally:
            _drop(connection)
