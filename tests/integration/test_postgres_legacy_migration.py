"""Revision 0001 on PostgreSQL, in a schema the other tests do not use.

The public schema stays on create_all. This test drops its own schema
when it finishes, including the Alembic version table.
"""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.database import Base
from app.core.init_db import require_company_instrument_columns
from tests.company_migration import (
    EXPECTED_ISIN_UNIQUENESS,
    LEGACY_COMPANIES,
    LEGACY_METRICS,
    assert_empty_metadata_diff,
    downgrade_base,
    downgrade_to,
    duplicate_ticker_message,
    isin_uniqueness,
    stamp,
    ticker_uniqueness,
    upgrade_head,
    upper_ticker_index,
)

pytestmark = pytest.mark.integration

SCHEMA = "company_migration"


def test_upgrade_sets_stock_on_postgresql(postgres_engine):
    with postgres_engine.connect() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))
        connection.execute(text(f"SET search_path TO {SCHEMA}"))
        connection.commit()
        try:
            connection.execute(text(LEGACY_COMPANIES))
            connection.execute(text(LEGACY_METRICS))
            connection.execute(
                text(
                    "INSERT INTO companies (id, name, ticker) "
                    "VALUES (1, 'Apple', 'AAPL')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO financial_metrics (id, company_id) "
                    "VALUES (1, 1)"
                )
            )
            connection.commit()

            upgrade_head(connection)
            require_company_instrument_columns(connection)
            stored = connection.execute(
                text(
                    "SELECT instrument_type, isin "
                    "FROM companies WHERE id = 1"
                )
            ).one()
            assert stored.instrument_type == "STOCK"
            assert stored.isin is None
            assert (
                connection.execute(
                    text("SELECT company_id FROM financial_metrics")
                ).scalar()
                == 1
            )

            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO companies "
                        "(id, name, ticker, instrument_type) "
                        "VALUES (2, 'Bad', 'BAD', 'BOND')"
                    )
                )
            connection.rollback()
            connection.execute(text(f"SET search_path TO {SCHEMA}"))

            connection.execute(
                text(
                    "INSERT INTO companies (id, name, ticker) "
                    "VALUES (3, 'C', 'CCC')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO companies (id, name, ticker) "
                    "VALUES (4, 'D', 'DDD')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO companies (id, name, ticker, isin) "
                    "VALUES (5, 'A', 'AAA', 'US0378331005')"
                )
            )
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO companies (id, name, ticker, isin) "
                        "VALUES (6, 'B', 'BBB', 'US0378331005')"
                    )
                )
            connection.rollback()
            connection.execute(text(f"SET search_path TO {SCHEMA}"))
            connection.execute(
                text(
                    "INSERT INTO companies (id, name, ticker, isin) "
                    "VALUES (5, 'A', 'AAA', 'US0378331005')"
                )
            )
            connection.commit()

            downgrade_base(connection)
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
            assert (
                connection.execute(
                    text("SELECT ticker FROM companies WHERE id = 1")
                ).scalar()
                == "AAPL"
            )
        finally:
            connection.rollback()
            connection.execute(text("SET search_path TO public"))
            connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
            connection.commit()


def test_model_and_migration_use_the_same_isin_uniqueness(postgres_engine):
    """The public create_all schema and revision 0001 agree on isin."""
    schema = "company_migration_match"
    with postgres_engine.connect() as public:
        public.execute(text("SET search_path TO public"))
        from_model = isin_uniqueness(public)
        ticker_from_model = ticker_uniqueness(public)
        upper_from_model = upper_ticker_index(public)

    with postgres_engine.connect() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        connection.execute(text(f"CREATE SCHEMA {schema}"))
        connection.execute(text(f"SET search_path TO {schema}"))
        connection.commit()
        try:
            connection.execute(text(LEGACY_COMPANIES))
            connection.execute(text(LEGACY_METRICS))
            connection.commit()
            upgrade_head(connection)
            from_migration = isin_uniqueness(connection)
            assert from_model == from_migration == EXPECTED_ISIN_UNIQUENESS
            assert ticker_uniqueness(connection) == ticker_from_model
            assert ticker_from_model == (
                (("ix_companies_ticker", False, ("ticker",)),),
                (),
            )
            assert upper_ticker_index(connection) == upper_from_model
            assert upper_from_model == (
                "uq_companies_ticker",
                True,
                ("upper(ticker::text)",),
            )
        finally:
            connection.rollback()
            connection.execute(text("SET search_path TO public"))
            connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            connection.commit()


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


def test_duplicate_tickers_stop_the_upgrade_on_postgresql(postgres_engine):
    schema = "company_duplicate_tickers"
    connection = _scratch(postgres_engine, schema)
    try:
        connection.execute(
            text(
                "CREATE TABLE companies ("
                "id integer PRIMARY KEY, "
                "name varchar(255) NOT NULL, "
                "ticker varchar(20) NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) VALUES "
                "(1, 'One', 'DUP'), (2, 'Two', 'DUP')"
            )
        )
        connection.commit()
        with pytest.raises(RuntimeError) as error:
            upgrade_head(connection)
        assert "'DUP' (2 rows)" in duplicate_ticker_message(error.value)
        connection.rollback()
        connection.execute(text(f"SET search_path TO {schema}"))
        indexes = {
            index["name"]
            for index in inspect(connection).get_indexes("companies")
        }
        assert "uq_companies_ticker" not in indexes
        rows = (
            connection.execute(
                text("SELECT ticker FROM companies ORDER BY id")
            )
            .scalars()
            .all()
        )
        assert rows == ["DUP", "DUP"]
    finally:
        _drop_scratch(connection, schema)


