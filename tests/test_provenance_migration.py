"""Revision 0009 on SQLite: provenance columns, backfill, downgrade.

PostgreSQL runs the same steps in
``tests/integration/test_postgres_provenance_migration.py``.

Alembic joins the caller's transaction when one is open. The test
commits before a revision command, so the command owns its
transaction, and after it, so a later rollback cannot undo it.
"""

import warnings

from sqlalchemy import inspect, text
from sqlalchemy.exc import SAWarning

from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.database import Base, create_db_engine
from tests.company_migration import (
    LEGACY_COMPANIES,
    LEGACY_METRICS,
    downgrade_to,
    stamp,
    upgrade_head,
    upgrade_to,
)

# Descriptions the backfill must tell apart. The prefix is exact and
# case-sensitive. A leading space is not the prefix.
_ROWS = (
    (1, "Demo One", "DEMO1", "[IAC-DEMO-V1] seeded"),
    (2, "Demo Two", "DEMO2", "[IAC-DEMO-V2] seeded"),
    (3, "Ordinary", "ORD1", "Ordinary notes"),
    (4, "Blank", "NULL1", None),
    (5, "Padded", "PAD1", " [IAC-DEMO-V1] seeded"),
    (6, "Lower", "LOW1", "[iac-demo-v1] seeded"),
    (7, "Exact", "EXACT", "[IAC-DEMO-"),
)


def _version(connection):
    return connection.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar()


def _names(connection, table):
    return {
        column["name"] for column in inspect(connection).get_columns(table)
    }


def _insert_companies(connection):
    for company_id, name, ticker, description in _ROWS:
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker, description) "
                "VALUES (:id, :name, :ticker, :description)"
            ),
            {
                "id": company_id,
                "name": name,
                "ticker": ticker,
                "description": description,
            },
        )


def _insert_metrics(connection):
    """One metric on a demo parent and one on an ordinary parent.

    The legacy stub at 0008 has ``id`` and ``company_id`` only.
    ``description`` is added in the test. A database built with
    ``create_all`` already has both.
    """
    connection.execute(
        text(
            "INSERT INTO financial_metrics (id, company_id) VALUES "
            "(1, 1), (2, 3), (3, 2)"
        )
    )


def _provenance(connection):
    rows = connection.execute(
        text("SELECT id, is_synthetic, source FROM companies ORDER BY id")
    ).all()
    return [(row[0], _truthy(row[1]), row[2]) for row in rows]


def _metric_sources(connection):
    return connection.execute(
        text(
            "SELECT id, company_id, source FROM financial_metrics "
            "ORDER BY id"
        )
    ).all()


def _truthy(value):
    return value in (True, 1)


def test_alembic_head_is_0009_revising_0008():
    """One head. 0009 revises 0008. 0008 still revises 0007."""
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    assert script.get_heads() == ["0009"]
    revision = script.get_revision("0009")
    assert revision.down_revision == "0008"
    assert script.get_revision("0008").down_revision == "0007"


def test_0009_backfills_demo_rows_and_downgrade_keeps_children(tmp_path):
    """Prefix rows become synthetic demo. A metric follows its parent.

    Downgrade drops the new columns and leaves the company row, the
    metric row, and the description. Upgrade again applies the same
    backfill. A raw insert that omits the columns gets the server
    defaults. A raw ``source`` outside the Python set is stored,
    because this revision adds no CHECK.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'provenance.db'}")
    with engine.begin() as connection:
        connection.execute(text(LEGACY_COMPANIES))
        connection.execute(text(LEGACY_METRICS))
    with engine.connect() as connection:
        upgrade_to(connection, "0008")
        connection.commit()
        # The legacy fixture omits description. Real databases have it.
        # The backfill reads that column, so the test adds it first.
        connection.execute(
            text("ALTER TABLE companies ADD COLUMN description TEXT")
        )
        _insert_companies(connection)
        _insert_metrics(connection)
        connection.commit()

        upgrade_head(connection)
        connection.commit()
        assert _version(connection) == "0009"
        assert {"is_synthetic", "source"} <= _names(connection, "companies")
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
        assert kept == [
            (1, "[IAC-DEMO-V1] seeded"),
            (3, "Ordinary notes"),
        ]
        metrics = connection.execute(
            text("SELECT id, company_id FROM financial_metrics ORDER BY id")
        ).all()
        assert metrics == [(1, 1), (2, 3), (3, 2)]

        upgrade_head(connection)
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
    engine.dispose()


def test_0009_upgrade_of_the_legacy_stub_does_not_require_description(
    tmp_path,
):
    """The legacy companies stub has no description column.

    Revision 0009 still upgrades that database. There is nothing to
    backfill, and a new row gets the server defaults.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'stub.db'}")
    with engine.begin() as connection:
        connection.execute(text(LEGACY_COMPANIES))
        connection.execute(text(LEGACY_METRICS))
    with engine.connect() as connection:
        upgrade_head(connection)
        connection.commit()
        assert _version(connection) == "0009"
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) "
                "VALUES (1, 'Stub', 'STUB')"
            )
        )
        row = connection.execute(
            text("SELECT is_synthetic, source FROM companies WHERE id = 1")
        ).one()
        assert _truthy(row[0]) is False
        assert row[1] == "manual"
        connection.rollback()
    engine.dispose()


def test_0009_upgrade_is_safe_when_create_all_already_has_the_columns(
    tmp_path,
):
    """A current create_all database stamped at 0008 can still upgrade.

    The legacy suite stamps that shape and then runs ``upgrade head``.
    Adding the column again would fail. The backfill still marks a
    description that starts with the demo prefix.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'created.db'}")
    Base.metadata.create_all(bind=engine)
    with engine.connect() as connection:
        stamp(connection, "0008")
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker, description) "
                "VALUES (1, 'Demo', 'CRALL', '[IAC-DEMO-V1] already')"
            )
        )
        connection.commit()
        upgrade_head(connection)
        connection.commit()
        row = connection.execute(
            text("SELECT is_synthetic, source FROM companies WHERE id = 1")
        ).one()
        assert _truthy(row[0]) is True
        assert row[1] == "demo"
        assert _version(connection) == "0009"
    engine.dispose()
