"""Revision 0002 adds price_bars on top of a legacy companies table.

The application engine is not used. SQLite is enough to see that
upgrade creates the table and the candle checks, and that downgrade
removes the table without dropping the company row. PostgreSQL runs
the same checks in the integration suite.
"""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.database import create_db_engine
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
