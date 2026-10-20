"""Revision 0001 on a legacy SQLite file.

PostgreSQL is covered by
tests/integration/test_postgres_legacy_migration.py.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.database import create_db_engine
from tests.company_migration import (
    LEGACY_COMPANIES,
    LEGACY_METRICS,
    downgrade_base,
    upgrade_head,
)


def test_upgrade_sets_stock_and_downgrade_removes_the_columns(tmp_path):
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
        connection.execute(
            text(
                "INSERT INTO financial_metrics (id, company_id) "
                "VALUES (1, 1)"
            )
        )

    with engine.connect() as connection:
        upgrade_head(connection)
        stored = connection.execute(
            text("SELECT instrument_type, isin FROM companies WHERE id = 1")
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
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker, isin) "
                "VALUES (5, 'A', 'AAA', 'US0378331005')"
            )
        )
        connection.commit()

        downgrade_base(connection)
        columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(companies)"))
        }
        assert "instrument_type" not in columns
        assert "isin" not in columns
        assert (
            connection.execute(
                text("SELECT ticker FROM companies WHERE id = 1")
            ).scalar()
            == "AAPL"
        )
        assert (
            connection.execute(
                text("SELECT company_id FROM financial_metrics")
            ).scalar()
            == 1
        )

    engine.dispose()
