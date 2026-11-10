"""Edges the main attribute tests do not hit.

These lock the 404s, the rejected shapes, and the skips in the
price formula. A missing value stays missing.
"""

from datetime import date, datetime, timezone

import pytest

from app.models.fund_attributes import FundAttributesCreate
from app.price_metrics import derive_price_metrics
from app.repositories.company_errors import CompanyNotFoundError
from app.repositories.fund_attributes_repository import (
    FundAttributesRepository,
)
from app.ui.view_models import to_instrument
from scripts.seed_demo import SeedError, seed_demo
from tests.test_fund_attributes_api import _company, _payload, session
from tests.test_seed_demo_v2 import _fixture

# The session fixture is defined in the API test module and reused here.
assert session is not None


@pytest.mark.asyncio
async def test_get_returns_null_until_a_row_exists_and_put_needs_that_row(
    client,
):
    created = await client.post(
        "/api/v1/companies/",
        json={"name": "Fund", "ticker": "FUND", "instrument_type": "ETF"},
    )
    company_id = created.json()["id"]
    empty = await client.get(
        f"/api/v1/instruments/{company_id}/fund-attributes"
    )
    assert empty.status_code == 200
    assert empty.json() is None
    missing_put = await client.put(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json={"issuer": "Later"},
    )
    assert missing_put.status_code == 404
    stored = await client.post(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json=_payload(),
    )
    assert stored.status_code == 201
    again = await client.post(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json=_payload(),
    )
    assert again.status_code == 400
    fetched = await client.get(
        f"/api/v1/instruments/{company_id}/fund-attributes"
    )
    assert fetched.status_code == 200
    assert fetched.json()["issuer"] == "Demo Issuer"
    absent = await client.get("/api/v1/instruments/999/fund-attributes")
    assert absent.status_code == 404
    missing_company = await client.put(
        "/api/v1/instruments/999/fund-attributes",
        json={"issuer": "Nope"},
    )
    assert missing_company.status_code == 404


@pytest.mark.asyncio
async def test_blank_currency_and_a_boolean_fee_are_rejected(client):
    created = await client.post(
        "/api/v1/companies/",
        json={"name": "Fund", "ticker": "FUND", "instrument_type": "ETF"},
    )
    company_id = created.json()["id"]
    blank = await client.post(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json=_payload(aum_currency="EURO"),
    )
    assert blank.status_code == 422
    boolean = await client.post(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json=_payload(ter=True),
    )
    assert boolean.status_code == 422


def test_repository_rejects_bad_shapes(session):
    repo = FundAttributesRepository(session)
    fund = _company(session, "FUND", "ETF")
    with pytest.raises(ValueError, match="as_of"):
        repo.create(fund.id, {"issuer": "X"})
    with pytest.raises(ValueError, match="manual, demo, or fixture"):
        repo.create(fund.id, _payload(), record_source="yahoo")
    with pytest.raises(CompanyNotFoundError):
        repo.create(999, _payload())
    with pytest.raises(ValueError, match="number"):
        repo.create(fund.id, _payload(ter="high"))
    with pytest.raises(ValueError, match="require aum"):
        repo.create(fund.id, _payload(aum=None, aum_currency="EUR"))
    with pytest.raises(ValueError, match="date"):
        repo.create(fund.id, _payload(as_of="not-a-date"))
    with pytest.raises(ValueError, match="date"):
        repo.create(fund.id, _payload(as_of=datetime(2026, 1, 2)))
    created = repo.create(
        fund.id,
        FundAttributesCreate(
            issuer="  Demo  ",
            as_of=date(2026, 9, 30),
            aum_currency="",
        ),
    )
    assert created.issuer == "Demo"
    assert created.aum is None
    cleared = repo.update(fund.id, {"aum": None, "aum_currency": None})
    assert cleared.aum is None
    assert cleared.aum_currency is None
    with pytest.raises(CompanyNotFoundError):
        repo.update(999, {"issuer": "X"})
    other = _company(session, "OTHER", "ETF")
    assert repo.update(other.id, {"issuer": "X"}) is None


def test_update_after_the_type_changes_to_stock_is_rejected(session):
    repo = FundAttributesRepository(session)
    fund = _company(session, "FUND", "ETF")
    repo.create(fund.id, _payload())
    fund.instrument_type = "STOCK"
    session.commit()
    with pytest.raises(ValueError, match="ETF or an ETC"):
        repo.update(fund.id, {"issuer": "Edited"})


def test_unusable_closes_are_skipped_before_the_formula():
    from decimal import Decimal

    result = derive_price_metrics(
        [
            ("2026-01-02", 10),
            (date(2025, 1, 2), True),
            (date(2025, 1, 3), float("nan")),
            (date(2025, 1, 4), "nope"),
            (date(2025, 1, 2), Decimal("100")),
            (date(2026, 1, 2), Decimal("110")),
        ],
        "demo",
    )
    assert result.return_1y.value == pytest.approx(0.10, abs=1e-12)
    assert result.return_1y.start == date(2025, 1, 2)


