"""Security nits on the instrument attribute routes.

Each test failed before the matching fix: a huge id was 500, a huge
TER took down the detail page, hidden characters were stored, a
blank price source was 500, and the seeder comment named only
companies and metrics.
"""

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.models.database_models import FundAttributesDB, PriceBarDB
from app.models.price_bar import PriceBarCreate
from app.repositories.price_bar_repository import PriceBarRepository
from app.ui.formatting import format_number
from app.ui.view_models import _finite_number
from tests.test_fund_attributes_api import _payload

_ROOT = Path(__file__).resolve().parents[1]
_HUGE_ID = str(2**63)


async def _etf(client, ticker="FUND"):
    created = await client.post(
        "/api/v1/companies/",
        json={
            "name": "Fund",
            "ticker": ticker,
            "instrument_type": "ETF",
            "currency": "EUR",
        },
    )
    assert created.status_code == 201
    return created.json()["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("GET", "", None),
        ("GET", "/fund-attributes", None),
        ("POST", "/fund-attributes", _payload()),
        ("PUT", "/fund-attributes", {"issuer": "Later"}),
    ],
)
async def test_instrument_id_above_signed_64_bit_is_422_not_500(
    client, method, suffix, body
):
    """L1. 2**63 must not reach the SQLite driver."""
    response = await client.request(
        method,
        f"/api/v1/instruments/{_HUGE_ID}{suffix}",
        json=body,
    )
    assert response.status_code == 422
    assert response.status_code != 500
    largest = await client.get(f"/api/v1/instruments/{2**63 - 1}")
    assert largest.status_code == 404


@pytest.mark.asyncio
async def test_ter_above_one_is_rejected_and_a_stored_monster_does_not_500(
    client,
):
    """L2. TER is a fraction. 1 is 100 percent. 1e308 is not stored.

    A row planted past the write cap still renders as missing data.
    """
    company_id = await _etf(client)
    rejected = await client.post(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json=_payload(ter=1e308),
    )
    assert rejected.status_code == 422
    accepted = await client.post(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json=_payload(ter=0.0022),
    )
    assert accepted.status_code == 201
    assert accepted.json()["ter"] == pytest.approx(0.0022)
    hundred = await client.post(
        "/api/v1/companies/",
        json={
            "name": "Other",
            "ticker": "OTHR",
            "instrument_type": "ETF",
            "currency": "EUR",
        },
    )
    other_id = hundred.json()["id"]
    over = await client.post(
        f"/api/v1/instruments/{other_id}/fund-attributes",
        json=_payload(ter=100),
    )
    assert over.status_code == 422

    session = client.app.state.testing_session_local()
    try:
        row = session.get(FundAttributesDB, accepted.json()["id"])
        row.ter = 1e308
        row.aum = 1e308
        session.commit()
    finally:
        session.close()
    page = await client.get(f"/ui/instruments/{company_id}")
    assert page.status_code == 200
    assert "brak danych" in page.text
    detail = await client.get(f"/api/v1/instruments/{company_id}")
    assert detail.status_code == 200


def test_format_number_treats_an_overflowing_int_as_missing():
    """L2. A 400-digit integer must not raise."""
    assert format_number(10**400, "en") is None
    assert format_number(10**400, "pl") is None
    assert _finite_number(1e308) is None
    assert _finite_number(0.0022) == pytest.approx(0.0022)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "issuer",
    ["iShares\u202eTXET", "foo\x00bar", "foo\nbar", "foo\x07bar"],
)
async def test_fund_text_rejects_hidden_and_control_characters(client, issuer):
    """L3. The same clean_text rules as company names."""
    company_id = await _etf(client, ticker="CLN" + str(ord(issuer[-1])))
    response = await client.post(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json=_payload(issuer=issuer),
    )
    assert response.status_code == 422
    session = client.app.state.testing_session_local()
    try:
        assert session.query(FundAttributesDB).count() == 0
    finally:
        session.close()


@pytest.mark.asyncio
async def test_blank_issuer_is_stored_as_missing(client):
    """A blank issuer is missing data, not a validation error."""
    company_id = await _etf(client, ticker="BLNK")
    response = await client.post(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json=_payload(issuer="   "),
    )
    assert response.status_code == 201
    assert response.json()["issuer"] is None


@pytest.mark.asyncio
async def test_blank_stored_price_source_does_not_500(client):
    """N1. Only a corrupt bar has a blank source. The page still loads."""
    company_id = await _etf(client, ticker="PRCE")
    session = client.app.state.testing_session_local()
    try:
        PriceBarRepository(session).create(
            company_id,
            PriceBarCreate(
                date=date(2026, 1, 2),
                open="10",
                high="10",
                low="10",
                close="10",
                currency="EUR",
                source="demo",
                retrieved_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ),
        )
        bar = session.query(PriceBarDB).one()
        bar.source = ""
        session.commit()
    finally:
        session.close()
    detail = await client.get(f"/api/v1/instruments/{company_id}")
    assert detail.status_code == 200
    assert detail.json()["price_metrics"]["return_1y"]["reason"] == "no_prices"
    page = await client.get(f"/ui/instruments/{company_id}")
    assert page.status_code == 200


def test_seeder_comment_names_fund_attribute_creates():
    """N2. The header comment must match the paths that send it."""
    text = (_ROOT / "scripts" / "seed_demo.py").read_text(encoding="utf-8")
    comment = text.split("headers = {", 1)[1].split("if method", 1)[0]
    assert "Company and metric creates only" not in comment
    assert "fund" in comment.casefold()
