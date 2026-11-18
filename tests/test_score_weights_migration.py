"""Revision 0011 on SQLite: the weight-set table, then downgrade.

PostgreSQL runs the same steps in
``tests/integration/test_postgres_score_weights_migration.py``.

The upgrade does not insert a weight row. The built-in equal weights
stay in code until a PUT stores a set. Downgrade drops the table and
leaves companies, metrics, fund attributes, and price bars.
"""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.database import Base, create_db_engine
from tests.company_migration import (
    downgrade_to,
    metadata_diff,
    stamp,
    upgrade_head,
    upgrade_to,
)
from tests.test_fund_attributes_migration import _prepare

_COLUMNS = {
    "id",
    "instrument_type",
    "version",
    "weights",
    "created_at",
    "updated_at",
}


def _version(connection):
    return connection.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar()


def _names(connection):
    return {
        column["name"]
        for column in inspect(connection).get_columns("score_weights")
    }


def _score_diff(connection):
    return [
        operation
        for operation in metadata_diff(connection)
        if "score_weights" in repr(operation)
    ]


def test_alembic_head_is_0011_revising_0010():
    """One head. 0011 revises 0010. 0010 still revises 0009."""
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    assert script.get_heads() == ["0011"]
    revision = script.get_revision("0011")
    assert revision.down_revision == "0010"
    assert script.get_revision("0010").down_revision == "0009"


def test_0011_creates_an_empty_weight_table_and_downgrade_keeps_rows(
    tmp_path,
):
    """Upgrade, a rejected row, downgrade, and a second upgrade.

    A raw insert has to name the type, the version, and the weights.
    There is no server default that would invent a weight set. Version
    0 and an unknown instrument type are rejected. Downgrade drops the
    weight row with the table. The company, the metric, the attribute
    row, and the price bar stay. The next upgrade starts empty.
    """
    engine, connection = _prepare(tmp_path)
    try:
        upgrade_to(connection, "0010")
        connection.commit()
        connection.execute(
            text(
                "INSERT INTO fund_attributes (company_id, issuer, as_of) "
                "VALUES (1, 'Demo Issuer', '2026-09-30')"
            )
        )
        connection.commit()
        upgrade_head(connection)
        connection.commit()
        assert _version(connection) == "0011"
        assert "score_weights" in inspect(connection).get_table_names()
        assert _names(connection) == _COLUMNS
        assert _score_diff(connection) == []
        count = connection.execute(
            text("SELECT COUNT(*) FROM score_weights")
        ).scalar()
        assert count == 0

        connection.execute(
            text(
                "INSERT INTO score_weights "
                "(instrument_type, version, weights) "
                "VALUES ('STOCK', 2, '{\"profitability\": 1}')"
            )
        )
        stored = connection.execute(
            text(
                "SELECT instrument_type, version, weights "
                "FROM score_weights"
            )
        ).one()
        assert stored[0] == "STOCK"
        assert stored[1] == 2
        assert "profitability" in stored[2]

        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO score_weights "
                    "(instrument_type, version, weights) "
                    "VALUES ('BOND', 1, '{}')"
                )
            )
        connection.rollback()
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO score_weights "
                    "(instrument_type, version, weights) "
                    "VALUES ('ETF', 0, '{}')"
                )
            )
        connection.rollback()
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO score_weights (instrument_type, version) "
                    "VALUES ('ETF', 1)"
                )
            )
        connection.rollback()
        assert _version(connection) == "0011"

        connection.commit()
        downgrade_to(connection, "0010")
        connection.commit()
        assert _version(connection) == "0010"
        names = inspect(connection).get_table_names()
        assert "score_weights" not in names
        assert "fund_attributes" in names
        company = connection.execute(
            text("SELECT ticker FROM companies WHERE id = 1")
        ).scalar()
        assert company == "FUND"
        attributes = connection.execute(
            text("SELECT issuer FROM fund_attributes")
        ).scalar()
        assert attributes == "Demo Issuer"

        upgrade_head(connection)
        connection.commit()
        assert _version(connection) == "0011"
        again = connection.execute(
            text("SELECT COUNT(*) FROM score_weights")
        ).scalar()
        assert again == 0
    finally:
        connection.close()
        engine.dispose()


def test_0011_upgrade_is_safe_when_create_all_already_has_the_table(
    tmp_path,
):
    """A database built by ``create_all`` already has ``score_weights``.

    Stamping 0010 and upgrading must not try to create the table again.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'created.db'}")
    Base.metadata.create_all(bind=engine)
    with engine.connect() as connection:
        stamp(connection, "0010")
        connection.commit()
        upgrade_head(connection)
        connection.commit()
        assert _version(connection) == "0011"
        assert _score_diff(connection) == []
        assert "score_weights" in inspect(connection).get_table_names()
