"""Revision 0010 on SQLite: fund attributes, defaults, downgrade.

PostgreSQL runs the same steps in
``tests/integration/test_postgres_fund_attributes_migration.py``.

There is nothing to copy from an older description. ETF and ETC
facts did not exist before this revision, so the upgrade creates
an empty table. A missing TER stays null. It is not filled with 0.
Downgrade drops that table and leaves companies, metrics, and
price bars in place.
"""

import warnings

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError, SAWarning

from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.database import Base, create_db_engine
from tests.company_migration import (
    LEGACY_COMPANIES,
    LEGACY_METRICS,
    downgrade_to,
    metadata_diff,
    stamp,
    upgrade_head,
    upgrade_to,
)

_FUND_COLUMNS = {
    "id",
    "company_id",
    "issuer",
    "underlying",
    "ter",
    "domicile",
    "replication_method",
    "distribution_policy",
    "aum",
    "aum_currency",
    "aum_as_of",
    "as_of",
    "is_synthetic",
    "source",
    "created_at",
    "updated_at",
}


def _version(connection):
    return connection.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar()


def _names(connection, table):
    return {
        column["name"] for column in inspect(connection).get_columns(table)
    }


def _truthy(value):
    return value in (True, 1)


def _fund_diff(connection):
    """Autogenerate operations that still mention ``fund_attributes``.

    A legacy stub is missing columns the model has on ``companies``.
    Those operations are not this revision. An empty list means the
    new table matches the model.
    """
    return [
        operation
        for operation in metadata_diff(connection)
        if "fund_attributes" in repr(operation)
    ]


def _prepare(tmp_path):
    """A database at 0009 with one company, one metric, and one bar."""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'funds.db'}")
    with engine.begin() as connection:
        connection.execute(text(LEGACY_COMPANIES))
        connection.execute(text(LEGACY_METRICS))
    connection = engine.connect()
    upgrade_to(connection, "0009")
    connection.commit()
    connection.execute(
        text(
            "INSERT INTO companies (id, name, ticker, instrument_type) "
            "VALUES (1, 'Fund', 'FUND', 'ETF'), (2, 'Share', 'SHR', 'STOCK')"
        )
    )
    connection.execute(
        text("INSERT INTO financial_metrics (id, company_id) VALUES (1, 1)")
    )
    connection.execute(
        text(
            "INSERT INTO price_bars "
            "(instrument_id, bar_date, currency, source, retrieved_at) "
            "VALUES (1, '2024-01-02', 'EUR', 'demo', '2024-01-02 18:00:00')"
        )
    )
    connection.commit()
    return engine, connection


def test_alembic_head_is_0010_revising_0009():
    """One head. 0010 revises 0009. 0009 still revises 0008."""
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    assert script.get_heads() == ["0010"]
    revision = script.get_revision("0010")
    assert revision.down_revision == "0009"
    assert script.get_revision("0009").down_revision == "0008"


def test_0010_creates_nullable_attributes_and_downgrade_keeps_rows(tmp_path):
    """Upgrade, defaults, a rejected negative TER, downgrade, upgrade.

    The attribute row does not exist at 0009, so downgrade drops it
    with the table. The company, the metric, and the price bar stay.
    A second upgrade starts from an empty table again. A raw insert
    that omits provenance gets ``manual`` and synthetic false. A raw
    ``source`` outside the Python allow-list is stored: this revision
    adds no CHECK on source. TER and AUM have no server default, so
    omitting them stores null rather than zero.
    """
    engine, connection = _prepare(tmp_path)
    try:
        upgrade_head(connection)
        connection.commit()
        assert _version(connection) == "0010"
        assert "fund_attributes" in inspect(connection).get_table_names()
        assert _names(connection, "fund_attributes") == _FUND_COLUMNS
        assert _fund_diff(connection) == []

        connection.execute(
            text(
                "INSERT INTO fund_attributes (company_id, issuer, as_of) "
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
            text("SELECT ter, aum FROM fund_attributes WHERE company_id = 2")
        ).one()
        assert float(zeros[0]) == 0.0
        assert float(zeros[1]) == 0.0
        connection.execute(
            text("DELETE FROM fund_attributes WHERE company_id = 2")
        )

        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO fund_attributes (company_id, ter) "
                    "VALUES (2, -0.01)"
                )
            )
        connection.rollback()
        # The downgrade must not be undone by that rollback. The
        # insert above was not committed.
        assert _version(connection) == "0010"
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO fund_attributes (company_id, aum) "
                    "VALUES (2, -1)"
                )
            )
        connection.rollback()
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO fund_attributes (company_id, ter) "
                    "VALUES (2, -1)"
                )
            )
        connection.rollback()
        connection.execute(
            text(
                "INSERT INTO fund_attributes "
                "(company_id, source, is_synthetic) "
                "VALUES (2, 'yahoo', 1)"
            )
        )
        yahoo = connection.execute(
            text(
                "SELECT source, is_synthetic FROM fund_attributes "
                "WHERE company_id = 2"
            )
        ).one()
        assert yahoo[0] == "yahoo"
        assert _truthy(yahoo[1]) is True
        connection.commit()

        with warnings.catch_warnings():
            warnings.simplefilter("error", SAWarning)
            downgrade_to(connection, "0009")
        connection.commit()
        assert _version(connection) == "0009"
        assert "fund_attributes" not in inspect(connection).get_table_names()
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
        connection.execute(
            text("INSERT INTO fund_attributes (company_id) VALUES (1)")
        )
        defaults = connection.execute(
            text(
                "SELECT ter, aum, is_synthetic, source, as_of "
                "FROM fund_attributes WHERE company_id = 1"
            )
        ).one()
        assert defaults[0] is None
        assert defaults[1] is None
        assert _truthy(defaults[2]) is False
        assert defaults[3] == "manual"
        assert defaults[4] is None
    finally:
        connection.close()
        engine.dispose()


def test_0010_upgrade_is_safe_when_create_all_already_has_the_table(
    tmp_path,
):
    """A create_all database stamped at 0009 can still upgrade.

    The table is already there. Creating it again would fail.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'created.db'}")
    Base.metadata.create_all(bind=engine)
    with engine.connect() as connection:
        stamp(connection, "0009")
        connection.commit()
        upgrade_head(connection)
        connection.commit()
        assert _version(connection) == "0010"
        assert "fund_attributes" in inspect(connection).get_table_names()
        assert metadata_diff(connection) == []
    engine.dispose()
