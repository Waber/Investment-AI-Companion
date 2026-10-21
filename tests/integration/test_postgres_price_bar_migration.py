"""Revision 0002 candle checks on PostgreSQL.

The public schema stays on create_all. This test uses its own schema
and drops it, including the Alembic version table.
"""

from decimal import Decimal

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.models.database_models import PriceBarDB
from tests.company_migration import (
    LEGACY_COMPANIES,
    LEGACY_METRICS,
    downgrade_base,
    downgrade_to,
    upgrade_head,
    upgrade_to,
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
            for name in (
                "open_price",
                "high_price",
                "low_price",
                "close_price",
            ):
                assert volume[name][0].startswith("NUMERIC")
                assert "20" in volume[name][0] and "8" in volume[name][0]
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


_FLOAT_BAR_SQL = (
    "INSERT INTO price_bars ("
    "instrument_id, bar_date, open_price, high_price, low_price, "
    "close_price, volume, currency, source, retrieved_at"
    ") VALUES (1, '2024-01-02', 10.5, 11.0, 9.25, 10.75, 100, "
    "'USD', 'fake', '2024-01-02 00:00:00+00')"
)


def _column_types(connection):
    return {
        column["name"]: str(column["type"]).upper()
        for column in inspect(connection).get_columns("price_bars")
    }


def test_revision_0006_changes_float_prices_to_numeric(postgres_engine):
    """A float stored at 0002 is numeric after 0006, on PostgreSQL.

    Downgrade stops at 0005, the parent revision. That undoes the
    price type change and leaves notes, theses, and the watchlist.
    """
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
            upgrade_to(connection, "0002")
            restored_before = _column_types(connection)["open_price"]
            assert "FLOAT" in restored_before or "DOUBLE" in restored_before
            connection.execute(text(_FLOAT_BAR_SQL))
            connection.commit()
            upgrade_to(connection, "head")
            kind = _column_types(connection)["open_price"]
            assert kind.startswith("NUMERIC")
            assert "20" in kind and "8" in kind
            stored = connection.execute(
                text(
                    "SELECT open_price, high_price, low_price, close_price "
                    "FROM price_bars"
                )
            ).one()
            assert [Decimal(str(value)) for value in stored] == [
                Decimal("10.5"),
                Decimal("11"),
                Decimal("9.25"),
                Decimal("10.75"),
            ]
            check_sql = dict(price_bar_structure(connection)["check_sql"])
            for name in CANDLE_CHECK_NAMES:
                assert "CAST" not in check_sql[name]
            downgrade_to(connection, "0005")
            restored = _column_types(connection)["open_price"]
            assert "NUMERIC" not in restored
            again = connection.execute(
                text("SELECT open_price FROM price_bars")
            ).scalar()
            assert Decimal(str(again)) == Decimal("10.5")
            upgrade_to(connection, "head")
            kind_again = _column_types(connection)["open_price"]
            assert kind_again.startswith("NUMERIC")
            round_trip = connection.execute(
                text("SELECT open_price FROM price_bars")
            ).scalar()
            assert Decimal(str(round_trip)) == Decimal("10.5")
        finally:
            _drop(connection)


def test_oversized_legacy_prices_abort_the_postgres_upgrade(postgres_engine):
    """1e12, 1e20, NaN, and infinity abort 0006 with the rows intact.

    PostgreSQL would otherwise raise ``numeric field overflow``
    while it alters the column. The message names the ids and the
    version stays ``0005``.
    """
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
            upgrade_to(connection, "0005")
            connection.execute(
                text(
                    "INSERT INTO price_bars ("
                    "id, instrument_id, bar_date, open_price, "
                    "high_price, low_price, close_price, volume, "
                    "currency, source, retrieved_at) VALUES "
                    "(1, 1, '2024-01-02', 10.5, 10.5, 10.5, 10.5, 1, "
                    "'USD', 'ok', '2024-01-02 00:00:00+00'), "
                    "(2, 1, '2024-01-03', 1000000000000, "
                    "1000000000000, 1000000000000, 1000000000000, 1, "
                    "'USD', 'edge', '2024-01-03 00:00:00+00'), "
                    "(3, 1, '2024-01-04', 1e20, 1e20, 1e20, 1e20, 1, "
                    "'USD', 'huge', '2024-01-04 00:00:00+00'), "
                    "(4, 1, '2024-01-05', 'Infinity'::float8, "
                    "'Infinity'::float8, 'Infinity'::float8, "
                    "'Infinity'::float8, 1, 'USD', 'inf', "
                    "'2024-01-05 00:00:00+00'), "
                    "(5, 1, '2024-01-06', 'NaN'::float8, 'NaN'::float8, "
                    "'NaN'::float8, 'NaN'::float8, 1, 'USD', 'nan', "
                    "'2024-01-06 00:00:00+00'), "
                    "(6, 1, '2024-01-07', '-Infinity'::float8, "
                    "'-Infinity'::float8, '-Infinity'::float8, "
                    "'-Infinity'::float8, 1, 'USD', 'neginf', "
                    "'2024-01-07 00:00:00+00')"
                )
            )
            connection.commit()
            before = connection.execute(
                text(
                    "SELECT id, open_price::text FROM price_bars "
                    "ORDER BY id"
                )
            ).all()
        except Exception:
            _drop(connection)
            raise

    with pytest.raises(RuntimeError) as error:
        with postgres_engine.connect() as connection:
            connection.execute(text(f"SET search_path TO {SCHEMA}"))
            connection.commit()
            upgrade_to(connection, "head")

    assert type(error.value).__name__ == "OversizedPricesError"
    assert str(error.value) == (
        "price_bars ids 2, 3, 4, 5, 6 have a price outside "
        "Numeric(20, 8) or a price that is not finite. "
        "This upgrade did not change those rows."
    )
    with postgres_engine.connect() as connection:
        connection.execute(text(f"SET search_path TO {SCHEMA}"))
        try:
            assert (
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar()
                == "0005"
            )
            kind = _column_types(connection)["open_price"]
            assert "NUMERIC" not in kind
            after = connection.execute(
                text(
                    "SELECT id, open_price::text FROM price_bars "
                    "ORDER BY id"
                )
            ).all()
            assert after == before
        finally:
            _drop(connection)


def test_floats_that_round_to_1e12_abort_the_postgres_upgrade(
    postgres_engine,
):
    """ROUND(float::numeric, 8) is what the ALTER stores.

    These four floats, and their negatives, are under 1e12 as raw
    floats and become 1e12 after that ROUND. The upgrade names the
    ids and leaves the float rows and revision ``0005`` in place.
    """
    from tests.test_price_bar_migration import (
        _ROUNDS_TO_LIMIT,
        _flat_float_rows,
    )

    sql = _flat_float_rows(_ROUNDS_TO_LIMIT, cast="::float8")
    sql = sql.replace("00:00:00')", "00:00:00+00')")
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
            upgrade_to(connection, "0005")
            connection.execute(text(sql))
            connection.commit()
            before = connection.execute(
                text(
                    "SELECT id, open_price::text FROM price_bars "
                    "ORDER BY id"
                )
            ).all()
        except Exception:
            _drop(connection)
            raise

    with pytest.raises(RuntimeError) as error:
        with postgres_engine.connect() as connection:
            connection.execute(text(f"SET search_path TO {SCHEMA}"))
            connection.commit()
            upgrade_to(connection, "head")

    assert type(error.value).__name__ == "OversizedPricesError"
    assert str(error.value) == (
        "price_bars ids 1, 2, 3, 4, 5, 6, 7, 8 have a price outside "
        "Numeric(20, 8) or a price that is not finite. "
        "This upgrade did not change those rows."
    )
    with postgres_engine.connect() as connection:
        connection.execute(text(f"SET search_path TO {SCHEMA}"))
        try:
            assert (
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar()
                == "0005"
            )
            assert "NUMERIC" not in _column_types(connection)["open_price"]
            after = connection.execute(
                text(
                    "SELECT id, open_price::text FROM price_bars "
                    "ORDER BY id"
                )
            ).all()
            assert after == before
        finally:
            _drop(connection)


def test_postgres_boundary_float_upgrades_below_1e12(postgres_engine):
    """``999999999999.9994`` rounds to ``999999999999.99900000``."""
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
            upgrade_to(connection, "0005")
            connection.execute(
                text(
                    "INSERT INTO price_bars ("
                    "id, instrument_id, bar_date, open_price, "
                    "high_price, low_price, close_price, volume, "
                    "currency, source, retrieved_at) VALUES ("
                    "1, 1, '2024-04-01', "
                    "999999999999.9994::float8, "
                    "999999999999.9994::float8, "
                    "999999999999.9994::float8, "
                    "999999999999.9994::float8, "
                    "1, 'USD', 'edge', '2024-04-01 00:00:00+00')"
                )
            )
            connection.commit()
            upgrade_to(connection, "head")
            stored = connection.execute(
                text(
                    "SELECT open_price::text, high_price::text, "
                    "low_price::text, close_price::text "
                    "FROM price_bars"
                )
            ).one()
            assert list(stored) == ["999999999999.99900000"] * 4
        finally:
            _drop(connection)
