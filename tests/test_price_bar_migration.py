"""Revision 0002 adds price_bars on top of a legacy companies table.

Revision 0006 changes the OHLC columns from FLOAT to TEXT. The text
is the canonical 8-place price string. PostgreSQL uses NUMERIC(20, 8)
instead, in the integration suite.

The application engine is not used. SQLite is enough to see that
upgrade creates the table and the candle checks, and that downgrade
removes the table without dropping the company row.
"""

from decimal import Decimal

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.database import create_db_engine
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


def test_upgrade_creates_price_bars_and_downgrade_drops_them(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(text(LEGACY_COMPANIES))
        connection.execute(text(LEGACY_METRICS))
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) "
                "VALUES (1, 'Apple', 'AAPL')"
            )
        )

    with engine.connect() as connection:
        upgrade_head(connection)
        assert "price_bars" in inspect(connection).get_table_names()
        assert check_names(connection) == set(CANDLE_CHECK_NAMES)
        assert model_check_names(PriceBarDB) == set(CANDLE_CHECK_NAMES)
        connection.execute(
            text(
                "INSERT INTO price_bars ("
                "instrument_id, bar_date, currency, source, retrieved_at"
                ") VALUES (1, '2024-01-02', 'USD', 'fake', "
                "'2024-01-02 00:00:00')"
            )
        )
        connection.commit()
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO price_bars ("
                    "instrument_id, bar_date, currency, source, retrieved_at"
                    ") VALUES (1, '2024-01-02', 'USD', 'fake', "
                    "'2024-01-03 00:00:00')"
                )
            )
        connection.rollback()

        downgrade_base(connection)
        assert "price_bars" not in inspect(connection).get_table_names()
        assert (
            connection.execute(
                text("SELECT ticker FROM companies WHERE id = 1")
            ).scalar()
            == "AAPL"
        )
        engine.dispose()


# A float bar stored by revision 0002. 10.5 is exact in binary.
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