def test_view_accepts_a_datetime_and_ignores_a_non_date():
    company = type(
        "Company",
        (),
        {
            "id": 1,
            "description": None,
            "is_synthetic": False,
            "financial_metrics": [],
            "ticker": "FUND",
            "isin": None,
            "name": "Fund",
            "exchange": None,
            "currency": "EUR",
            "country": None,
            "sector": None,
            "industry": None,
            "website": None,
            "instrument_type": "ETF",
        },
    )()
    row = type(
        "Attributes",
        (),
        {
            "issuer": " Demo ",
            "underlying": None,
            "ter": None,
            "domicile": None,
            "replication_method": None,
            "distribution_policy": None,
            "aum": None,
            "aum_currency": None,
            "aum_as_of": "not-a-date",
            "as_of": datetime(2026, 9, 30, tzinfo=timezone.utc),
            "is_synthetic": False,
        },
    )()
    view = to_instrument(company, fund_attributes=row)
    assert view.fund_attributes.issuer == "Demo"
    assert view.fund_attributes.aum_as_of is None
    assert view.fund_attributes.as_of == datetime(
        2026, 9, 30, tzinfo=timezone.utc
    )
    assert view.fund_attributes.source is None


def test_a_stock_attribute_object_is_rejected_before_writes():
    fixture = _fixture()
    fixture["companies"][0]["attributes"] = {"issuer": "Nope"}
    with pytest.raises(SeedError, match="no fund attributes"):
        seed_demo(fixture, None, apply=False)


def test_currency_blank_and_a_non_date_are_rejected(session):
    from app.models.fund_attributes import FundAttributesCreate

    FundAttributesCreate(as_of=date(2026, 9, 30), aum_currency=None)
    repo = FundAttributesRepository(session)
    fund = _company(session, "FUND", "ETF")
    with pytest.raises(ValueError, match="date"):
        repo.create(fund.id, _payload(as_of=1, aum_currency="  "))
    with pytest.raises(ValueError, match="letters"):
        repo.create(fund.id, _payload(aum_currency="EU"))


def test_a_failed_commit_does_not_leave_the_row(session, monkeypatch):
    from sqlalchemy.exc import IntegrityError

    repo = FundAttributesRepository(session)
    fund = _company(session, "FUND", "ETF")

    def boom():
        raise IntegrityError("insert", {}, Exception("constraint"))

    monkeypatch.setattr(session, "commit", boom)
    with pytest.raises(ValueError, match="Failed to create"):
        repo.create(fund.id, _payload())
    monkeypatch.undo()
    created = repo.create(fund.id, _payload())
    monkeypatch.setattr(session, "commit", boom)
    with pytest.raises(ValueError, match="constraint violation"):
        repo.update(fund.id, {"issuer": "Edited"})
    assert created.issuer == "Demo Issuer"


@pytest.mark.asyncio
async def test_put_rejects_a_stock_after_the_type_changes(client):
    created = await client.post(
        "/api/v1/companies/",
        json={"name": "Fund", "ticker": "FUND", "instrument_type": "ETF"},
    )
    company_id = created.json()["id"]
    await client.post(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json=_payload(),
    )
    session = client.app.state.testing_session_local()
    try:
        from app.models.database_models import CompanyDB

        row = session.get(CompanyDB, company_id)
        row.instrument_type = "STOCK"
        session.commit()
    finally:
        session.close()
    response = await client.put(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json={"issuer": "Edited"},
    )
    assert response.status_code == 400
    assert "ETF" in response.json()["detail"]


def test_demo_seed_header_path_is_only_the_attribute_create():
    from scripts.seed_demo import _demo_seed_path

    assert _demo_seed_path("/api/v1/companies/") is True
    assert _demo_seed_path("/api/v1/instruments/4/fund-attributes") is True
    assert _demo_seed_path("/api/v1/instruments/4/prices") is False
    assert _demo_seed_path("/api/v1/instruments/nope/fund-attributes") is False


def test_attribute_source_must_be_demo():
    fixture = _fixture()
    company = fixture["companies"][0]
    company["company"]["instrument_type"] = "ETF"
    company["attributes"] = {
        "issuer": "Demo Issuer",
        "underlying": "Index",
        "ter": -1,
        "domicile": "Ireland",
        "replication_method": "physical",
        "distribution_policy": "accumulating",
        "aum": 10,
        "aum_currency": "PLN",
        "aum_as_of": "2026-09-30",
        "as_of": "2026-09-30",
        "source": "manual",
    }
    with pytest.raises(SeedError, match="source must be demo"):
        seed_demo(fixture, None, apply=False)
    company["attributes"]["source"] = "demo"
    with pytest.raises(SeedError, match="negative"):
        seed_demo(fixture, None, apply=False)
