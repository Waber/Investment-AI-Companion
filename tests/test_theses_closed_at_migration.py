"""Revision 0008 on SQLite: ``theses.closed_at`` up, down, and up.

PostgreSQL runs the same steps in
``tests/integration/test_postgres_theses_closed_at_migration.py``.

Alembic joins the caller's transaction when one is open. The test
commits before a revision command, so the command owns its
transaction, and after it, so a later rollback cannot undo it.

There is no empty-autogenerate check here. The legacy companies
table always differs from the model. The empty diff through 0008
is covered in ``tests/test_sqlite_notes_migration.py``.
"""

import warnings

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError, SAWarning

from app.core.database import create_db_engine
from tests.company_migration import (
    LEGACY_COMPANIES,
    LEGACY_METRICS,
    downgrade_to,
    upgrade_head,
    upgrade_to,
)
from tests.research_migration import research_schema

# Two different last edits, so the backfill has to copy each row's
# own updated_at. SQLite keeps the text exactly as it was inserted.
_ACTIVE_EDIT = "2024-01-02 03:04:05"
_CLOSED_EDIT = "2025-02-03 04:05:06"


def _version(connection):
    return connection.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar()


def _column_names(connection, table):
    return [
        column["name"] for column in inspect(connection).get_columns(table)
    ]


def test_0008_backfills_closed_rows_and_downgrade_restores_0007(tmp_path):
    """A closed row gets ``closed_at = updated_at``. Down restores 0007.

    SQLite copies ``theses`` to drop the column. The rows, the status
    CHECK, the foreign key with ON DELETE CASCADE, and the company
    index must all come back as they were at 0007.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'theses.db'}")
    with engine.begin() as connection:
        connection.execute(text(LEGACY_COMPANIES))
        connection.execute(text(LEGACY_METRICS))
    with engine.connect() as connection:
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
                "(id, company_id, title, body, status, updated_at) VALUES "
                "(1, 1, 'Open', 'body', 'active', :active_edit), "
                "(2, 1, 'Done', 'body', 'closed', :closed_edit)"
            ),
            {"active_edit": _ACTIVE_EDIT, "closed_edit": _CLOSED_EDIT},
        )
        connection.commit()

        upgrade_head(connection)
        rows = connection.execute(
            text("SELECT id, updated_at, closed_at FROM theses ORDER BY id")
        ).all()
        assert rows == [
            (1, _ACTIVE_EDIT, None),
            (2, _CLOSED_EDIT, _CLOSED_EDIT),
        ]
        connection.commit()

        with warnings.catch_warnings():
            # The copy reflects theses only. Following its foreign key
            # would reflect companies too, and SQLite warns that it
            # cannot read the upper(ticker) index there.
            warnings.simplefilter("error", SAWarning)
            downgrade_to(connection, "0007")
        connection.commit()
        assert _version(connection) == "0007"
        assert "closed_at" not in _column_names(connection, "theses")
        assert research_schema(connection) == at_0007
        kept = connection.execute(
            text("SELECT id, status FROM theses ORDER BY id")
        ).all()
        assert kept == [(1, "active"), (2, "closed")]
        with pytest.raises(IntegrityError, match="ck_theses_status"):
            connection.execute(
                text(
                    "INSERT INTO theses (id, company_id, title, body, status) "
                    "VALUES (3, 1, 'Bad', 'body', 'bogus')"
                )
            )
        connection.rollback()
        # The downgrade was committed, so that rollback did not undo it.
        assert _version(connection) == "0007"
        connection.execute(text("DELETE FROM companies WHERE id = 1"))
        remaining = connection.execute(text("SELECT COUNT(*) FROM theses"))
        assert remaining.scalar() == 0
        connection.commit()

        upgrade_head(connection)
        connection.commit()
        assert _version(connection) == "0008"
        assert "closed_at" in _column_names(connection, "theses")
    engine.dispose()
