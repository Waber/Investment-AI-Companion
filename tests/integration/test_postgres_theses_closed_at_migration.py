"""Revision 0008 on PostgreSQL, in a schema the other tests do not use.

The steps match ``tests/test_theses_closed_at_migration.py``.
PostgreSQL drops the column in place. This test drops its own
schema when it finishes, including the Alembic version table.
"""

from datetime import datetime, timezone

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
from tests.research_migration import research_schema

pytestmark = pytest.mark.integration

SCHEMA = "theses_closed_at"

# Two different last edits, so the backfill has to copy each row's
# own updated_at. The session time zone is Europe/Warsaw; aware
# datetimes compare as instants, so UTC literals still match.
_ACTIVE_EDIT = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
_CLOSED_EDIT = datetime(2025, 2, 3, 4, 5, 6, tzinfo=timezone.utc)


def _version(connection):
    return connection.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar()


def _column_names(connection, table):
    return [
        column["name"] for column in inspect(connection).get_columns(table)
    ]


def test_0008_backfills_closed_rows_and_downgrade_restores_0007(
    postgres_engine,
):
    """A closed row gets ``closed_at = updated_at``. Down restores 0007."""
    with postgres_engine.connect() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))
        connection.execute(text(f"SET search_path TO {SCHEMA}"))
        connection.commit()
        try:
            connection.execute(text(LEGACY_COMPANIES))
            connection.execute(text(LEGACY_METRICS))
            connection.commit()
            upgrade_to(connection, "0007")
            at_0007 = research_schema(connection)
            connection.execute(
                text(
                    "INSERT INTO companies (id, name, ticker) "
                    "VALUES (1, 'Acme', 'ACME')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO theses "
                    "(id, company_id, title, body, status, updated_at) "
                    "VALUES "
                    "(1, 1, 'Open', 'body', 'active', :active_edit), "
                    "(2, 1, 'Done', 'body', 'closed', :closed_edit)"
                ),
                {"active_edit": _ACTIVE_EDIT, "closed_edit": _CLOSED_EDIT},
            )
            connection.commit()

            upgrade_head(connection)
            rows = connection.execute(
                text(
                    "SELECT id, updated_at, closed_at FROM theses ORDER BY id"
                )
            ).all()
            assert rows == [
                (1, _ACTIVE_EDIT, None),
                (2, _CLOSED_EDIT, _CLOSED_EDIT),
            ]
            connection.commit()

            downgrade_to(connection, "0007")
            connection.commit()
            assert _version(connection) == "0007"
            assert "closed_at" not in _column_names(connection, "theses")
            assert research_schema(connection) == at_0007
            kept = connection.execute(
                text("SELECT id, status FROM theses ORDER BY id")
            ).all()
            assert kept == [(1, "active"), (2, "closed")]
            # An error aborts the whole PostgreSQL transaction. The
            # savepoint rolls back only the failed insert.
            with pytest.raises(IntegrityError, match="ck_theses_status"):
                with connection.begin_nested():
                    connection.execute(
                        text(
                            "INSERT INTO theses "
                            "(id, company_id, title, body, status) "
                            "VALUES (3, 1, 'Bad', 'body', 'bogus')"
                        )
                    )
            # The downgrade was committed, so that rollback did not
            # undo it.
            assert _version(connection) == "0007"
            connection.execute(text("DELETE FROM companies WHERE id = 1"))
            remaining = connection.execute(text("SELECT COUNT(*) FROM theses"))
            assert remaining.scalar() == 0
            connection.commit()

            upgrade_head(connection)
            connection.commit()
            assert _version(connection) == "0008"
            assert "closed_at" in _column_names(connection, "theses")
        finally:
            connection.rollback()
            connection.execute(text("SET search_path TO public"))
            connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
            connection.commit()
