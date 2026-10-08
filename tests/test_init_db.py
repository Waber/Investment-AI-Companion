"""init_db and seed_sample_data against a private in-memory SQLite engine."""

import pytest
from sqlalchemy import create_engine, inspect
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
