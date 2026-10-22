"""Revision 0007 on PostgreSQL, in a schema the other tests do not use."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.company_migration import (
    LEGACY_COMPANIES,
    LEGACY_METRICS,
    assert_plain_ticker_index_recorded,
    downgrade_to,
    unique_constraint_names,
    upgrade_to,
    upper_ticker_index,
)

pytestmark = pytest.mark.integration


def _scratch(postgres_engine, schema):
    connection = postgres_engine.connect()
    connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    connection.execute(text(f"CREATE SCHEMA {schema}"))
    connection.execute(text(f"SET search_path TO {schema}"))
    connection.commit()
    return connection


def _drop_scratch(connection, schema):
    connection.rollback()
    connection.execute(text("SET search_path TO public"))
    connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    connection.commit()
    connection.close()


def _version(connection):
    return connection.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar()


def _child_counts(connection):
    return {
        name: connection.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar()
        for name in (
            "companies",
            "financial_metrics",
            "price_bars",
            "watchlist_items",
            "notes",
            "theses",
        )
    }


def test_case_collision_stops_before_the_index_changes(postgres_engine):
    """``aapl`` and ``AAPL`` are named. Nothing is rewritten."""
    schema = "ticker_upper_case"
    connection = _scratch(postgres_engine, schema)
    try:
        connection.execute(text(LEGACY_COMPANIES))
        connection.execute(text(LEGACY_METRICS))
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) "
                "VALUES (1, 'Upper', 'AAPL')"
            )
        )
        connection.commit()
        upgrade_to(connection, "0005")
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) "
                "VALUES (2, 'Lower', 'aapl')"
            )
        )
        connection.commit()
        with pytest.raises(RuntimeError) as error:
            upgrade_to(connection, "0007")
        message = str(error.value)
        assert error.value.__class__.__name__ == "UpperTickerCollision"
        assert "'aapl'" in message
        assert "'AAPL'" in message
        assert "did not change those rows" in message
        connection.rollback()
        connection.execute(text(f"SET search_path TO {schema}"))
        assert _version(connection) == "0005"
        stored = (
            connection.execute(
                text("SELECT ticker FROM companies ORDER BY id")
            )
            .scalars()
            .all()
        )
        assert stored == ["AAPL", "aapl"]
        assert upper_ticker_index(connection) is None
    finally:
        _drop_scratch(connection, schema)


def test_a_trailing_space_is_not_an_upper_collision(postgres_engine):
    """``upper(ticker)`` keeps ``AAPL`` and ``AAPL `` as two rows."""
    schema = "ticker_upper_space"
    connection = _scratch(postgres_engine, schema)
    try:
        connection.execute(text(LEGACY_COMPANIES))
        connection.execute(text(LEGACY_METRICS))
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) "
                "VALUES (1, 'Plain', 'AAPL')"
            )
        )
        connection.commit()
        upgrade_to(connection, "0005")
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) "
                "VALUES (2, 'Padded', 'AAPL ')"
            )
        )
        connection.commit()
        upgrade_to(connection, "0007")
        stored = (
            connection.execute(
                text("SELECT ticker FROM companies ORDER BY id")
            )
            .scalars()
            .all()
        )
        assert stored == ["AAPL", "AAPL "]
        assert upper_ticker_index(connection) == (
            "uq_companies_ticker",
            True,
            ("upper(ticker::text)",),
        )
        assert_plain_ticker_index_recorded(connection)
        downgrade_to(connection, "0005")
        missing = connection.execute(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE schemaname = current_schema() "
                "AND indexname = 'ix_companies_ticker'"
            )
        ).scalar()
        assert missing is None
    finally:
        _drop_scratch(connection, schema)


def test_round_trip_keeps_child_rows(postgres_engine):
    """Upgrade to 0007 and back to 0005 keeps every child row."""
    schema = "ticker_upper_children"
    connection = _scratch(postgres_engine, schema)
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
        upgrade_to(connection, "0005")
        connection.execute(
            text(
                "INSERT INTO financial_metrics (id, company_id) "
                "VALUES (1, 1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO price_bars ("
                "id, instrument_id, bar_date, currency, source, "
                "retrieved_at) VALUES ("
                "7, 1, '2024-01-02', 'USD', 'fake', "
                "'2024-01-02 00:00:00+00')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO watchlist_items (id, company_id, added_at) "
                "VALUES (1, 1, '2024-01-02 00:00:00+00')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO notes (id, company_id, body) "
                "VALUES (1, 1, 'a note')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO theses (id, company_id, title, body) "
                "VALUES (1, 1, 'a title', 'a body')"
            )
        )
        connection.commit()
        before = _child_counts(connection)
        upgrade_to(connection, "0007")
        # The count above left a transaction open. Commit the upgrade
        # before the insert that is rolled back, or that rollback
        # returns the schema to 0005 and the downgrade does not run.
        connection.commit()
        assert _child_counts(connection) == before
        assert upper_ticker_index(connection) == (
            "uq_companies_ticker",
            True,
            ("upper(ticker::text)",),
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO companies (id, name, ticker) "
                    "VALUES (2, 'Lower', 'aapl')"
                )
            )
        connection.rollback()
        connection.execute(text(f"SET search_path TO {schema}"))
        downgrade_to(connection, "0005")
        assert _child_counts(connection) == before
        assert upper_ticker_index(connection) is None
        names = unique_constraint_names(connection)
        assert "uq_company_name_ticker" in names
        upgrade_to(connection, "0007")
        assert _child_counts(connection) == before
        assert "uq_company_name_ticker" not in unique_constraint_names(
            connection
        )
    finally:
        _drop_scratch(connection, schema)


def test_pair_constraint_is_dropped_and_children_stay(postgres_engine):
    """``ALTER TABLE`` drops the pair constraint. Child rows stay."""
    schema = "ticker_upper_constraint"
    connection = _scratch(postgres_engine, schema)
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
        upgrade_to(connection, "0005")
        connection.execute(
            text(
                "ALTER TABLE companies ADD CONSTRAINT "
                "uq_company_name_ticker UNIQUE (name, ticker)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO financial_metrics (id, company_id) "
                "VALUES (1, 1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO price_bars ("
                "id, instrument_id, bar_date, currency, source, "
                "retrieved_at) VALUES ("
                "7, 1, '2024-01-02', 'USD', 'fake', "
                "'2024-01-02 00:00:00+00')"
            )
        )
        connection.commit()
        upgrade_to(connection, "0007")
        assert connection.execute(
            text("SELECT id, instrument_id FROM price_bars")
        ).one() == (7, 1)
        assert connection.execute(
            text("SELECT id, company_id FROM financial_metrics")
        ).one() == (1, 1)
        assert "uq_company_name_ticker" not in unique_constraint_names(
            connection
        )
        assert upper_ticker_index(connection) == (
            "uq_companies_ticker",
            True,
            ("upper(ticker::text)",),
        )
        downgrade_to(connection, "0005")
        assert (
            connection.execute(text("SELECT id FROM price_bars")).scalar() == 7
        )
        assert "uq_company_name_ticker" in unique_constraint_names(connection)
        assert upper_ticker_index(connection) is None
    finally:
        _drop_scratch(connection, schema)
