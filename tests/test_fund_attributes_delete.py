"""Delete the fund-attribute row and leave the instrument.

``DELETE /api/v1/instruments/{id}/fund-attributes`` removes that one
row. The company, its prices, and its notes stay. A second delete,
a stock, and an instrument with no row are 404. An id ItemId rejects
is 422, the same body as the other instrument routes. The demo-seed
header is not read: a valid token and a non-token both leave the
outcome unchanged, and a non-token does not become a 500.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, create_db_engine
from app.demo_seed_auth import DEMO_SEED_HEADER, demo_seed_token
from app.models.database_models import (
    CompanyDB,
    FundAttributesDB,
    NoteDB,
    PriceBarDB,
)
from app.models.price_bar import PriceBarCreate
from app.models.research import NoteCreate
from app.repositories.company_errors import CompanyNotFoundError
from app.repositories.fund_attributes_repository import (
    FundAttributesRepository,
)
from app.repositories.note_repository import NoteRepository
from app.repositories.price_bar_repository import PriceBarRepository
from tests.test_fund_attributes_api import _company, _payload

_NOT_FOUND = {"detail": "Instrument not found"}
_NO_ATTRIBUTES = {"detail": "Fund attributes not found"}
_HUGE_ID = str(2**63)
# The same 422 entries GET /api/v1/instruments/{id} already returns.
_ID_ERRORS = {
    "0": {
        "type": "greater_than",
        "loc": ["path", "instrument_id"],
        "msg": "Input should be greater than 0",
        "input": "0",
        "ctx": {"gt": 0},
    },
    "-1": {
        "type": "greater_than",
        "loc": ["path", "instrument_id"],
        "msg": "Input should be greater than 0",
        "input": "-1",
        "ctx": {"gt": 0},
    },
    _HUGE_ID: {
        "type": "less_than_equal",
        "loc": ["path", "instrument_id"],
        "msg": "Input should be less than or equal to 9223372036854775807",
        "input": _HUGE_ID,
        "ctx": {"le": 9223372036854775807},
    },
}


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


def _attributes_url(instrument_id):
    return f"/api/v1/instruments/{instrument_id}/fund-attributes"


async def _raw_delete(client, instrument_id, header):
    """DELETE through ASGI so the header can be Latin-1."""
    path = _attributes_url(instrument_id)
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "DELETE",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": [
            (b"host", b"127.0.0.1"),
            (b"x-iac-demo-seed", header),
        ],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 80),
    }
    status = {}

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            status["code"] = message["status"]
        elif message["type"] == "http.response.body":
            status["body"] = status.get("body", b"") + message.get("body", b"")

    await client.app(scope, receive, send)
    return status


def _price_bar():
    return PriceBarCreate(
        date="2026-01-02",
        open="10",
        high="11",
        low="10",
        close="11",
        currency="EUR",
        source="demo",
        retrieved_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def assert_repository_delete_happy_path(session):
    """The row goes. The company, its price, and its note stay."""
    company = _company(session, "FUND", "ETF")
    repo = FundAttributesRepository(session)
    created = repo.create(company.id, _payload())
    PriceBarRepository(session).create(company.id, _price_bar())
    NoteRepository(session).create(
        company.id, NoteCreate(body="Kept when attributes go.")
    )

    assert repo.delete(company.id) is True

    assert repo.get_by_company(company.id) is None
    assert session.get(FundAttributesDB, created.id) is None
    kept = session.get(CompanyDB, company.id)
    assert kept is not None
    assert kept.ticker == "FUND"
    assert kept.instrument_type == "ETF"
    assert session.query(PriceBarDB).count() == 1
    assert session.query(NoteDB).count() == 1
    assert session.query(FundAttributesDB).count() == 0

    assert repo.delete(company.id) is False
    assert session.get(CompanyDB, company.id) is not None
    assert session.query(PriceBarDB).count() == 1
    assert session.query(NoteDB).count() == 1


def assert_repository_delete_missing(session):
    """No row, and no company, both leave every other row in place."""
    repo = FundAttributesRepository(session)
    companies = session.query(CompanyDB).count()
    prices = session.query(PriceBarDB).count()
    notes = session.query(NoteDB).count()
    attributes = session.query(FundAttributesDB).count()
    with pytest.raises(CompanyNotFoundError):
        repo.delete(999999)
    assert session.query(CompanyDB).count() == companies
    assert session.query(PriceBarDB).count() == prices
    assert session.query(NoteDB).count() == notes
    assert session.query(FundAttributesDB).count() == attributes

    fund = _company(session, "BARE", "ETF")
    assert repo.delete(fund.id) is False
    assert session.get(CompanyDB, fund.id) is not None
    stock = _company(session, "SHR", "STOCK")
    assert repo.delete(stock.id) is False
    assert session.get(CompanyDB, stock.id).instrument_type == "STOCK"
    assert session.query(FundAttributesDB).count() == attributes


def test_repository_delete_removes_only_the_attribute_row(session):
    assert_repository_delete_happy_path(session)


def test_repository_delete_missing_is_a_no_op(session):
    assert_repository_delete_missing(session)


async def _instrument(client, ticker, instrument_type):
    response = await client.post(
        "/api/v1/companies/",
        json={
            "name": ticker,
            "ticker": ticker,
            "instrument_type": instrument_type,
            "currency": "EUR",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _store_attributes(client, instrument_id, headers=None):
    response = await client.post(
        _attributes_url(instrument_id),
        json=_payload(),
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response


async def _store_price(client, instrument_id):
    response = await client.post(
        f"/api/v1/instruments/{instrument_id}/prices",
        json={
            "date": "2026-01-05",
            "open": "10.00000000",
            "high": "12.00000000",
            "low": "9.00000000",
            "close": "11.00000000",
            "volume": 100,
            "currency": "EUR",
            "source": "demo",
            "retrieved_at": "2026-01-02T00:00:00Z",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _store_note(client, instrument_id):
    response = await client.post(
        f"/api/v1/instruments/{instrument_id}/notes",
        json={"body": "Kept when attributes go."},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def assert_delete_keeps_the_instrument(client):
    instrument_id = await _instrument(client, "FUND", "ETF")
    await _store_attributes(client, instrument_id)
    price = await _store_price(client, instrument_id)
    note = await _store_note(client, instrument_id)

    deleted = await client.delete(_attributes_url(instrument_id))
    assert deleted.status_code == 204
    assert deleted.content == b""

    detail = await client.get(f"/api/v1/instruments/{instrument_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == instrument_id
    assert body["ticker"] == "FUND"
    assert body["instrument_type"] == "ETF"
    assert body["fund_attributes"] is None
    attributes = await client.get(_attributes_url(instrument_id))
    assert attributes.status_code == 200
    assert attributes.json() is None
    prices = await client.get(f"/api/v1/instruments/{instrument_id}/prices")
    assert [row["id"] for row in prices.json()] == [price["id"]]
    notes = await client.get(f"/api/v1/instruments/{instrument_id}/notes")
    assert [row["id"] for row in notes.json()] == [note["id"]]

    again = await client.delete(_attributes_url(instrument_id))
    assert again.status_code == 404
    assert again.json() == _NO_ATTRIBUTES
    still = await client.get(f"/api/v1/instruments/{instrument_id}")
    assert still.status_code == 200
    assert still.json()["ticker"] == "FUND"
    assert still.json()["fund_attributes"] is None


async def assert_unknown_instrument_is_404(client):
    deleted = await client.delete(_attributes_url(999999))
    assert deleted.status_code == 404
    assert deleted.json() == _NOT_FOUND


async def assert_delete_on_a_stock_keeps_the_stock(client):
    instrument_id = await _instrument(client, "SHR", "STOCK")
    price = await _store_price(client, instrument_id)
    deleted = await client.delete(_attributes_url(instrument_id))
    assert deleted.status_code == 404
    assert deleted.json() == _NO_ATTRIBUTES
    detail = await client.get(f"/api/v1/instruments/{instrument_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == instrument_id
    assert body["ticker"] == "SHR"
    assert body["instrument_type"] == "STOCK"
    assert body["fund_attributes"] is None
    prices = await client.get(f"/api/v1/instruments/{instrument_id}/prices")
    assert [row["id"] for row in prices.json()] == [price["id"]]


async def assert_delete_rejects_id(client, raw):
    deleted = await client.delete(_attributes_url(raw))
    assert deleted.status_code == 422
    assert deleted.json() == {"detail": [_ID_ERRORS[raw]]}
    existing = await client.get(f"/api/v1/instruments/{raw}")
    assert deleted.json() == existing.json()


async def assert_delete_header_is_ignored(client, monkeypatch):
    """Creates honor the header. Delete does not read it.

    ``DEMO_SEED_ENABLED`` is on, which is the only mode where a
    header is inspected. A valid token still deletes the row. A
    value that is not 64 lowercase hex characters would raise
    inside the token compare, so a 500 here would mean delete
    started to read the header.
    """
    monkeypatch.setattr(settings, "DEMO_SEED_ENABLED", True)
    token = demo_seed_token(settings.SECRET_KEY)
    instrument_id = await _instrument(client, "SEED", "ETF")
    created = await _store_attributes(
        client, instrument_id, headers={DEMO_SEED_HEADER: token}
    )
    assert created.json()["source"] == "demo"
    assert created.json()["is_synthetic"] is True

    deleted = await client.delete(
        _attributes_url(instrument_id),
        headers={DEMO_SEED_HEADER: token},
    )
    assert deleted.status_code == 204
    assert deleted.content == b""
    detail = await client.get(f"/api/v1/instruments/{instrument_id}")
    assert detail.status_code == 200
    assert detail.json()["fund_attributes"] is None
    assert detail.json()["ticker"] == "SEED"

    other_id = await _instrument(client, "SEED2", "ETF")
    await _store_attributes(client, other_id)
    # httpx refuses a non-ASCII header, so this call is raw ASGI.
    # 64 Latin-1 characters is the token length. compare_digest
    # raises TypeError on that string. Delete must not read it.
    messy = await _raw_delete(
        client, other_id, ("\u00e9" * 64).encode("latin-1")
    )
    assert messy["code"] == 204
    assert messy.get("body", b"") == b""
    still = await client.get(f"/api/v1/instruments/{other_id}")
    assert still.status_code == 200
    assert still.json()["fund_attributes"] is None
    assert still.json()["ticker"] == "SEED2"


@pytest.mark.asyncio
async def test_delete_returns_204_then_a_second_delete_is_404(client):
    await assert_delete_keeps_the_instrument(client)


@pytest.mark.asyncio
async def test_delete_unknown_instrument_is_404(client):
    await assert_unknown_instrument_is_404(client)


@pytest.mark.asyncio
async def test_delete_on_a_stock_is_404_and_keeps_the_stock(client):
    await assert_delete_on_a_stock_keeps_the_stock(client)


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", ["0", "-1", _HUGE_ID])
async def test_delete_rejects_an_id_outside_item_id(client, raw):
    await assert_delete_rejects_id(client, raw)


@pytest.mark.asyncio
async def test_demo_seed_header_is_ignored_on_delete(client, monkeypatch):
    await assert_delete_header_is_ignored(client, monkeypatch)
