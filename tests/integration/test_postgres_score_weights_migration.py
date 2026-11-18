"""Revision 0011 on PostgreSQL, in a schema the other tests do not use.

The steps match ``tests/test_score_weights_migration.py``. This test
drops its own schema when it finishes.
"""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from tests.company_migration import (
    LEGACY_COMPANIES,
    LEGACY_METRICS,
    downgrade_to,
    upgrade_head,
    upgrade_to,
)
from tests.test_score_weights_migration import _COLUMNS, _names, _score_diff

pytestmark = pytest.mark.integration

SCHEMA = "score_weights_0011"


def _version(connection):
    return connection.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar()


def test_0011_creates_an_empty_weight_table_and_downgrade_keeps_rows(
    postgres_engine,
):
    """Upgrade, a rejected row, downgrade, and a second upgrade."""
    with postgres_engine.connect() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))
        connection.execute(text(f"SET search_path TO {SCHEMA}"))
        connection.commit()
        try:
            connection.execute(text(LEGACY_COMPANIES))
            connection.execute(text(LEGACY_METRICS))
            connection.commit()
            upgrade_to(connection, "0010")
            connection.commit()
            connection.execute(
                text(
                    "INSERT INTO companies "
                    "(id, name, ticker, instrument_type) "
                    "VALUES (1, 'Fund', 'FUND', 'ETF')"
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
            connection.execute(
                text(
                    "INSERT INTO fund_attributes (company_id, issuer) "
                    "VALUES (1, 'Demo Issuer')"
                )
            )
            connection.commit()

            upgrade_head(connection)
            connection.commit()
            assert _version(connection) == "0011"
            assert "score_weights" in inspect(connection).get_table_names()
            assert _names(connection) == _COLUMNS
            assert _score_diff(connection) == []
            assert (
                connection.execute(
                    text("SELECT COUNT(*) FROM score_weights")
                ).scalar()
                == 0
            )
            connection.execute(
                text(
                    "INSERT INTO score_weights "
                    "(instrument_type, version, weights) "
                    "VALUES ('STOCK', 2, '{\"profitability\": 1}')"
                )
            )
            with pytest.raises(IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            "INSERT INTO score_weights "
                            "(instrument_type, version, weights) "
                            "VALUES ('BOND', 1, '{}')"
                        )
                    )
            with pytest.raises(IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            "INSERT INTO score_weights "
                            "(instrument_type, version, weights) "
                            "VALUES ('ETF', 0, '{}')"
                        )
                    )
            connection.commit()
            downgrade_to(connection, "0010")
            connection.commit()
            assert _version(connection) == "0010"
            names = inspect(connection).get_table_names()
            assert "score_weights" not in names
            assert "fund_attributes" in names
            assert (
                connection.execute(
                    text("SELECT issuer FROM fund_attributes")
                ).scalar()
                == "Demo Issuer"
            )
            upgrade_head(connection)
            connection.commit()
            assert _version(connection) == "0011"
            assert (
                connection.execute(
                    text("SELECT COUNT(*) FROM score_weights")
                ).scalar()
                == 0
            )
        finally:
            connection.rollback()
            connection.execute(text("SET search_path TO public"))
            connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
            connection.commit()
