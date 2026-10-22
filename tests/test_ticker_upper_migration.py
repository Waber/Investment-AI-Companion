"""Revision 0007 on SQLite: upper(ticker) and the pair constraint."""

from pathlib import Path

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from app.core.database import Base, create_db_engine
from app.models.database_models import CompanyDB
from tests.company_migration import (
    LEGACY_COMPANIES,
    LEGACY_METRICS,
    downgrade_to,
    stamp,
    unique_constraint_names,
    upgrade_to,
    upper_ticker_index,
)

ROOT = Path(__file__).resolve().parents[1]
_MIGRATION = ROOT / "alembic" / "versions" / "0007_companies_ticker_upper.py"


def _version(connection):
    return connection.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar()


def _child_counts(connection):
    return {
        name: connection.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar()
        for name in (
            "companies",
            "financial_metrics",
            "price_bars",
            "watchlist_items",
            "notes",
            "theses",
        )
    }


def test_migration_file_does_not_import_application_code():
    """0007 is frozen. It does not import app or scripts.

    The check is the start of a line. The docstring says the file
    does not import application code, and that sentence contains
    the letters ``import app``.
    """
    source = _MIGRATION.read_text()
    for line in source.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("import app")
        assert not stripped.startswith("from app")
        assert not stripped.startswith("import scripts")
        assert not stripped.startswith("from scripts")
    assert 'revision = "0007"' in source
    assert 'down_revision = "0005"' in source
    assert (
        "price_bars"
        not in source.split("def upgrade")[1].split("def downgrade")[0]
    )


def test_case_collision_stops_before_the_index_changes(tmp_path):
    """``aapl`` and ``AAPL`` are named. Nothing is rewritten.

    Revision 0003's column index allows the pair. 0007 must refuse it
    before it creates the expression index.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'case.db'}")
    with engine.begin() as connection:
        connection.execute(text(LEGACY_COMPANIES))
        connection.execute(text(LEGACY_METRICS))
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) VALUES "
                "(1, 'Upper', 'AAPL')"
            )
        )
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
        upgrade_to(connection, "0005")
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) "
                "VALUES (2, 'Lower', 'aapl')"
            )
        )
        connection.commit()
        with pytest.raises(RuntimeError) as error:
            upgrade_to(connection, "0007")
        message = str(error.value)
        assert error.value.__class__.__name__ == "UpperTickerCollision"
        assert "'aapl'" in message
        assert "'AAPL'" in message
        assert "did not change those rows" in message
        assert "Traceback" not in message
        assert _version(connection) == "0005"
        stored = (
            connection.execute(
                text("SELECT ticker FROM companies ORDER BY id")
            )
            .scalars()
            .all()
        )
        assert stored == ["AAPL", "aapl"]
        assert upper_ticker_index(connection) is None
    engine.dispose()


def test_a_trailing_space_is_not_an_upper_collision(tmp_path):
    """``upper(ticker)`` does not trim. ``AAPL`` and ``AAPL `` both stay.

    The index expression is ``upper(ticker)``, the same comparison the
    preflight uses. Trim-and-uppercase stays the command's check.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'space.db'}")
    with engine.begin() as connection:
        connection.execute(text(LEGACY_COMPANIES))
        connection.execute(text(LEGACY_METRICS))
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) "
                "VALUES (1, 'Plain', 'AAPL')"
            )
        )
    with engine.connect() as connection:
        upgrade_to(connection, "0005")
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker) "
                "VALUES (2, 'Padded', 'AAPL ')"
            )
        )
        connection.commit()
        upgrade_to(connection, "0007")
        stored = (
            connection.execute(
                text("SELECT ticker FROM companies ORDER BY id")
            )
            .scalars()
            .all()
        )
        assert stored == ["AAPL", "AAPL "]
        assert upper_ticker_index(connection) == (
            "uq_companies_ticker",
            True,
            "upper(ticker)",
        )
    engine.dispose()


