"""Revision 0001 on a legacy SQLite file.

PostgreSQL is covered by
tests/integration/test_postgres_legacy_migration.py.
"""

import pytest
from sqlalchemy import Index, text
from sqlalchemy.exc import IntegrityError

from app.core.database import Base, create_db_engine
from app.core.init_db import require_company_instrument_columns
from app.models.database_models import CompanyDB
from scripts.check_duplicate_tickers import DuplicateTickersError
from tests.company_migration import (
    EXPECTED_ISIN_UNIQUENESS,
    LEGACY_COMPANIES,
    LEGACY_METRICS,
    downgrade_base,
    downgrade_to,
    isin_uniqueness,
    metadata_diff,
    stamp,
    ticker_uniqueness,
    upgrade_head,
    upgrade_to,
)


def test_upgrade_sets_stock_and_downgrade_removes_the_columns(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
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

    with engine.connect() as connection:
        upgrade_head(connection)
        require_company_instrument_columns(connection)
        stored = connection.execute(
            text("SELECT instrument_type, isin FROM companies WHERE id = 1")
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
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker, isin) "
                "VALUES (5, 'A', 'AAA', 'US0378331005')"
            )
        )
        connection.commit()

        downgrade_base(connection)
        columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(companies)"))
        }
        assert "instrument_type" not in columns
        assert "isin" not in columns
        assert (
            connection.execute(
                text("SELECT ticker FROM companies WHERE id = 1")
            ).scalar()
            == "AAPL"
        )
        assert (
            connection.execute(
                text("SELECT company_id FROM financial_metrics")
            ).scalar()
            == 1
        )

    engine.dispose()


def test_model_and_migration_use_the_same_isin_uniqueness(tmp_path):
    """create_all and revision 0001 both use one unique index on isin."""
    indexes = [
        index
        for index in CompanyDB.__table__.indexes
        if index.name == "uq_companies_isin"
    ]
    assert len(indexes) == 1
    assert isinstance(indexes[0], Index)
    assert indexes[0].unique is True
    assert [column.name for column in indexes[0].columns] == ["isin"]

    model_engine = create_db_engine(f"sqlite:///{tmp_path / 'model.db'}")
    Base.metadata.create_all(model_engine)
    with model_engine.connect() as connection:
        from_model = isin_uniqueness(connection)
    model_engine.dispose()

    legacy_engine = create_db_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with legacy_engine.begin() as connection:
        connection.execute(text(LEGACY_COMPANIES))
        connection.execute(text(LEGACY_METRICS))
    with legacy_engine.connect() as connection:
        upgrade_head(connection)
        from_migration = isin_uniqueness(connection)
    legacy_engine.dispose()

    assert from_model == from_migration == EXPECTED_ISIN_UNIQUENESS


def test_duplicate_tickers_stop_the_upgrade_without_a_unique_index(tmp_path):
    """Two rows with ticker DUP are named, and the index is not created."""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'dups.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE companies ("
                "id INTEGER PRIMARY KEY, "
                "name VARCHAR(255) NOT NULL, "
                "ticker VARCHAR(20) NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) VALUES "
                "(1, 'One', 'DUP'), (2, 'Two', 'DUP')"
            )
        )

    with pytest.raises(DuplicateTickersError) as error:
        with engine.connect() as connection:
            upgrade_head(connection)

    message = str(error.value)
    assert "'DUP' (2 rows)" in message
    assert "did not change those rows" in message
    with engine.connect() as connection:
        indexes = {index["name"] for index in inspect_indexes(connection)}
        assert "uq_companies_ticker" not in indexes
        rows = (
            connection.execute(
                text("SELECT ticker FROM companies ORDER BY id")
            )
            .scalars()
            .all()
        )
        assert rows == ["DUP", "DUP"]
    engine.dispose()


