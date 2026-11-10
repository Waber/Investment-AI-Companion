"""ETF and ETC attributes, and price metrics on the instrument detail.

A public JSON body cannot set ``source`` or ``is_synthetic``. A create
without the demo-seed header is manual. The header marks a new row
``demo``. An update records manual and leaves the synthetic flag.
Attributes on a stock are rejected. A missing TER stays null.
"""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, create_db_engine
from app.demo_seed_auth import DEMO_SEED_HEADER, demo_seed_token
from app.models.company import CompanyCreate
from app.models.database_models import (
    RECORD_SOURCE_DEMO,
    RECORD_SOURCE_MANUAL,
    CompanyDB,
    FundAttributesDB,
)
from app.models.price_bar import PriceBarCreate
from app.repositories.company_repository import CompanyRepository
from app.repositories.fund_attributes_repository import (
    FundAttributesRepository,
)
from app.repositories.price_bar_repository import PriceBarRepository


def _token():
    return demo_seed_token(settings.SECRET_KEY)


def _stored(client, row_id):
    session = client.app.state.testing_session_local()
    try:
        return session.get(FundAttributesDB, row_id)
    finally:
        session.close()


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


def _company(session, ticker, instrument_type):
    return CompanyRepository(session).create(
        CompanyCreate(
            name=ticker,
            ticker=ticker,
            instrument_type=instrument_type,
            currency="EUR",
        )
    )


def _payload(**overrides):
    body = {
        "issuer": "Demo Issuer",
        "underlying": "Synthetic World Equity Index",
        "domicile": "Ireland",
        "replication_method": "physical",
        "distribution_policy": "accumulating",
        "aum": 1250000000,
        "aum_currency": "eur",
        "aum_as_of": "2026-06-30",
        "as_of": "2026-09-30",
    }
    body.update(overrides)
    return body


def test_repository_create_is_manual_and_keeps_a_missing_ter(session):
    company = _company(session, "FUND", "ETF")
    created = FundAttributesRepository(session).create(
        company.id, _payload(ter=None)
    )
    assert created.ter is None
    assert created.aum == 1250000000
    assert created.aum_currency == "EUR"
    assert created.aum_as_of == date(2026, 6, 30)
    assert created.as_of == date(2026, 9, 30)
    assert created.source == RECORD_SOURCE_MANUAL
    assert created.is_synthetic is False


def test_repository_rejects_a_stock_and_a_second_row(session):
    repo = FundAttributesRepository(session)
    stock = _company(session, "SHR", "STOCK")
    with pytest.raises(ValueError, match="ETF or an ETC"):
        repo.create(stock.id, _payload())
    assert session.query(FundAttributesDB).count() == 0

    fund = _company(session, "FUND", "ETF")
    repo.create(
        fund.id,
        _payload(),
        record_source=RECORD_SOURCE_DEMO,
        is_synthetic=True,
    )
    with pytest.raises(ValueError, match="already exist"):
        repo.create(fund.id, _payload())


def test_repository_update_records_manual_and_keeps_the_flag(session):
    repo = FundAttributesRepository(session)
    fund = _company(session, "FUND", "ETC")
    repo.create(
        fund.id,
        _payload(ter=0.0015, distribution_policy=None),
        record_source=RECORD_SOURCE_DEMO,
        is_synthetic=True,
    )
    updated = repo.update(fund.id, {"issuer": "Edited", "source": "demo"})
    assert updated.issuer == "Edited"
    assert updated.ter == 0.0015
    assert updated.distribution_policy is None
    assert updated.is_synthetic is True
    assert updated.source == RECORD_SOURCE_MANUAL


def test_repository_rejects_aum_without_its_currency_and_date(session):
    fund = _company(session, "FUND", "ETF")
    repo = FundAttributesRepository(session)
    with pytest.raises(ValueError, match="currency"):
        repo.create(
            fund.id, _payload(aum=10, aum_currency=None, aum_as_of=None)
        )
    with pytest.raises(ValueError, match="negative"):
        repo.create(fund.id, _payload(ter=-0.01))
    assert session.query(FundAttributesDB).count() == 0


def test_repository_rejects_a_non_boolean_synthetic_flag(session):
    fund = _company(session, "FUND", "ETF")
    with pytest.raises(ValueError, match="is_synthetic"):
        FundAttributesRepository(session).create(
            fund.id, _payload(), is_synthetic=1
        )
    assert session.query(FundAttributesDB).count() == 0


def test_deleting_the_company_deletes_the_attributes(session):
    companies = CompanyRepository(session)
    fund = _company(session, "FUND", "ETF")
    FundAttributesRepository(session).create(fund.id, _payload())
    assert companies.delete(fund.id) is True
    assert session.query(FundAttributesDB).count() == 0
    assert session.query(CompanyDB).count() == 0


