"""Revision 0010 on PostgreSQL, in a schema the other tests do not use.

The steps match ``tests/test_fund_attributes_migration.py``.
PostgreSQL drops the table in place. This test drops its own schema
when it finishes, including the Alembic version table.
"""

import warnings

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError, SAWarning

from tests.company_migration import (
    LEGACY_COMPANIES,
    LEGACY_METRICS,
    downgrade_to,
    upgrade_head,
    upgrade_to,
)
from tests.test_fund_attributes_migration import (
    _FUND_COLUMNS,
    _fund_diff,
    _names,
    _truthy,
    _version,
)

pytestmark = pytest.mark.integration

SCHEMA = "fund_attributes_0010"


def test_0010_creates_nullable_attributes_and_downgrade_keeps_rows(
    postgres_engine,
):
    """Upgrade, defaults, downgrade, and upgrade again."""
    with postgres_engine.connect() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))
        connection.execute(text(f"SET search_path TO {SCHEMA}"))
        connection.commit()
        try:
            connection.execute(text(LEGACY_COMPANIES))
            connection.execute(text(LEGACY_METRICS))
            connection.commit()
            upgrade_to(connection, "0009")
            connection.commit()
            connection.execute(
                text(
                    "INSERT INTO companies "
                    "(id, name, ticker, instrument_type) "
                    "VALUES (1, 'Fund', 'FUND', 'ETF'), "
                    "(2, 'Share', 'SHR', 'STOCK')"
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
                    "INSERT INTO price_bars "
                    "(instrument_id, bar_date, currency, source, "
                    "retrieved_at) "
                    "VALUES (1, '2024-01-02', 'EUR', 'demo', "
                    "'2024-01-02 18:00:00+00')"
                )
            )
            connection.commit()

            upgrade_head(connection)
            connection.commit()
            assert _version(connection) == "0010"
            assert "fund_attributes" in inspect(connection).get_table_names()
            assert _names(connection, "fund_attributes") == _FUND_COLUMNS
            assert _fund_diff(connection) == []

            connection.execute(
                text(
                    "INSERT INTO fund_attributes "
                    "(company_id, issuer, as_of) "
                    "VALUES (1, 'Demo Issuer', '2026-09-30')"
                )
            )
            stored = connection.execute(
                text(
                    "SELECT issuer, ter, aum, is_synthetic, source "
                    "FROM fund_attributes WHERE company_id = 1"
                )
            ).one()
            assert stored[0] == "Demo Issuer"
            assert stored[1] is None
            assert stored[2] is None
            assert _truthy(stored[3]) is False
            assert stored[4] == "manual"

            connection.execute(
                text(
                    "INSERT INTO fund_attributes (company_id, ter, aum) "
                    "VALUES (2, 0, 0)"
                )
            )
            zeros = connection.execute(
                text(
                    "SELECT ter, aum FROM fund_attributes "
                    "WHERE company_id = 2"
                )
            ).one()
            assert float(zeros[0]) == 0.0
            assert float(zeros[1]) == 0.0
            connection.execute(
                text("DELETE FROM fund_attributes WHERE company_id = 2")
            )

            with pytest.raises(IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            "INSERT INTO fund_attributes (company_id, ter) "
                            "VALUES (2, -0.01)"
                        )
                    )
            with pytest.raises(IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            "INSERT INTO fund_attributes (company_id, aum) "
                            "VALUES (2, -1)"
                        )
                    )
            with pytest.raises(IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            "INSERT INTO fund_attributes (company_id, ter) "
                            "VALUES (2, -1)"
                        )
                    )
            assert _version(connection) == "0010"
            connection.commit()

            with warnings.catch_warnings():
                warnings.simplefilter("error", SAWarning)
                downgrade_to(connection, "0009")
            connection.commit()
            assert _version(connection) == "0009"
            names = inspect(connection).get_table_names()
            assert "fund_attributes" not in names
            company = connection.execute(
                text("SELECT id, ticker FROM companies WHERE id = 1")
            ).one()
            assert tuple(company) == (1, "FUND")
            metric = connection.execute(
                text("SELECT id, company_id FROM financial_metrics")
            ).one()
            assert tuple(metric) == (1, 1)
            bar = connection.execute(
                text("SELECT instrument_id, currency FROM price_bars")
            ).one()
            assert tuple(bar) == (1, "EUR")

            upgrade_head(connection)
            connection.commit()
            assert _version(connection) == "0010"
            count = connection.execute(
                text("SELECT COUNT(*) FROM fund_attributes")
            ).scalar()
            assert count == 0
        finally:
            connection.rollback()
            connection.execute(text("SET search_path TO public"))
            connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
            connection.commit()
