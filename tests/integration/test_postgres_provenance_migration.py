"""Revision 0009 on PostgreSQL, in a schema the other tests do not use.

The steps match ``tests/test_provenance_migration.py``. PostgreSQL
drops the columns in place. This test drops its own schema when it
finishes, including the Alembic version table.
"""

import warnings

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SAWarning

from tests.company_migration import (
    LEGACY_COMPANIES,
    LEGACY_METRICS,
    downgrade_to,
    upgrade_to,
)
from tests.test_provenance_migration import (
    _insert_companies,
    _insert_metrics,
    _metric_sources,
    _names,
    _provenance,
    _truthy,
    _version,
)

pytestmark = pytest.mark.integration

SCHEMA = "provenance_0009"


def test_0009_backfills_demo_rows_and_downgrade_keeps_children(
    postgres_engine,
):
    """Prefix rows become synthetic demo. Downgrade keeps the children."""
    with postgres_engine.connect() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))
        connection.execute(text(f"SET search_path TO {SCHEMA}"))
        connection.commit()
        try:
            connection.execute(text(LEGACY_COMPANIES))
            connection.execute(text(LEGACY_METRICS))
            connection.commit()
            upgrade_to(connection, "0008")
            connection.commit()
            connection.execute(
                text("ALTER TABLE companies ADD COLUMN description TEXT")
            )
            _insert_companies(connection)
            _insert_metrics(connection)
            connection.commit()

            upgrade_to(connection, "0009")
            connection.commit()
            assert _version(connection) == "0009"
            assert {"is_synthetic", "source"} <= _names(
                connection, "companies"
            )
            assert "source" in _names(connection, "financial_metrics")
            assert _provenance(connection) == [
                (1, True, "demo"),
                (2, True, "demo"),
                (3, False, "manual"),
                (4, False, "manual"),
                (5, False, "manual"),
                (6, False, "manual"),
                (7, True, "demo"),
            ]
            assert _metric_sources(connection) == [
                (1, 1, "demo"),
                (2, 3, "manual"),
                (3, 2, "demo"),
            ]

            connection.execute(
                text(
                    "INSERT INTO companies (id, name, ticker) "
                    "VALUES (8, 'Default', 'DEF1')"
                )
            )
            stored = connection.execute(
                text("SELECT is_synthetic, source FROM companies WHERE id = 8")
            ).one()
            assert _truthy(stored[0]) is False
            assert stored[1] == "manual"
            connection.execute(
                text(
                    "INSERT INTO companies (id, name, ticker, source) "
                    "VALUES (9, 'Later', 'YAH1', 'yahoo')"
                )
            )
            yahoo = connection.execute(
                text("SELECT source FROM companies WHERE id = 9")
            ).scalar()
            assert yahoo == "yahoo"
            connection.commit()

            with warnings.catch_warnings():
                warnings.simplefilter("error", SAWarning)
                downgrade_to(connection, "0008")
            connection.commit()
            assert _version(connection) == "0008"
            assert "is_synthetic" not in _names(connection, "companies")
            assert "source" not in _names(connection, "companies")
            assert "source" not in _names(connection, "financial_metrics")
            kept = connection.execute(
                text(
                    "SELECT id, description FROM companies "
                    "WHERE id IN (1, 3) ORDER BY id"
                )
            ).all()
            assert list(kept) == [
                (1, "[IAC-DEMO-V1] seeded"),
                (3, "Ordinary notes"),
            ]
            metrics = connection.execute(
                text(
                    "SELECT id, company_id FROM financial_metrics ORDER BY id"
                )
            ).all()
            assert list(metrics) == [(1, 1), (2, 3), (3, 2)]

            upgrade_to(connection, "0009")
            connection.commit()
            assert _version(connection) == "0009"
            again = connection.execute(
                text(
                    "SELECT id, is_synthetic, source FROM companies "
                    "WHERE id IN (1, 3, 8) ORDER BY id"
                )
            ).all()
            assert [(row[0], _truthy(row[1]), row[2]) for row in again] == [
                (1, True, "demo"),
                (3, False, "manual"),
                (8, False, "manual"),
            ]
        finally:
            connection.rollback()
            connection.execute(text("SET search_path TO public"))
            connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
            connection.commit()
