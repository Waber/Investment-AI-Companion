"""Revision 0002 adds price_bars on top of a legacy companies table.

The application engine is not used. SQLite is enough to see that
upgrade creates the table and downgrade removes it without dropping
the company row. PostgreSQL runs the same revision through the
legacy migration test, which upgrades to head.
"""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.database import create_db_engine
from tests.company_migration import (
    LEGACY_COMPANIES,
    LEGACY_METRICS,
    downgrade_base,
    upgrade_head,
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
