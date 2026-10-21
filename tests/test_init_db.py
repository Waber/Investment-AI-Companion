"""init_db and seed_sample_data against a private in-memory SQLite engine."""

import json
import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import init_db as database_initializer
from app.core.database import Base
from app.models.database_models import CompanyDB, FinancialMetricsDB


@pytest.fixture
def memory_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield engine
    engine.dispose()


@pytest.fixture
def session(memory_engine):
    Base.metadata.create_all(bind=memory_engine)
    db = sessionmaker(bind=memory_engine)()
    yield db
    db.close()


# company-shaped pin, see #26
def test_init_db_creates_tables_on_configured_engine(
    monkeypatch, memory_engine, capsys
):
    monkeypatch.setattr(database_initializer, "engine", memory_engine)

    database_initializer.init_db()

    tables = set(inspect(memory_engine).get_table_names())
    assert {"companies", "financial_metrics"} <= tables
    assert "Database tables created successfully!" in capsys.readouterr().out


def test_missing_company_table_is_left_for_create_all(memory_engine):
    database_initializer.require_company_instrument_columns(memory_engine)


def test_init_db_rejects_a_companies_table_without_the_new_columns(
    monkeypatch, memory_engine
):
    """An older create_all database has the table and not the columns.

    Startup must stop before it serves. The message names both
    columns and the two Alembic commands.
    """
    with memory_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE companies ("
                "id INTEGER PRIMARY KEY, "
                "name VARCHAR(255) NOT NULL, "
                "ticker VARCHAR(20) NOT NULL)"
            )
        )
    monkeypatch.setattr(database_initializer, "engine", memory_engine)

    with pytest.raises(database_initializer.CompanySchemaError) as error:
        database_initializer.init_db()

    message = str(error.value)
    assert "instrument_type" in message
    assert "isin" in message
    assert "alembic upgrade head" in message
    assert "alembic stamp head" in message
    assert "not `alembic upgrade head`" in message
    assert "ck_companies_instrument_type" in message
    assert "uq_companies_isin" in message
    assert "or the columns added" not in message
    assert "or add the columns" not in message


@pytest.mark.parametrize("present", ["instrument_type", "isin"])
def test_one_missing_company_column_is_named(memory_engine, present):
    missing = "isin" if present == "instrument_type" else "instrument_type"
    with memory_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE companies ("
                "id INTEGER PRIMARY KEY, " + present + " VARCHAR(12))"
            )
        )

    with pytest.raises(database_initializer.CompanySchemaError) as error:
        database_initializer.require_company_instrument_columns(memory_engine)

    message = str(error.value)
    assert missing in message
    assert present not in message.split(". An Alembic-managed", 1)[0]


def test_init_db_is_safe_to_repeat(monkeypatch, memory_engine):
    monkeypatch.setattr(database_initializer, "engine", memory_engine)

    database_initializer.init_db()
    database_initializer.init_db()

    assert "companies" in inspect(memory_engine).get_table_names()


# company-shaped pin, see #26
def test_seed_sample_data_inserts_companies_and_apple_metrics(session, capsys):
    database_initializer.seed_sample_data(session)

    tickers = sorted(row.ticker for row in session.query(CompanyDB))
    assert tickers == ["AAPL", "MSFT", "TSLA"]
    apple = session.query(CompanyDB).filter_by(ticker="AAPL").one()
    metrics = session.query(FinancialMetricsDB).all()
    assert len(metrics) == 2
    assert {row.company_id for row in metrics} == {apple.id}
    assert {row.period_type for row in metrics} == {"annual"}
    assert sorted(row.period_end.year for row in metrics) == [2022, 2023]
    assert "Sample data seeded successfully!" in capsys.readouterr().out


def test_known_tickers_match_the_write_pattern():
    """Seed and demo tickers already match the PR #61 pattern.

    No cleanup migration is added. A ticker outside this pattern is
    not in the repository's sample data.
    """
    from app.models.company import TICKER_PATTERN

    pattern = re.compile(TICKER_PATTERN)
    for ticker in ("AAPL", "MSFT", "TSLA"):
        assert pattern.fullmatch(ticker)
    fixture = json.loads(
        (
            Path(__file__).resolve().parents[1] / "fixtures" / "demo-v1.json"
        ).read_text()
    )
    for item in fixture["companies"]:
        assert pattern.fullmatch(item["company"]["ticker"])


def test_operator_docs_do_not_offer_adding_columns_by_hand():
    root = Path(__file__).resolve().parents[1]
    for relative in ("README.md", "docs/api-demo.md"):
        text = (root / relative).read_text()
        assert "or add the columns" not in text
        assert "or the columns added" not in text
        assert "ck_companies_instrument_type" in text
        assert "uq_companies_isin" in text
        assert "alembic stamp head" in text


def test_seed_sample_data_skips_when_data_exists(session, capsys):
    session.add(CompanyDB(name="Existing", ticker="EXST"))
    session.commit()

    database_initializer.seed_sample_data(session)

    assert session.query(CompanyDB).count() == 1
    assert session.query(FinancialMetricsDB).count() == 0
    assert "already contains data" in capsys.readouterr().out


# company-shaped pin, see #26
def test_seed_sample_data_runs_once(session):
    database_initializer.seed_sample_data(session)
    database_initializer.seed_sample_data(session)

    assert session.query(CompanyDB).count() == 3
    assert session.query(FinancialMetricsDB).count() == 2
