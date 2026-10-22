"""Revision 0004 on SQLite: up, down, up, and an empty autogenerate."""

from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.database import Base, create_db_engine
from tests.company_migration import (
    upgrade_head,
    without_unreflectable_ticker_index,
)
from tests.watchlist_migration import (
    ROOT,
    _config,
    assert_autogenerate_is_empty,
    assert_rendered_revision_is_empty,
    downgrade_to,
    prepare_legacy,
    watchlist_diffs,
    watchlist_structure,
)


def test_alembic_has_a_single_head():
    """0007 is the only head. 0006 continues the notes revision."""
    script = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
    heads = script.get_heads()
    assert len(heads) == 1
    assert heads[0] == "0007"
    assert script.get_revision("0005").down_revision == "0004"
    assert script.get_revision("0006").down_revision == "0005"
    assert script.get_revision("0007").down_revision == "0006"


def test_upgrade_downgrade_upgrade_on_sqlite(tmp_path):
    """Head creates the table, 0003 drops it, and head creates it again.

    The company row and ``price_bars`` survive. Downgrade removes the
    watchlist rows with the table.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        prepare_legacy(connection)

    with engine.connect() as connection:
        upgrade_head(connection)
        assert "watchlist_items" in inspect(connection).get_table_names()
        connection.execute(
            text(
                "INSERT INTO watchlist_items (company_id, added_at, label) "
                "VALUES (1, '2024-01-02 00:00:00', 'core')"
            )
        )
        connection.commit()
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO watchlist_items (company_id, added_at) "
                    "VALUES (1, '2024-02-02 00:00:00')"
                )
            )
        connection.rollback()
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO watchlist_items (company_id, added_at) "
                    "VALUES (999, '2024-02-02 00:00:00')"
                )
            )
        connection.rollback()
        connection.execute(text("DELETE FROM companies WHERE id = 1"))
        connection.commit()
        remaining = connection.execute(
            text("SELECT COUNT(*) FROM watchlist_items")
        ).scalar()
        assert remaining == 0

        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker, instrument_type) "
                "VALUES (1, 'Apple', 'AAPL', 'STOCK')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO watchlist_items (company_id, added_at) "
                "VALUES (1, '2024-03-01 00:00:00')"
            )
        )
        connection.commit()

        downgrade_to(connection, "0003")
        assert "watchlist_items" not in inspect(connection).get_table_names()
        assert "price_bars" in inspect(connection).get_table_names()
        assert (
            connection.execute(
                text("SELECT ticker FROM companies WHERE id = 1")
            ).scalar()
            == "AAPL"
        )

        upgrade_head(connection)
        assert "watchlist_items" in inspect(connection).get_table_names()
        assert (
            connection.execute(
                text("SELECT COUNT(*) FROM watchlist_items")
            ).scalar()
            == 0
        )
        assert watchlist_diffs(connection) == []
    engine.dispose()


def test_migrated_sqlite_watchlist_matches_the_model(tmp_path):
    upgraded = create_db_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with upgraded.begin() as connection:
        prepare_legacy(connection)
    with upgraded.connect() as connection:
        upgrade_head(connection)
        from_migration = watchlist_structure(connection)
    upgraded.dispose()

    created = create_db_engine(f"sqlite:///{tmp_path / 'model.db'}")
    Base.metadata.create_all(bind=created)
    with created.connect() as connection:
        from_model = watchlist_structure(connection)
    created.dispose()

    assert from_migration == from_model
    ondelete = from_model["foreign_keys"][0][4]
    assert ondelete is not None
    assert ondelete.upper() == "CASCADE"
    assert "ix_watchlist_items_id" not in {
        index[0] for index in from_model["indexes"]
    }


def test_autogenerate_against_sqlite_watchlist_is_empty(tmp_path):
    """create_all, then let revision 0004 rebuild watchlist_items.

    Autogenerate against that database has nothing left to do. A
    rendered revision is only ``pass`` in upgrade and downgrade.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'full.db'}")
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        # create_all already built these. Revision 0004 recreates
        # the watchlist. Revision 0005 recreates notes and theses.
        connection.execute(text("DROP TABLE theses"))
        connection.execute(text("DROP TABLE notes"))
        connection.execute(text("DROP TABLE watchlist_items"))
    written = None
    try:
        with engine.connect() as connection:
            config = _config(connection)
            command.stamp(config, "0003")
            upgrade_head(connection)
            assert_autogenerate_is_empty(connection)
            with without_unreflectable_ticker_index():
                script = command.revision(
                    config,
                    message="empty check",
                    autogenerate=True,
                    rev_id="9997",
                )
            written = Path(script.path)
            source = written.read_text()
    finally:
        if written is not None and written.exists():
            written.unlink()
        engine.dispose()

    assert_rendered_revision_is_empty(source)
    assert not (ROOT / "alembic" / "versions" / "9997_empty_check.py").exists()