def test_round_trip_keeps_child_rows(tmp_path):
    """Upgrade to 0007 and back to 0005 keeps every child row.

    This path never had ``uq_company_name_ticker``. Downgrade adds that
    constraint back, which matches the model from before 0007. The
    company, the price bar, the metrics row, the watchlist row, the
    note, and the thesis are still there.
    """
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
        upgrade_to(connection, "0005")
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
        connection.execute(
            text(
                "INSERT INTO watchlist_items (id, company_id, added_at) "
                "VALUES (1, 1, '2024-01-02 00:00:00')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO notes (id, company_id, body) "
                "VALUES (1, 1, 'a note')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO theses (id, company_id, title, body) "
                "VALUES (1, 1, 'a title', 'a body')"
            )
        )
        connection.commit()
        before = _child_counts(connection)
        upgrade_to(connection, "0007")
        # The sqlite3 driver commits the index change immediately and
        # leaves the Alembic version in the open transaction. Commit
        # that version before the insert below. Rolling back the
        # insert would otherwise move the version back to 0005 and
        # the downgrade would not run.
        connection.commit()
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert _child_counts(connection) == before
        assert upper_ticker_index(connection) == (
            "uq_companies_ticker",
            True,
            "upper(ticker)",
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO companies (id, name, ticker) "
                    "VALUES (2, 'Lower', 'aapl')"
                )
            )
        connection.rollback()
        downgrade_to(connection, "0005")
        assert _child_counts(connection) == before
        assert upper_ticker_index(connection) is None
        names = unique_constraint_names(connection)
        assert "uq_company_name_ticker" in names
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
        upgrade_to(connection, "0007")
        assert _child_counts(connection) == before
        assert "uq_company_name_ticker" not in unique_constraint_names(
            connection
        )
    engine.dispose()