def test_revision_0006_stores_sqlite_prices_as_text(tmp_path):
    """A float stored at 0002 is the canonical string after 0006.

    Upgrade to 0006, downgrade to 0005, and upgrade again.
    0005 is the parent (notes and theses), so the downgrade undoes
    only this price revision and the column is FLOAT again. The
    second upgrade stores the 8-place string. ``companies`` is
    not rebuilt. The test stops at 0006 because revision 0007
    rebuilds ``companies`` on SQLite.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(text(LEGACY_COMPANIES))
        connection.execute(text(LEGACY_METRICS))
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) "
                "VALUES (1, 'Apple', 'AAPL')"
            )
        )
    with engine.connect() as connection:
        upgrade_to(connection, "0002")
        assert _column_types(connection)["open_price"].startswith("FLOAT")
        connection.execute(text(_FLOAT_BAR_SQL))
        connection.commit()
        companies_sql = connection.execute(
            text("SELECT sql FROM sqlite_master WHERE name = 'companies'")
        ).scalar()
        upgrade_to(connection, "0006")
        kinds = _column_types(connection)
        assert kinds["open_price"].startswith("TEXT")
        assert check_names(connection) == set(CANDLE_CHECK_NAMES)
        stored = connection.execute(
            text(
                "SELECT open_price, high_price, low_price, close_price "
                "FROM price_bars"
            )
        ).one()
        assert list(stored) == [
            "10.50000000",
            "11.00000000",
            "9.25000000",
            "10.75000000",
        ]
        assert (
            connection.execute(
                text("SELECT sql FROM sqlite_master WHERE name = 'companies'")
            ).scalar()
            == companies_sql
        )
        downgrade_to(connection, "0005")
        assert _column_types(connection)["open_price"].startswith("FLOAT")
        again = connection.execute(
            text("SELECT open_price FROM price_bars")
        ).scalar()
        assert Decimal(str(again)) == Decimal("10.5")
        upgrade_to(connection, "0006")
        restored = connection.execute(
            text("SELECT open_price FROM price_bars")
        ).scalar()
        assert restored == "10.50000000"
        assert _column_types(connection)["open_price"].startswith("TEXT")
    engine.dispose()


def test_migrated_sqlite_price_bars_match_the_model(tmp_path):
    """Revision 0002 and ``PriceBarDB`` describe the same table.

    An autogenerate against the upgraded table would not add
    ``ix_price_bars_id`` or ``ix_price_bars_instrument_id``, and it
    would not change the volume type or the cascade.
    """
    from app.core.database import Base

    upgraded = create_db_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with upgraded.begin() as connection:
        connection.execute(text(LEGACY_COMPANIES))
        connection.execute(text(LEGACY_METRICS))
    with upgraded.connect() as connection:
        upgrade_head(connection)
        from_migration = price_bar_structure(connection)
    upgraded.dispose()

    created = create_db_engine(f"sqlite:///{tmp_path / 'model.db'}")
    Base.metadata.create_all(bind=created)
    with created.connect() as connection:
        from_model = price_bar_structure(connection)
    created.dispose()

    assert from_migration == from_model
    kinds = {name: kind for name, kind, _nullable in from_model["columns"]}
    for name in ("open_price", "high_price", "low_price", "close_price"):
        assert kinds[name].startswith("TEXT")
    sql_by_name = dict(from_model["check_sql"])
    for name in CANDLE_CHECK_NAMES:
        if name == "ck_price_bars_volume_gte_zero":
            assert "CAST" not in sql_by_name[name]
        else:
            assert "CAST" in sql_by_name[name]
            assert "REAL" in sql_by_name[name]
    index_names = set(from_model["indexes"])
    assert "ix_price_bars_id" not in index_names
    assert "ix_price_bars_instrument_id" not in index_names
    ondelete = from_model["foreign_keys"][0][2]
    assert ondelete is not None
    assert ondelete.upper() == "CASCADE"


def test_sqlite_cascade_deletes_bars_with_the_company(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(text(LEGACY_COMPANIES))
        connection.execute(text(LEGACY_METRICS))
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) "
                "VALUES (1, 'Apple', 'AAPL')"
            )
        )
    with engine.connect() as connection:
        upgrade_head(connection)
        connection.execute(text(NULL_BAR_SQL))
        connection.commit()
        connection.execute(text("DELETE FROM companies WHERE id = 1"))
        connection.commit()
        remaining = connection.execute(
            text("SELECT COUNT(*) FROM price_bars")
        ).scalar()
        assert remaining == 0
        # The count opened a transaction. Downgrade copies
        # companies and refuses that.
        connection.commit()
        downgrade_base(connection)
        assert "price_bars" not in inspect(connection).get_table_names()
    engine.dispose()


@pytest.mark.parametrize(
    ("columns", "values", "constraint"),
    CANDLE_VIOLATIONS,
)
def test_upgraded_sqlite_rejects_each_candle_violation(
    tmp_path, columns, values, constraint
):
    """Each check fires on upgrade, and downgrade removes the table."""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(text(LEGACY_COMPANIES))
        connection.execute(text(LEGACY_METRICS))
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) "
                "VALUES (1, 'Apple', 'AAPL')"
            )
        )

    with engine.connect() as connection:
        upgrade_head(connection)
        with pytest.raises(IntegrityError) as caught:
            connection.execute(text(violation_sql(columns, values)))
        assert constraint in str(caught.value)
        connection.rollback()
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
    engine.dispose()


def _legacy_company(connection):
    connection.execute(text(LEGACY_COMPANIES))
    connection.execute(text(LEGACY_METRICS))
    connection.execute(
        text(
            "INSERT INTO companies (id, name, ticker) "
            "VALUES (1, 'Apple', 'AAPL')"
        )
    )


def test_oversized_legacy_prices_abort_the_sqlite_upgrade(tmp_path):
    """A price outside Numeric(20, 8) stops 0006 before any rewrite.

    SQLite would otherwise store 1e12 and 1e20 as text the API then
    skips, and ``1e20`` can become ``1.0e+20``, which ``quantize``
    cannot parse. ``sqlite3`` writes NaN as NULL, so this row set is
    1e12, 1e20, and infinity. The good bar is not in the message.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'oversized.db'}")
    with engine.begin() as connection:
        _legacy_company(connection)
    with engine.connect() as connection:
        upgrade_to(connection, "0005")
        connection.execute(
            text(
                "INSERT INTO price_bars ("
                "id, instrument_id, bar_date, open_price, high_price, "
                "low_price, close_price, volume, currency, source, "
                "retrieved_at) VALUES "
                "(1, 1, '2024-01-02', 10.5, 10.5, 10.5, 10.5, 1, "
                "'USD', 'ok', '2024-01-02 00:00:00'), "
                "(2, 1, '2024-01-03', 1000000000000, 1000000000000, "
                "1000000000000, 1000000000000, 1, 'USD', 'edge', "
                "'2024-01-03 00:00:00'), "
                "(3, 1, '2024-01-04', 1e20, 1e20, 1e20, 1e20, 1, "
                "'USD', 'huge', '2024-01-04 00:00:00'), "
                "(4, 1, '2024-01-05', 1e999, 1e999, 1e999, 1e999, 1, "
                "'USD', 'inf', '2024-01-05 00:00:00')"
            )
        )
        connection.commit()
        before = connection.execute(
            text("SELECT id, open_price FROM price_bars ORDER BY id")
        ).all()

    with pytest.raises(RuntimeError) as error:
        with engine.connect() as connection:
            upgrade_to(connection, "head")

    assert type(error.value).__name__ == "OversizedPricesError"
    message = str(error.value)
    assert message == (
        "price_bars ids 2, 3, 4 have a price outside Numeric(20, 8) "
        "or a price that is not finite. "
        "This upgrade did not change those rows."
    )
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
            == "0005"
        )
        kind = _column_types(connection)["open_price"]
        assert kind.startswith("FLOAT")
        after = connection.execute(
            text("SELECT id, open_price FROM price_bars ORDER BY id")
        ).all()
        assert after == before
    engine.dispose()