def test_case_and_space_collisions_stop_the_sqlite_upgrade(tmp_path):
    """``aapl`` and ``AAPL `` are named, and neither row is rewritten."""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'case.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE companies ("
                "id INTEGER PRIMARY KEY, "
                "name VARCHAR(255) NOT NULL, "
                "ticker VARCHAR(20) NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) VALUES "
                "(1, 'Lower', 'aapl'), (2, 'Padded', 'AAPL ')"
            )
        )

    with pytest.raises(DuplicateTickersError) as error:
        with engine.connect() as connection:
            upgrade_head(connection)

    message = str(error.value)
    assert "'aapl'" in message
    assert "'AAPL '" in message
    assert "did not change those rows" in message
    with engine.connect() as connection:
        indexes = {index["name"] for index in inspect_indexes(connection)}
        assert "uq_companies_ticker" not in indexes
        rows = (
            connection.execute(
                text("SELECT ticker FROM companies ORDER BY id")
            )
            .scalars()
            .all()
        )
        assert rows == ["aapl", "AAPL "]
    engine.dispose()


def test_tab_cr_and_lf_collisions_stop_the_sqlite_upgrade(tmp_path):
    """A tab, CR, or LF beside the symbol is the same ticker."""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'ws.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE companies ("
                "id INTEGER PRIMARY KEY, "
                "name VARCHAR(255) NOT NULL, "
                "ticker VARCHAR(20) NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) VALUES "
                "(1, 'Tab', :tab), (2, 'Cr', :cr), (3, 'Lf', :lf)"
            ),
            {"tab": "AAPL\t", "cr": "aapl\r", "lf": "AAPL\n"},
        )

    with pytest.raises(DuplicateTickersError) as error:
        with engine.connect() as connection:
            upgrade_head(connection)

    message = str(error.value)
    assert repr("AAPL\t") in message
    assert repr("aapl\r") in message
    assert repr("AAPL\n") in message
    assert "did not change those rows" in message
    with engine.connect() as connection:
        indexes = {index["name"] for index in inspect_indexes(connection)}
        assert "uq_companies_ticker" not in indexes
        rows = (
            connection.execute(
                text("SELECT ticker FROM companies ORDER BY id")
            )
            .scalars()
            .all()
        )
        assert rows == ["AAPL\t", "aapl\r", "AAPL\n"]
    engine.dispose()


def inspect_indexes(connection):
    from sqlalchemy import inspect

    return inspect(connection).get_indexes("companies")


