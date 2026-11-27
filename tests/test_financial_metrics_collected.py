"""The collected-row upsert stores a collector's ratios as one TTM row.

It may only replace a row that a collector wrote. A manual row on the
same key must stay untouched.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from app.collected_metrics import TTM_PERIOD
from app.core.database import Base, create_db_engine
from app.models.company import CompanyCreate
from app.models.database_models import (
    RECORD_SOURCE_MANUAL,
    FinancialMetricsDB,
    require_record_source,
)
from app.models.financial_metrics import FinancialMetricsCreate
from app.repositories.company_repository import CompanyRepository
from app.repositories.financial_metrics_repository import (
    CollectedRowConflict,
    FinancialMetricsRepository,
)

PERIOD_END = datetime(2026, 9, 30, tzinfo=timezone.utc)


@pytest.fixture
def session():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture
def company(session):
    return CompanyRepository(session).create(
        CompanyCreate(name="Apple", ticker="AAPL")
    )


def test_first_call_creates_a_yahoo_ttm_row(session, company):
    row, created = FinancialMetricsRepository(session).upsert_collected(
        company.id,
        PERIOD_END,
        TTM_PERIOD,
        {"pe_ratio": 30.5, "roe": 1.4},
        record_source="yahoo_finance",
    )
    assert created is True
    assert row.source == "yahoo_finance"
    assert row.period_type == "ttm"
    assert row.pe_ratio == 30.5


def test_second_call_updates_the_same_row_and_clears_missing_keys(
    session, company
):
    repo = FinancialMetricsRepository(session)
    first, _ = repo.upsert_collected(
        company.id,
        PERIOD_END,
        TTM_PERIOD,
        {"pe_ratio": 30.5, "roe": 1.4},
        record_source="yahoo_finance",
    )
    second, created = repo.upsert_collected(
        company.id,
        PERIOD_END,
        TTM_PERIOD,
        {"pe_ratio": 28.0},
        record_source="yahoo_finance",
    )
    assert created is False
    assert second.id == first.id
    assert second.pe_ratio == 28.0
    assert second.roe is None
    assert session.query(FinancialMetricsDB).count() == 1


def test_a_manual_row_on_the_same_key_is_not_overwritten(session, company):
    repo = FinancialMetricsRepository(session)
    manual = repo.create(
        FinancialMetricsCreate(
            company_id=company.id,
            period_end=PERIOD_END,
            period_type=TTM_PERIOD,
            pe_ratio=11.0,
        ),
        record_source=RECORD_SOURCE_MANUAL,
    )
    with pytest.raises(CollectedRowConflict):
        repo.upsert_collected(
            company.id,
            PERIOD_END,
            TTM_PERIOD,
            {"pe_ratio": 99.0},
            record_source="yahoo_finance",
        )
    session.refresh(manual)
    assert manual.pe_ratio == 11.0
    assert manual.source == RECORD_SOURCE_MANUAL


def test_an_unknown_source_is_rejected(session, company):
    with pytest.raises(ValueError):
        FinancialMetricsRepository(session).upsert_collected(
            company.id,
            PERIOD_END,
            TTM_PERIOD,
            {"pe_ratio": 1.0},
            record_source="stub",
        )
    assert session.query(FinancialMetricsDB).count() == 0


@pytest.mark.parametrize("source", ["yahoo_finance", "fake"])
def test_collector_sources_are_allowed(source):
    assert require_record_source(source) == source
