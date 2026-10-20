"""Revision 0001 on PostgreSQL, in a schema the other tests do not use.

The public schema stays on create_all. This test drops its own schema
when it finishes, including the Alembic version table.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.company_migration import (
    LEGACY_COMPANIES,
    LEGACY_METRICS,
    downgrade_base,
    upgrade_head,
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