def test_named_ticker_index_matches_the_model_and_round_trips(tmp_path):
    """create_all's old ix_companies_ticker becomes uq_companies_ticker.

    After upgrade, autogenerate has nothing to do. Downgrade restores
    the old index name. Upgrade again matches the model.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'named.db'}")
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        assert metadata_diff(connection) == []
        assert ticker_uniqueness(connection) == (
            (("uq_companies_ticker", True, ("ticker",)),),
            (),
        )
    with engine.begin() as connection:
        connection.execute(text("DROP INDEX uq_companies_ticker"))
        connection.execute(
            text(
                "CREATE UNIQUE INDEX ix_companies_ticker "
                "ON companies (ticker)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO companies (name, ticker) VALUES "
                "('Berkshire Hathaway', 'BRK.A'), "
                "('Berkshire Hathaway', 'BRK.B')"
            )
        )

    with engine.connect() as connection:
        # create_all already built watchlist_items. Revision 0004
        # creates that table, so the upgrade from 0002 needs it gone.
        connection.execute(text("DROP TABLE watchlist_items"))
        connection.commit()
        stamp(connection, "0002")
        upgrade_head(connection)
        require_company_instrument_columns(connection)
        assert metadata_diff(connection) == []
        assert ticker_uniqueness(connection) == (
            (("uq_companies_ticker", True, ("ticker",)),),
            (),
        )
        downgrade_to(connection, "0002")
        assert ticker_uniqueness(connection) == (
            (("ix_companies_ticker", True, ("ticker",)),),
            (),
        )
        upgrade_head(connection)
        assert metadata_diff(connection) == []
        stored = (
            connection.execute(
                text("SELECT ticker FROM companies ORDER BY ticker")
            )
            .scalars()
            .all()
        )
        assert stored == ["BRK.A", "BRK.B"]
    engine.dispose()


def test_upgrade_downgrade_upgrade_keeps_the_legacy_row(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'round.db'}")
    with engine.begin() as connection:
        connection.execute(text(LEGACY_COMPANIES))
        connection.execute(text(LEGACY_METRICS))
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) "
                "VALUES (1, 'Apple', 'AAPL')"
            )
        )
    with engine.connect() as connection:
        upgrade_head(connection)
        require_company_instrument_columns(connection)
        downgrade_base(connection)
        upgrade_head(connection)
        require_company_instrument_columns(connection)
        stored = connection.execute(
            text("SELECT ticker, instrument_type FROM companies WHERE id = 1")
        ).one()
        assert stored.ticker == "AAPL"
        assert stored.instrument_type == "STOCK"
        assert ticker_uniqueness(connection)[0] == (
            ("uq_companies_ticker", True, ("ticker",)),
        )
    engine.dispose()


def test_downgrade_keeps_an_extra_ticker_index(tmp_path):
    """A second unique ticker index means downgrade does not add ix_."""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'extra.db'}")
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        stamp(connection, "0003")
        connection.execute(
            text("CREATE UNIQUE INDEX extra_ticker ON companies (ticker)")
        )
        connection.commit()
        downgrade_to(connection, "0002")
        names = [index["name"] for index in inspect_indexes(connection)]
        assert "uq_companies_ticker" not in names
        assert "ix_companies_ticker" not in names
        assert "extra_ticker" in names
    engine.dispose()


def test_sqlite_ticker_upgrade_keeps_price_bars(tmp_path):
    """``create_index`` does not rebuild ``companies``.

    Foreign keys are on. A ``batch_alter_table`` rebuild would drop
    ``companies`` and SQLite would cascade-delete ``price_bars``.
    The bars and the metrics row are still there after revision 0003.
    """
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0003_companies_ticker_unique.py"
    )
    source = migration.read_text()
    assert "op.batch_alter_table" not in source
    assert "op.create_index" in source

    engine = create_db_engine(f"sqlite:///{tmp_path / 'children.db'}")
    with engine.begin() as connection:
        connection.execute(text(LEGACY_COMPANIES))
        connection.execute(text(LEGACY_METRICS))
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) "
                "VALUES (1, 'Apple', 'AAPL')"
            )
        )
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
        upgrade_to(connection, "0002")
        connection.execute(
            text(
                "INSERT INTO financial_metrics (id, company_id) "
                "VALUES (1, 1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO price_bars ("
                "id, instrument_id, bar_date, currency, source, "
                "retrieved_at) VALUES ("
                "7, 1, '2024-01-02', 'USD', 'fake', "
                "'2024-01-02 00:00:00')"
            )
        )
        connection.commit()
        upgrade_to(connection, "0003")
        bars = connection.execute(
            text("SELECT id, instrument_id, source FROM price_bars")
        ).one()
        assert bars == (7, 1, "fake")
        metrics = connection.execute(
            text("SELECT id, company_id FROM financial_metrics")
        ).one()
        assert metrics == (1, 1)
        names = {index["name"] for index in inspect_indexes(connection)}
        assert "uq_companies_ticker" in names
    engine.dispose()


def test_two_connections_share_a_name_and_reject_a_ticker(tmp_path):
    """The unique index is what stops a second insert of BRK.A.

    The same name on BRK.B is allowed. The second connection does not
    use the repository pre-check, so this is the database rule.
    """
    from sqlalchemy.orm import sessionmaker

    engine = create_db_engine(f"sqlite:///{tmp_path / 'two.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    first = session_factory()
    second = session_factory()
    try:
        first.add(CompanyDB(name="Berkshire Hathaway", ticker="BRK.A"))
        first.commit()
        second.add(CompanyDB(name="Berkshire Hathaway", ticker="BRK.B"))
        second.commit()
        second.add(CompanyDB(name="Other", ticker="BRK.A"))
        with pytest.raises(IntegrityError):
            second.commit()
        second.rollback()
        assert first.query(CompanyDB).count() == 2
    finally:
        first.close()
        second.close()
        engine.dispose()