def test_sqlite_rebuild_drops_the_pair_constraint_and_keeps_children(
    tmp_path,
):
    """The pair constraint forces a copy of companies, and only companies.

    Foreign keys are on. ``price_bars`` uses ON DELETE CASCADE and
    ``financial_metrics`` does not. Both rows survive the copy. A
    ``BOND`` value still fails the CHECK that was part of the table.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'rebuild.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE companies ("
                "id INTEGER PRIMARY KEY, "
                "name VARCHAR(255) NOT NULL, "
                "ticker VARCHAR(20) NOT NULL, "
                "instrument_type VARCHAR(8) NOT NULL DEFAULT 'STOCK' "
                "CHECK (instrument_type IN ('STOCK', 'ETF', 'ETC')), "
                "CONSTRAINT uq_company_name_ticker UNIQUE (name, ticker))"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX uq_companies_ticker "
                "ON companies (ticker)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE price_bars ("
                "id INTEGER PRIMARY KEY, "
                "instrument_id INTEGER NOT NULL "
                "REFERENCES companies (id) ON DELETE CASCADE)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE financial_metrics ("
                "id INTEGER PRIMARY KEY, "
                "company_id INTEGER NOT NULL REFERENCES companies (id))"
            )
        )
        connection.execute(
            text(
                "INSERT INTO companies (id, name, ticker, instrument_type) "
                "VALUES (1, 'Apple', 'AAPL', 'STOCK')"
            )
        )
        connection.execute(
            text("INSERT INTO price_bars (id, instrument_id) VALUES (7, 1)")
        )
        connection.execute(
            text(
                "INSERT INTO financial_metrics (id, company_id) "
                "VALUES (1, 1)"
            )
        )
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
        stamp(connection, "0005")
        upgrade_to(connection, "0007")
        # Commit the Alembic version before the CHECK insert is
        # rolled back. The version update shares that transaction.
        connection.commit()
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert connection.execute(
            text("SELECT id, instrument_id FROM price_bars")
        ).one() == (7, 1)
        assert connection.execute(
            text("SELECT id, company_id FROM financial_metrics")
        ).one() == (1, 1)
        assert connection.execute(
            text("SELECT name, ticker, instrument_type FROM companies")
        ).one() == ("Apple", "AAPL", "STOCK")
        assert "uq_company_name_ticker" not in unique_constraint_names(
            connection
        )
        assert upper_ticker_index(connection) == (
            "uq_companies_ticker",
            True,
            "upper(ticker)",
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
        downgrade_to(connection, "0005")
        assert (
            connection.execute(text("SELECT id FROM price_bars")).scalar() == 7
        )
        assert (
            connection.execute(
                text("SELECT id FROM financial_metrics")
            ).scalar()
            == 1
        )
        assert "uq_company_name_ticker" in unique_constraint_names(connection)
        assert upper_ticker_index(connection) is None
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
    engine.dispose()


def test_version_survives_closing_the_connection(tmp_path):
    """The revision row is committed, not only the index change.

    Alembic commits its own transaction when this connection was not
    already in one. The companies copy has to commit early so SQLite
    will honor the foreign-key pragma. That early commit must not
    throw away the version update. A new connection is how the
    command-line upgrade is checked: it does not share the
    transaction that ran the migration.
    """
    path = tmp_path / "closed.db"
    engine = create_db_engine(f"sqlite:///{path}")
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
    engine.dispose()

    engine = create_db_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        upgrade_to(connection, "0007")
    engine.dispose()

    engine = create_db_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        assert _version(connection) == "0007"
        assert upper_ticker_index(connection) == (
            "uq_companies_ticker",
            True,
            "upper(ticker)",
        )
        assert (
            connection.execute(
                text("SELECT company_id FROM financial_metrics")
            ).scalar()
            == 1
        )
    engine.dispose()

    engine = create_db_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        downgrade_to(connection, "0005")
    engine.dispose()

    engine = create_db_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        assert _version(connection) == "0005"
        assert upper_ticker_index(connection) is None
        names = unique_constraint_names(connection)
        assert "uq_company_name_ticker" in names
        assert (
            connection.execute(
                text("SELECT company_id FROM financial_metrics")
            ).scalar()
            == 1
        )
    engine.dispose()

    engine = create_db_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        upgrade_to(connection, "0007")
    engine.dispose()

    engine = create_db_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        assert _version(connection) == "0007"
        assert upper_ticker_index(connection) == (
            "uq_companies_ticker",
            True,
            "upper(ticker)",
        )
        assert "uq_company_name_ticker" not in unique_constraint_names(
            connection
        )
    engine.dispose()


def _companies_with_pair_constraint_and_children(connection):
    """A 0005-shaped file whose companies table still has the pair constraint.

    The child tables are the ones that reference companies. The copy
    in revision 0007 must leave every one of them in place.
    """
    connection.execute(
        text(
            "CREATE TABLE companies ("
            "id INTEGER PRIMARY KEY, "
            "name VARCHAR(255) NOT NULL, "
            "ticker VARCHAR(20) NOT NULL, "
            "instrument_type VARCHAR(8) NOT NULL DEFAULT 'STOCK' "
            "CHECK (instrument_type IN ('STOCK', 'ETF', 'ETC')), "
            "CONSTRAINT uq_company_name_ticker UNIQUE (name, ticker))"
        )
    )
    connection.execute(
        text("CREATE UNIQUE INDEX uq_companies_ticker ON companies (ticker)")
    )
    connection.execute(
        text(
            "CREATE TABLE price_bars ("
            "id INTEGER PRIMARY KEY, "
            "instrument_id INTEGER NOT NULL "
            "REFERENCES companies (id) ON DELETE CASCADE)"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE financial_metrics ("
            "id INTEGER PRIMARY KEY, "
            "company_id INTEGER NOT NULL REFERENCES companies (id))"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE watchlist_items ("
            "id INTEGER PRIMARY KEY, "
            "company_id INTEGER NOT NULL "
            "REFERENCES companies (id) ON DELETE CASCADE)"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE notes ("
            "id INTEGER PRIMARY KEY, "
            "company_id INTEGER NOT NULL "
            "REFERENCES companies (id) ON DELETE CASCADE)"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE theses ("
            "id INTEGER PRIMARY KEY, "
            "company_id INTEGER NOT NULL "
            "REFERENCES companies (id) ON DELETE CASCADE)"
        )
    )
    connection.execute(
        text(
            "INSERT INTO companies (id, name, ticker, instrument_type) "
            "VALUES (1, 'Apple', 'AAPL', 'STOCK')"
        )
    )
    connection.execute(
        text("INSERT INTO price_bars (id, instrument_id) VALUES (7, 1)")
    )
    connection.execute(
        text("INSERT INTO financial_metrics (id, company_id) VALUES (1, 1)")
    )
    connection.execute(
        text("INSERT INTO watchlist_items (id, company_id) VALUES (1, 1)")
    )
    connection.execute(
        text("INSERT INTO notes (id, company_id) VALUES (1, 1)")
    )
    connection.execute(
        text("INSERT INTO theses (id, company_id) VALUES (1, 1)")
    )


def _child_row_counts(connection):
    return {
        name: connection.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar()
        for name in (
            "companies",
            "financial_metrics",
            "price_bars",
            "watchlist_items",
            "notes",
            "theses",
        )
    }


def test_upgrade_keeps_foreign_keys_off_when_they_started_off(tmp_path):
    """A connection that had foreign keys off still has them off.

    The companies copy turns the pragma off, then puts back the value
    it found. The application's connections start with the pragma on.
    This one is turned off first, so afterwards it must still be 0.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'fk-off.db'}")
    with engine.begin() as connection:
        _companies_with_pair_constraint_and_children(connection)
    with engine.connect() as connection:
        connection.execute(text("PRAGMA foreign_keys=OFF"))
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 0
        stamp(connection, "0005")
        before = _child_row_counts(connection)
        upgrade_to(connection, "0007")
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 0
        assert _child_row_counts(connection) == before
        assert "uq_company_name_ticker" not in unique_constraint_names(
            connection
        )
        assert upper_ticker_index(connection) == (
            "uq_companies_ticker",
            True,
            "upper(ticker)",
        )
    engine.dispose()