def test_sqlite_text_nan_aborts_the_upgrade(tmp_path):
    """The text ``NaN`` is a decimal that is not finite.

    ``Decimal('NaN').quantize`` does not raise, and comparing it
    with ``>=`` raises ``InvalidOperation``. The preflight has to
    report the id instead. ``Infinity`` text is the same class of
    stored value.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'nan.db'}")
    with engine.begin() as connection:
        _legacy_company(connection)
    with engine.connect() as connection:
        upgrade_to(connection, "0005")
        connection.execute(
            text(
                "INSERT INTO price_bars ("
                "id, instrument_id, bar_date, open_price, high_price, "
                "low_price, close_price, volume, currency, source, "
                "retrieved_at) VALUES "
                "(1, 1, '2024-05-01', 'NaN', 'NaN', 'NaN', 'NaN', 1, "
                "'USD', 'nan', '2024-05-01 00:00:00'), "
                "(2, 1, '2024-05-02', 'Infinity', 'Infinity', "
                "'Infinity', 'Infinity', 1, 'USD', 'inf', "
                "'2024-05-02 00:00:00')"
            )
        )
        connection.commit()
        before = connection.execute(
            text("SELECT id, open_price FROM price_bars ORDER BY id")
        ).all()

    with pytest.raises(RuntimeError) as error:
        with engine.connect() as connection:
            upgrade_to(connection, "head")

    assert type(error.value).__name__ == "OversizedPricesError"
    assert str(error.value) == (
        "price_bars ids 1, 2 have a price outside Numeric(20, 8) "
        "or a price that is not finite. "
        "This upgrade did not change those rows."
    )
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
            == "0005"
        )
        after = connection.execute(
            text("SELECT id, open_price FROM price_bars ORDER BY id")
        ).all()
        assert after == before
    engine.dispose()


# These floats are below 1e12. SQLite's REAL-to-text cast, then the
# same quantize the upgrade uses, turns each of them into 1e12.
_ROUNDS_TO_LIMIT = (
    "999999999999.9999",
    "999999999999.9998",
    "999999999999.9996",
    "999999999999.9995",
    "-999999999999.9999",
    "-999999999999.9998",
    "-999999999999.9996",
    "-999999999999.9995",
)


def _flat_float_rows(values, cast=""):
    """One flat bar per value. ``cast`` is ``::float8`` on PostgreSQL."""
    rows = []
    for index, value in enumerate(values, start=1):
        day = f"2024-03-{index:02d}"
        price = f"{value}{cast}"
        rows.append(
            f"({index}, 1, '{day}', {price}, {price}, {price}, {price}, "
            f"1, 'USD', 'near', '2024-03-{index:02d} 00:00:00')"
        )
    return (
        "INSERT INTO price_bars ("
        "id, instrument_id, bar_date, open_price, high_price, "
        "low_price, close_price, volume, currency, source, "
        "retrieved_at) VALUES " + ", ".join(rows)
    )


def test_floats_that_round_to_1e12_abort_the_sqlite_upgrade(tmp_path):
    """A raw float under 1e12 can still be 1e12 after the text cast.

    The preflight has to use that cast and the same quantize as the
    rewrite. Otherwise the stored text is ``1000000000000.00000000``
    and later reads skip the bar.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'rounded.db'}")
    with engine.begin() as connection:
        _legacy_company(connection)
    with engine.connect() as connection:
        upgrade_to(connection, "0005")
        connection.execute(text(_flat_float_rows(_ROUNDS_TO_LIMIT)))
        connection.commit()
        before = connection.execute(
            text("SELECT id, open_price FROM price_bars ORDER BY id")
        ).all()

    with pytest.raises(RuntimeError) as error:
        with engine.connect() as connection:
            upgrade_to(connection, "head")

    assert type(error.value).__name__ == "OversizedPricesError"
    assert str(error.value) == (
        "price_bars ids 1, 2, 3, 4, 5, 6, 7, 8 have a price outside "
        "Numeric(20, 8) or a price that is not finite. "
        "This upgrade did not change those rows."
    )
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
            == "0005"
        )
        assert _column_types(connection)["open_price"].startswith("FLOAT")
        after = connection.execute(
            text("SELECT id, open_price FROM price_bars ORDER BY id")
        ).all()
        assert after == before
    engine.dispose()


def test_sqlite_boundary_float_upgrades_below_1e12(tmp_path):
    """``999999999999.9994`` stays inside Numeric(20, 8).

    SQLite's text cast is ``999999999999.999``. Quantize writes
    ``999999999999.99900000``.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'boundary.db'}")
    with engine.begin() as connection:
        _legacy_company(connection)
    with engine.connect() as connection:
        upgrade_to(connection, "0005")
        connection.execute(text(_flat_float_rows(("999999999999.9994",))))
        connection.commit()
        upgrade_to(connection, "head")
        stored = connection.execute(
            text(
                "SELECT open_price, high_price, low_price, close_price "
                "FROM price_bars"
            )
        ).one()
        assert list(stored) == ["999999999999.99900000"] * 4
    engine.dispose()
