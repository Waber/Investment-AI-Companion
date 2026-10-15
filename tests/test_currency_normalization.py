"""Currency is stored as uppercase ISO 4217, except Yahoo minor units.

``usd`` and ``USD`` are one code. ``GBp`` (pence) and ``ZAc`` (South
African cents) stay exactly as Yahoo sends them. The read model does
not apply the write rule, so a legacy lowercase row still lists.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.api.data_collection import get_collector
from app.models.company import Company, CompanyCreate, CompanyUpdate
from app.models.database_models import CompanyDB
from tests.collector_stubs import sourced

COMPANIES = "/api/v1/companies/"
FETCH = "/api/v1/data-collection/fetch-company"


class PayloadCollector:
    def __init__(self, payload):
        self.payload = payload

    def fetch_company_info(self, ticker):
        return sourced(dict(self.payload))


def test_create_model_uppercases_an_ordinary_code_and_keeps_minor_units():
    assert (
        CompanyCreate(name="Dollar", ticker="USDX", currency="usd").currency
        == "USD"
    )
    assert (
        CompanyCreate(name="Dollar", ticker="USDX", currency="USD").currency
        == "USD"
    )
    assert (
        CompanyCreate(name="Pence", ticker="VOD", currency="GBp").currency
        == "GBp"
    )
    assert (
        CompanyCreate(name="Pounds", ticker="GBP1", currency="gbp").currency
        == "GBP"
    )
    assert (
        CompanyCreate(name="Cents", ticker="ZAC1", currency="ZAc").currency
        == "ZAc"
    )
    assert (
        CompanyCreate(name="Rand", ticker="ZAR1", currency="zar").currency
        == "ZAR"
    )
    # "zac" is not the Yahoo spelling, so it is not treated as cents and
    # it is not folded into ZAR either.
    assert (
        CompanyCreate(name="Other", ticker="ZAC2", currency="zac").currency
        == "ZAC"
    )
    assert (
        CompanyCreate(name="Agorot", ticker="ILA1", currency="ila").currency
        == "ILA"
    )
    assert (
        CompanyCreate(name="Agorot", ticker="ILA2", currency="ILA").currency
        == "ILA"
    )
    assert (
        CompanyCreate(name="Pence", ticker="GBX1", currency="gbx").currency
        == "GBX"
    )
    assert (
        CompanyCreate(name="Padded", ticker="PAD1", currency=" usd ").currency
        == "USD"
    )
    assert (
        CompanyCreate(name="Padded", ticker="PAD2", currency=" GBp ").currency
        == "GBp"
    )

    with pytest.raises(ValidationError):
        CompanyCreate(name="Bad", ticker="BADC", currency="US1")
    with pytest.raises(ValidationError):
        CompanyCreate(name="Bad", ticker="BAD2", currency="abcd")


def test_update_model_uses_the_same_rule():
    assert CompanyUpdate(currency="eur").currency == "EUR"
    assert CompanyUpdate(currency="GBp").currency == "GBp"
    assert CompanyUpdate(currency="ZAc").currency == "ZAc"
    assert CompanyUpdate().currency is None


def test_read_model_does_not_rewrite_a_legacy_code():
    company = Company(
        id=1,
        name="Old",
        ticker="OLD",
        currency="usd",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert company.currency == "usd"


@pytest.mark.asyncio
async def test_api_stores_usd_and_keeps_gbp_pence(client):
    created = await client.post(
        COMPANIES,
        json={"name": "Dollar", "ticker": "USDX", "currency": "usd"},
    )
    assert created.status_code == 201
    assert created.json()["currency"] == "USD"

    updated = await client.put(
        f"/api/v1/companies/{created.json()['id']}",
        json={"currency": "eur"},
    )
    assert updated.status_code == 200
    assert updated.json()["currency"] == "EUR"

    pence = await client.post(
        COMPANIES,
        json={"name": "Vodafone", "ticker": "VOD", "currency": "GBp"},
    )
    assert pence.status_code == 201
    assert pence.json()["currency"] == "GBp"

    cents = await client.post(
        COMPANIES,
        json={"name": "Shoprite", "ticker": "SHP", "currency": "ZAc"},
    )
    assert cents.status_code == 201
    assert cents.json()["currency"] == "ZAc"

    rejected = await client.post(
        COMPANIES,
        json={"name": "Bad", "ticker": "BADC", "currency": "US1"},
    )
    assert rejected.status_code == 422


@pytest.mark.asyncio
async def test_legacy_lowercase_row_still_reads(client):
    session = client.app.state.testing_session_local()
    session.add(CompanyDB(name="Legacy", ticker="LEGC", currency="usd"))
    session.commit()
    session.close()

    listing = await client.get(COMPANIES)
    assert listing.status_code == 200
    legacy = next(row for row in listing.json() if row["ticker"] == "LEGC")
    assert legacy["currency"] == "usd"

    one = await client.get(f"/api/v1/companies/{legacy['id']}")
    assert one.status_code == 200
    assert one.json()["currency"] == "usd"


@pytest.mark.asyncio
async def test_currency_filter_and_uniqueness_follow_the_stored_code(client):
    first = await client.post(
        COMPANIES,
        json={"name": "One", "ticker": "SAME", "currency": "usd"},
    )
    duplicate = await client.post(
        COMPANIES,
        json={"name": "Two", "ticker": "SAME", "currency": "USD"},
    )
    other = await client.post(
        COMPANIES,
        json={"name": "Three", "ticker": "OTHR", "currency": "usd"},
    )
    assert first.status_code == 201
    assert first.json()["currency"] == "USD"
    # Same ticker stays one row. Currency case is not a second identity.
    # The create response for that duplicate is the open ticker-uniqueness
    # defect, so the check is the row, not the status code.
    assert duplicate.status_code != 201
    assert other.status_code == 201
    assert other.json()["currency"] == "USD"
    clash = await client.put(
        f"/api/v1/companies/{other.json()['id']}",
        json={"ticker": "SAME"},
    )
    assert clash.status_code == 400
    kept = await client.get(f"/api/v1/companies/{other.json()['id']}")
    assert kept.json()["ticker"] == "OTHR"
    assert kept.json()["currency"] == "USD"
    listed = await client.get(COMPANIES)
    tickers = sorted(row["ticker"] for row in listed.json())
    assert tickers == ["OTHR", "SAME"]

    session = client.app.state.testing_session_local()
    session.add(CompanyDB(name="Legacy", ticker="LEGC", currency="usd"))
    session.commit()
    session.close()

    uppercase = await client.get("/ui", params={"currency": "USD"})
    assert uppercase.status_code == 200
    assert "SAME" in uppercase.text
    assert "OTHR" in uppercase.text
    assert "LEGC" not in uppercase.text

    legacy = await client.get("/ui", params={"currency": "usd"})
    assert "LEGC" in legacy.text
    assert "SAME" not in legacy.text
    assert "OTHR" not in legacy.text


@pytest.mark.asyncio
async def test_fetch_company_normalizes_currency(client):
    client.app.dependency_overrides[get_collector] = lambda: PayloadCollector(
        {"name": "Dollar Co", "currency": "usd"}
    )
    created = await client.post(FETCH, json={"ticker": "USDX"})
    assert created.status_code == 200
    company_id = created.json()["company_id"]
    stored = await client.get(f"/api/v1/companies/{company_id}")
    assert stored.json()["currency"] == "USD"

    client.app.dependency_overrides[get_collector] = lambda: PayloadCollector(
        {"name": "Dollar Co", "currency": "GBp"}
    )
    updated = await client.post(FETCH, json={"ticker": "USDX"})
    assert updated.status_code == 200
    stored = await client.get(f"/api/v1/companies/{company_id}")
    assert stored.json()["currency"] == "GBp"

    client.app.dependency_overrides[get_collector] = lambda: PayloadCollector(
        {"name": "Shoprite", "currency": "ZAc"}
    )
    cents = await client.post(FETCH, json={"ticker": "SHP"})
    assert cents.status_code == 200
    stored = await client.get(
        f"/api/v1/companies/{cents.json()['company_id']}"
    )
    assert stored.json()["currency"] == "ZAc"