@pytest.mark.asyncio
async def test_public_json_cannot_set_source_or_the_synthetic_flag(client):
    created = await client.post(
        "/api/v1/companies/",
        json={"name": "Fund", "ticker": "FUND", "instrument_type": "ETF"},
    )
    assert created.status_code == 201
    company_id = created.json()["id"]
    response = await client.post(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json=_payload(ter=None, source="demo", is_synthetic=True),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["ter"] is None
    assert body["source"] == "manual"
    assert body["is_synthetic"] is False
    assert body["as_of"] == "2026-09-30"
    row = _stored(client, body["id"])
    assert row.source == RECORD_SOURCE_MANUAL
    assert row.is_synthetic is False


@pytest.mark.asyncio
async def test_seed_header_marks_a_create_and_an_update_stays_manual(
    client, monkeypatch
):
    monkeypatch.setattr(settings, "DEMO_SEED_ENABLED", True)
    created = await client.post(
        "/api/v1/companies/",
        json={"name": "Fund", "ticker": "FUND", "instrument_type": "ETC"},
        headers={DEMO_SEED_HEADER: _token()},
    )
    company_id = created.json()["id"]
    response = await client.post(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json=_payload(ter=0.0015),
        headers={DEMO_SEED_HEADER: _token()},
    )
    assert response.status_code == 201
    assert response.json()["source"] == "demo"
    assert response.json()["is_synthetic"] is True

    edited = await client.put(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json={"issuer": "Edited", "source": "demo", "is_synthetic": False},
        headers={DEMO_SEED_HEADER: _token()},
    )
    assert edited.status_code == 200
    assert edited.json()["issuer"] == "Edited"
    assert edited.json()["source"] == "manual"
    assert edited.json()["is_synthetic"] is True
    assert edited.json()["ter"] == 0.0015


@pytest.mark.asyncio
async def test_attributes_on_a_stock_are_rejected(client):
    created = await client.post(
        "/api/v1/companies/",
        json={"name": "Share", "ticker": "SHR", "instrument_type": "STOCK"},
    )
    company_id = created.json()["id"]
    response = await client.post(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json=_payload(),
    )
    assert response.status_code == 400
    assert "ETF" in response.json()["detail"]
    missing = await client.post(
        "/api/v1/instruments/999/fund-attributes",
        json=_payload(),
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_detail_includes_attributes_and_hand_calculated_metrics(client):
    """110 / 100 - 1 = 0.10 and 110 / 50 - 1 = 1.20.

    Two closes in the one-year window are not enough for volatility.
    The path never falls, so the drawdown is zero.
    """
    created = await client.post(
        "/api/v1/companies/",
        json={
            "name": "Fund",
            "ticker": "FUND",
            "instrument_type": "ETF",
            "currency": "EUR",
        },
    )
    company_id = created.json()["id"]
    await client.post(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json=_payload(ter=None),
    )
    session = client.app.state.testing_session_local()
    try:
        prices = PriceBarRepository(session)
        for day, close in (
            (date(2023, 1, 2), "50"),
            (date(2025, 1, 2), "100"),
            (date(2026, 1, 2), "110"),
        ):
            prices.create(
                company_id,
                PriceBarCreate(
                    date=day,
                    open=close,
                    high=close,
                    low=close,
                    close=close,
                    currency="EUR",
                    source="demo",
                    retrieved_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
                ),
            )
    finally:
        session.close()

    detail = await client.get(f"/api/v1/instruments/{company_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["instrument_type"] == "ETF"
    assert body["fund_attributes"]["ter"] is None
    assert body["fund_attributes"]["source"] == "manual"
    assert body["fund_attributes"]["as_of"] == "2026-09-30"
    metrics = body["price_metrics"]
    assert metrics["source"] == "demo"
    assert metrics["as_of"] == "2026-01-02"
    assert metrics["return_1y"]["value"] == pytest.approx(0.10, abs=1e-12)
    assert metrics["return_1y"]["start"] == "2025-01-02"
    assert metrics["return_1y"]["reason"] is None
    assert metrics["return_3y"]["value"] == pytest.approx(1.20, abs=1e-12)
    assert metrics["volatility"]["value"] is None
    assert metrics["volatility"]["reason"] == "insufficient_history"
    assert metrics["max_drawdown"]["value"] == pytest.approx(0.0, abs=1e-12)

    empty = await client.post(
        "/api/v1/companies/",
        json={"name": "Other", "ticker": "OTHER", "instrument_type": "ETF"},
    )
    other = await client.get(f"/api/v1/instruments/{empty.json()['id']}")
    assert other.status_code == 200
    assert other.json()["fund_attributes"] is None
    assert other.json()["price_metrics"]["return_1y"]["reason"] == "no_prices"
    assert other.json()["price_metrics"]["source"] is None
    missing = await client.get("/api/v1/instruments/999")
    assert missing.status_code == 404
