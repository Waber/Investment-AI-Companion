"""instrument_type and ISIN on the existing company API.

The type is chosen by the caller. A provider quoteType is not a type.
The ISIN examples are published identifiers used to pin the checksum.
They are not holdings and they are not a suggestion to buy or sell.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.api.data_collection import get_collector
from app.models.company import InstrumentType, normalize_instrument_type
from app.models.database_models import CompanyDB
from app.repositories.company_repository import (
    DUPLICATE_ISIN_DETAIL,
    CompanyRepository,
    _instrument_type_value,
)
from tests.collector_stubs import sourced

COMPANIES = "/api/v1/companies/"
FETCH = "/api/v1/data-collection/fetch-company"
APPLE_ISIN = "US0378331005"
ETF_ISIN = "IE00B4L5Y983"


def test_stored_type_is_the_enum_value_or_stock_when_missing():
    assert _instrument_type_value(InstrumentType.ETC) == "ETC"
    assert _instrument_type_value(None) == "STOCK"
    assert _instrument_type_value("ETF") == "ETF"


def test_instrument_type_accepts_only_the_three_names():
    assert normalize_instrument_type(" etf ") == "ETF"
    assert normalize_instrument_type("Etc") == "ETC"
    assert normalize_instrument_type(InstrumentType.ETF) is InstrumentType.ETF
    assert normalize_instrument_type(None) is None
    assert normalize_instrument_type(1) == 1
    with pytest.raises(ValueError, match="STOCK, ETF, or ETC"):
        normalize_instrument_type("EQUITY")
    with pytest.raises(ValueError, match="ASCII"):
        normalize_instrument_type("ETFÉ")
    with pytest.raises(ValueError, match="control characters"):
        normalize_instrument_type("ETF\n")


@pytest.mark.asyncio
async def test_create_defaults_type_to_stock_and_leaves_isin_empty(client):
    response = await client.post(
        COMPANIES, json={"name": "Share", "ticker": "SHAR"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["instrument_type"] == "STOCK"
    assert body["isin"] is None
    fetched = await client.get(f"{COMPANIES}{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["instrument_type"] == "STOCK"
    assert fetched.json()["isin"] is None

    db = client.app.state.testing_session_local()
    try:
        stored = db.get(CompanyDB, body["id"])
        assert stored.instrument_type == "STOCK"
        assert stored.isin is None
    finally:
        db.close()


@pytest.mark.asyncio
async def test_create_stores_uppercase_type_and_isin(client):
    response = await client.post(
        COMPANIES,
        json={
            "name": "World Fund",
            "ticker": "FUND",
            "instrument_type": "etf",
            "isin": "ie00b4l5y983",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["instrument_type"] == "ETF"
    assert body["isin"] == ETF_ISIN
    listed = await client.get(COMPANIES)
    assert listed.status_code == 200
    assert listed.json()[0]["isin"] == ETF_ISIN
    assert listed.json()[0]["instrument_type"] == "ETF"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"name": "A", "ticker": "EQTY", "instrument_type": "EQUITY"},
        {"name": "A", "ticker": "BOND", "instrument_type": "bond"},
        {"name": "A", "ticker": "BADI", "isin": "US0378331006"},
        {"name": "A", "ticker": "SHORT", "isin": "US037833100"},
        {"name": "A", "ticker": "NASC", "isin": "US037833100５"},
    ],
)
async def test_rejected_type_or_isin_writes_no_row(client, payload):
    response = await client.post(COMPANIES, json=payload)

    assert response.status_code == 422
    db = client.app.state.testing_session_local()
    try:
        assert db.query(CompanyDB).count() == 0
    finally:
        db.close()


@pytest.mark.asyncio
async def test_duplicate_ticker_is_400_and_the_session_recovers(client):
    first = await client.post(COMPANIES, json={"name": "A", "ticker": "DUP"})
    assert first.status_code == 201

    duplicate = await client.post(
        COMPANIES, json={"name": "B", "ticker": "dup"}
    )

    assert duplicate.status_code == 400
    assert (
        duplicate.json()["detail"]
        == "A company with this ticker already exists"
    )
    lowered = duplicate.text.lower()
    assert "integrityerror" not in lowered
    assert "unique" not in lowered
    assert "duplicate key" not in lowered

    other = await client.post(COMPANIES, json={"name": "C", "ticker": "OTHER"})
    assert other.status_code == 201
    db = client.app.state.testing_session_local()
    try:
        assert db.query(CompanyDB).count() == 2
    finally:
        db.close()


@pytest.mark.asyncio
async def test_unexpected_integrity_error_stays_a_generic_500(
    client, monkeypatch
):
    def fail(self, company):
        raise IntegrityError(
            "INSERT", {}, Exception("password=hunter2 unique violation")
        )

    monkeypatch.setattr(CompanyRepository, "create", fail)
    response = await client.post(
        COMPANIES, json={"name": "Boom", "ticker": "BOOM"}
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "hunter2" not in response.text
    assert "IntegrityError" not in response.text
    assert "unique violation" not in response.text


@pytest.mark.asyncio
async def test_duplicate_isin_is_400_and_keeps_one_row(client):
    first = await client.post(
        COMPANIES,
        json={
            "name": "A",
            "ticker": "AAA",
            "instrument_type": "STOCK",
            "isin": APPLE_ISIN,
        },
    )
    assert first.status_code == 201

    duplicate = await client.post(
        COMPANIES,
        json={
            "name": "B",
            "ticker": "BBB",
            "instrument_type": "etc",
            "isin": "us0378331005",
        },
    )

    assert duplicate.status_code == 400
    assert duplicate.json()["detail"] == DUPLICATE_ISIN_DETAIL
    assert "IntegrityError" not in duplicate.text
    assert "UNIQUE" not in duplicate.text
    db = client.app.state.testing_session_local()
    try:
        assert db.query(CompanyDB).count() == 1
    finally:
        db.close()


@pytest.mark.asyncio
async def test_update_changes_type_and_can_clear_isin(client):
    created = await client.post(
        COMPANIES,
        json={
            "name": "Fund",
            "ticker": "FUND",
            "instrument_type": "ETF",
            "isin": ETF_ISIN,
        },
    )
    assert created.status_code == 201
    company_id = created.json()["id"]
    url = f"{COMPANIES}{company_id}"

    updated = await client.put(
        url, json={"instrument_type": "etc", "isin": None}
    )

    assert updated.status_code == 200
    assert updated.json()["instrument_type"] == "ETC"
    assert updated.json()["isin"] is None
    assert updated.json()["ticker"] == "FUND"
    fetched = await client.get(url)
    assert fetched.json()["instrument_type"] == "ETC"
    assert fetched.json()["isin"] is None


@pytest.mark.asyncio
async def test_update_rejects_an_isin_owned_by_another_company(client):
    first = await client.post(
        COMPANIES,
        json={"name": "A", "ticker": "AAA", "isin": APPLE_ISIN},
    )
    second = await client.post(
        COMPANIES,
        json={"name": "B", "ticker": "BBB", "isin": ETF_ISIN},
    )
    assert first.status_code == 201
    assert second.status_code == 201

    response = await client.put(
        f"{COMPANIES}{second.json()['id']}",
        json={"isin": "us0378331005"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == DUPLICATE_ISIN_DETAIL
    fetched = await client.get(f"{COMPANIES}{second.json()['id']}")
    assert fetched.json()["isin"] == ETF_ISIN

    same = await client.put(
        f"{COMPANIES}{second.json()['id']}",
        json={"isin": ETF_ISIN},
    )
    assert same.status_code == 200
    assert same.json()["isin"] == ETF_ISIN


class _QuoteTypeCollector:
    """Provider stand-in. quoteType must not become the stored type."""

    def fetch_company_info(self, ticker):
        return sourced(
            {
                "name": "Fetched Share",
                "currency": "USD",
                "quoteType": "EQUITY",
            }
        )


@pytest.mark.asyncio
async def test_fetch_company_does_not_copy_provider_quote_type(client):
    client.app.dependency_overrides[get_collector] = (
        lambda: _QuoteTypeCollector()
    )

    response = await client.post(FETCH, json={"ticker": "AAPL"})

    assert response.status_code == 200
    company_id = response.json()["company_id"]
    fetched = await client.get(f"{COMPANIES}{company_id}")
    assert fetched.status_code == 200
    assert fetched.json()["instrument_type"] == "STOCK"
    assert fetched.json()["isin"] is None
    assert fetched.json()["ticker"] == "AAPL"