def test_case_and_space_collisions_stop_the_postgresql_upgrade(
    postgres_engine,
):
    """``aapl`` and ``AAPL `` are named, and neither row is rewritten."""
    schema = "company_ticker_case"
    connection = _scratch(postgres_engine, schema)
    try:
        connection.execute(
            text(
                "CREATE TABLE companies ("
                "id integer PRIMARY KEY, "
                "name varchar(255) NOT NULL, "
                "ticker varchar(20) NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) VALUES "
                "(1, 'Lower', 'aapl'), (2, 'Padded', 'AAPL ')"
            )
        )
        connection.commit()
        with pytest.raises(RuntimeError) as error:
            upgrade_head(connection)
        message = duplicate_ticker_message(error.value)
        assert "'aapl'" in message
        assert "'AAPL '" in message
        assert "did not change those rows" in message
        connection.rollback()
        connection.execute(text(f"SET search_path TO {schema}"))
        indexes = {
            index["name"]
            for index in inspect(connection).get_indexes("companies")
        }
        assert "uq_companies_ticker" not in indexes
        rows = (
            connection.execute(
                text("SELECT ticker FROM companies ORDER BY id")
            )
            .scalars()
            .all()
        )
        assert rows == ["aapl", "AAPL "]
    finally:
        _drop_scratch(connection, schema)


def test_tab_cr_and_lf_collisions_stop_the_postgresql_upgrade(
    postgres_engine,
):
    """A tab, CR, or LF beside the symbol is the same ticker."""
    schema = "company_ticker_whitespace"
    connection = _scratch(postgres_engine, schema)
    try:
        connection.execute(
            text(
                "CREATE TABLE companies ("
                "id integer PRIMARY KEY, "
                "name varchar(255) NOT NULL, "
                "ticker varchar(20) NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) VALUES "
                "(1, 'Tab', :tab), (2, 'Cr', :cr), (3, 'Lf', :lf)"
            ),
            {"tab": "AAPL\t", "cr": "aapl\r", "lf": "AAPL\n"},
        )
        connection.commit()
        with pytest.raises(RuntimeError) as error:
            upgrade_head(connection)
        message = duplicate_ticker_message(error.value)
        assert repr("AAPL\t") in message
        assert repr("aapl\r") in message
        assert repr("AAPL\n") in message
        assert "did not change those rows" in message
        connection.rollback()
        connection.execute(text(f"SET search_path TO {schema}"))
        indexes = {
            index["name"]
            for index in inspect(connection).get_indexes("companies")
        }
        assert "uq_companies_ticker" not in indexes
        rows = (
            connection.execute(
                text("SELECT ticker FROM companies ORDER BY id")
            )
            .scalars()
            .all()
        )
        assert rows == ["AAPL\t", "aapl\r", "AAPL\n"]
    finally:
        _drop_scratch(connection, schema)


def test_upgrade_downgrade_upgrade_on_postgresql(postgres_engine):
    schema = "company_round_trip"
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
        upgrade_head(connection)
        require_company_instrument_columns(connection)
        assert ticker_uniqueness(connection)[1] == ()
        downgrade_base(connection)
        upgrade_head(connection)
        require_company_instrument_columns(connection)
        stored = connection.execute(
            text("SELECT ticker, instrument_type FROM companies WHERE id = 1")
        ).one()
        assert stored.ticker == "AAPL"
        assert stored.instrument_type == "STOCK"
        assert upper_ticker_index(connection) == (
            "uq_companies_ticker",
            True,
            ("upper(ticker::text)",),
        )
        assert ticker_uniqueness(connection) == (
            (("ix_companies_ticker", False, ("ticker",)),),
            (),
        )
    finally:
        _drop_scratch(connection, schema)


def test_autogenerate_is_empty_after_replacing_the_old_index(postgres_engine):
    schema = "company_ticker_rename"
    connection = _scratch(postgres_engine, schema)
    try:
        Base.metadata.create_all(bind=connection)
        connection.commit()
        assert_empty_metadata_diff(connection)
        connection.execute(text("DROP INDEX uq_companies_ticker"))
        connection.execute(text("DROP INDEX ix_companies_ticker"))
        connection.execute(
            text(
                "CREATE UNIQUE INDEX ix_companies_ticker "
                "ON companies (ticker)"
            )
        )
        connection.commit()
        # create_all already built watchlist_items, notes, and
        # theses. Revisions 0004 and 0005 create those tables, so
        # the upgrade from 0002 needs them gone.
        connection.execute(text("DROP TABLE theses"))
        connection.execute(text("DROP TABLE notes"))
        connection.execute(text("DROP TABLE watchlist_items"))
        connection.commit()
        stamp(connection, "0002")
        upgrade_head(connection)
        require_company_instrument_columns(connection)
        assert_empty_metadata_diff(connection)
        assert ticker_uniqueness(connection) == (
            (("ix_companies_ticker", False, ("ticker",)),),
            (),
        )
        assert upper_ticker_index(connection) == (
            "uq_companies_ticker",
            True,
            ("upper(ticker::text)",),
        )
        downgrade_to(connection, "0002")
        assert ticker_uniqueness(connection) == (
            (("ix_companies_ticker", True, ("ticker",)),),
            (),
        )
    finally:
        _drop_scratch(connection, schema)
