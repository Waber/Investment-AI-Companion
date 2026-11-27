"""The collector's fund-attribute row: insert, refresh, never overwrite.

A collector may only replace a row it wrote. A manual, demo, or fixture
row on the same instrument stays untouched.
"""

from datetime import date

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, create_db_engine
from app.models.company import CompanyCreate
from app.models.fund_attributes import FundAttributesCreate
from app.repositories.company_errors import CompanyNotFoundError
from app.repositories.company_repository import CompanyRepository
from app.repositories.financial_metrics_repository import CollectedRowConflict
from app.repositories.fund_attributes_repository import (
    FundAttributesRepository,
)

DAY = date(2026, 11, 27)


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


def _company(session, ticker="SPY", instrument_type="ETF"):
    return CompanyRepository(session).create(
        CompanyCreate(
            name="Some Fund", ticker=ticker, instrument_type=instrument_type
        )
    )


def _snapshot(**overrides):
    values = {
        "ter": 0.000945,
        "aum": 796865200128.0,
        "aum_currency": "USD",
        "aum_as_of": DAY,
        "issuer": "State Street Investment Management",
        "as_of": DAY,
    }
    values.update(overrides)
    return FundAttributesCreate(**values)


def _upsert(session, company_id, attributes, source="yahoo_finance"):
    return FundAttributesRepository(session).upsert_collected(
        company_id,
        attributes,
        record_source=source,
        is_synthetic=source == "fake",
    )


def test_first_call_creates_the_collector_row(session):
    fund = _company(session)

    row, created = _upsert(session, fund.id, _snapshot())

    assert created is True
    assert row.source == "yahoo_finance"
    assert row.is_synthetic is False
    assert row.ter == 0.000945
    assert row.aum == 796865200128.0
    assert row.aum_currency == "USD"
    assert row.aum_as_of == DAY
    assert row.issuer == "State Street Investment Management"
    assert row.as_of == DAY


def test_refresh_rewrites_every_fact_column(session):
    fund = _company(session)
    _upsert(session, fund.id, _snapshot(domicile="Ireland"))
    later = date(2026, 11, 28)

    row, created = _upsert(
        session,
        fund.id,
        FundAttributesCreate(ter=0.0009, as_of=later),
    )

    assert created is False
    assert row.ter == 0.0009
    assert row.as_of == later
    # A fact the provider no longer sends does not survive the refresh.
    assert row.aum is None
    assert row.aum_currency is None
    assert row.aum_as_of is None
    assert row.issuer is None
    assert row.domicile is None
    assert len(session.query(type(row)).all()) == 1


def test_fake_rows_are_synthetic(session):
    fund = _company(session)

    row, _created = _upsert(session, fund.id, _snapshot(), source="fake")

    assert row.source == "fake"
    assert row.is_synthetic is True


@pytest.mark.parametrize("other", ["manual", "demo", "fixture", "fake"])
def test_a_row_from_another_source_is_never_overwritten(session, other):
    fund = _company(session)
    FundAttributesRepository(session).create(
        fund.id,
        _snapshot(ter=0.002),
        record_source=other,
        is_synthetic=other != "manual",
    )

    with pytest.raises(CollectedRowConflict) as caught:
        _upsert(session, fund.id, _snapshot())

    assert other in str(caught.value)
    row = FundAttributesRepository(session).get_by_company(fund.id)
    assert row.source == other
    assert row.ter == 0.002


def test_a_stock_gets_no_fund_row(session):
    stock = _company(session, ticker="AAPL", instrument_type="STOCK")

    with pytest.raises(ValueError):
        _upsert(session, stock.id, _snapshot())

    assert FundAttributesRepository(session).get_by_company(stock.id) is None


def test_a_missing_company_is_reported(session):
    with pytest.raises(CompanyNotFoundError):
        _upsert(session, 999, _snapshot())


def test_aum_without_its_currency_is_rejected(session):
    fund = _company(session)

    with pytest.raises(ValueError):
        _upsert(session, fund.id, _snapshot(aum_currency=None))

    assert FundAttributesRepository(session).get_by_company(fund.id) is None


def test_an_unknown_source_is_rejected_before_writing(session):
    fund = _company(session)

    with pytest.raises(ValueError):
        _upsert(session, fund.id, _snapshot(), source="scraper")

    assert FundAttributesRepository(session).get_by_company(fund.id) is None


def test_is_synthetic_must_be_a_bool(session):
    fund = _company(session)

    with pytest.raises(ValueError):
        FundAttributesRepository(session).upsert_collected(
            fund.id, _snapshot(), record_source="fake", is_synthetic="yes"
        )


def test_a_mapping_without_as_of_is_rejected(session):
    fund = _company(session)

    with pytest.raises(ValueError):
        FundAttributesRepository(session).upsert_collected(
            fund.id,
            {"ter": 0.001},
            record_source="yahoo_finance",
            is_synthetic=False,
        )