def test_a_failed_companies_copy_rolls_back_to_0005(tmp_path):
    """A failure after the copy starts leaves revision 0005 intact.

    The listener raises once ``DROP TABLE companies`` is about to
    run. By then ``companies__new`` has been created and filled.
    The copy's transaction rolls that back. The company row and
    every child table are still there, and the version is 0005.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'copy-fail.db'}")
    with engine.begin() as connection:
        _companies_with_pair_constraint_and_children(connection)
    with engine.connect() as connection:
        stamp(connection, "0005")
        connection.commit()
        before = _child_row_counts(connection)

        def fail_mid_copy(*listener_args):
            statement = listener_args[2]
            compact = " ".join(statement.split()).lower()
            if (
                compact.startswith("drop table")
                and "companies__new" not in compact
                and compact.endswith("companies")
            ):
                raise RuntimeError("forced failure during the companies copy")

        event.listen(engine, "before_cursor_execute", fail_mid_copy)
        try:
            with pytest.raises(
                RuntimeError, match="forced failure during the companies copy"
            ):
                upgrade_to(connection, "0007")
        finally:
            event.remove(engine, "before_cursor_execute", fail_mid_copy)
        assert _version(connection) == "0005"
        assert _child_row_counts(connection) == before
        assert (
            connection.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE name = 'companies__new'"
                )
            ).scalar()
            is None
        )
        assert "uq_company_name_ticker" in unique_constraint_names(connection)
        assert upper_ticker_index(connection) is None
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
    engine.dispose()


def test_create_all_rejects_a_lower_case_twin(tmp_path):
    """The model index, not only the migration, blocks ``aapl``."""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'model.db'}")
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        connection.execute(
            text(
                "INSERT INTO companies (name, ticker) "
                "VALUES ('Apple', 'AAPL')"
            )
        )
        connection.commit()
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO companies (name, ticker) "
                    "VALUES ('Other', 'aapl')"
                )
            )
        connection.rollback()
        assert (
            connection.execute(text("SELECT COUNT(*) FROM companies")).scalar()
            == 1
        )
        assert "uq_company_name_ticker" not in unique_constraint_names(
            connection
        )
    engine.dispose()
    # The ORM row uses the same index. Importing CompanyDB keeps the
    # model under the coverage run's measured package.
    assert CompanyDB.__table__.name == "companies"
