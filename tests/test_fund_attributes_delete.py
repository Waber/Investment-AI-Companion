"""Delete the fund-attribute row and leave the instrument.

``DELETE /api/v1/instruments/{id}/fund-attributes`` removes that one
row. The company, its prices, its notes, and its theses stay. A
second company that also has attributes stays too. A second delete,
a stock, and an instrument with no row are 404. An id ItemId rejects
is 422, the same body as the other instrument routes. Delete does
not call ``request_is_demo_seed``. A patch that raises from that
function still gets 204.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import sessionmaker

import app.api.instruments as instruments_api
from app.core.config import settings
from app.core.database import Base, create_db_engine
from app.demo_seed_auth import DEMO_SEED_HEADER, demo_seed_token
from app.models.database_models import (
    CompanyDB,
    FundAttributesDB,
    NoteDB,
    PriceBarDB,
    ThesisDB,
)
from app.models.price_bar import PriceBarCreate
from app.models.research import NoteCreate
from app.repositories.company_errors import CompanyNotFoundError
from app.repositories.fund_attributes_repository import (
    FundAttributesDeleteError,
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


def assert_repository_delete_leaves_the_other_row(session):
    """One company is deleted. The other company's row stays.

    The keeper is inserted first. Deleting every row, or deleting
    whichever row the query returns first, removes the keeper.
    """
    keeper = _company(session, "KEEP", "ETF")
    victim = _company(session, "DROP", "ETF")
    repo = FundAttributesRepository(session)
    kept = repo.create(keeper.id, _payload(issuer="Keeper"))
    gone = repo.create(victim.id, _payload(issuer="Victim"))

    assert repo.delete(victim.id) is True

    assert session.query(FundAttributesDB).count() == 1
    row = session.get(FundAttributesDB, kept.id)
    assert row is not None
    assert row.company_id == keeper.id
    assert row.issuer == "Keeper"
    assert session.get(FundAttributesDB, gone.id) is None
    assert session.get(CompanyDB, victim.id) is not None


def test_repository_delete_leaves_the_other_fund(session):
    assert_repository_delete_leaves_the_other_row(session)


def assert_failed_delete_commit_rolls_back(session, ticker="ROLL"):
    """A failed commit undoes the delete. A later commit keeps the row."""
    from sqlalchemy.exc import IntegrityError

    repo = FundAttributesRepository(session)
    fund = _company(session, ticker, "ETF")
    created = repo.create(fund.id, _payload(issuer="Stay"))
    rollbacks = []
    real_rollback = session.rollback

    def rollback():
        rollbacks.append(1)
        return real_rollback()

    def boom():
        raise IntegrityError("DELETE", {}, Exception("constraint"))

    monkeypatch_commit = session.commit
    session.rollback = rollback
    session.commit = boom
    try:
        with pytest.raises(FundAttributesDeleteError) as caught:
            repo.delete(fund.id)
        assert str(caught.value) == (
            "Delete failed due to constraint violation"
        )
        assert not isinstance(caught.value, ValueError)
        assert caught.value.__cause__ is None
        assert caught.value.__context__ is None
    finally:
        session.rollback = real_rollback
        session.commit = monkeypatch_commit
    assert rollbacks
    session.commit()
    row = session.get(FundAttributesDB, created.id)
    assert row is not None
    assert row.company_id == fund.id
    assert row.issuer == "Stay"


def test_failed_delete_commit_rolls_back_and_keeps_the_row(session):
    assert_failed_delete_commit_rolls_back(session)


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


async def _store_attributes(client, instrument_id, headers=None, **overrides):
    response = await client.post(
        _attributes_url(instrument_id),
        json=_payload(**overrides),
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


async def _store_thesis(client, instrument_id):
    response = await client.post(
        f"/api/v1/instruments/{instrument_id}/theses",
        json={"title": "Kept", "body": "The thesis stays."},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def assert_delete_keeps_the_instrument(
    client, ticker="FUND", instrument_type="ETF"
):
    instrument_id = await _instrument(client, ticker, instrument_type)
    await _store_attributes(client, instrument_id)
    price = await _store_price(client, instrument_id)
    note = await _store_note(client, instrument_id)
    thesis = await _store_thesis(client, instrument_id)

    deleted = await client.delete(_attributes_url(instrument_id))
    assert deleted.status_code == 204
    assert deleted.content == b""

    detail = await client.get(f"/api/v1/instruments/{instrument_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == instrument_id
    assert body["ticker"] == ticker
    assert body["instrument_type"] == instrument_type
    assert body["fund_attributes"] is None
    attributes = await client.get(_attributes_url(instrument_id))
    assert attributes.status_code == 200
    assert attributes.json() is None
    prices = await client.get(f"/api/v1/instruments/{instrument_id}/prices")
    assert [row["id"] for row in prices.json()] == [price["id"]]
    notes = await client.get(f"/api/v1/instruments/{instrument_id}/notes")
    assert [row["id"] for row in notes.json()] == [note["id"]]
    session = client.app.state.testing_session_local()
    try:
        stored_thesis = session.get(ThesisDB, thesis["id"])
        assert stored_thesis is not None
        assert stored_thesis.id == thesis["id"]
        assert stored_thesis.company_id == instrument_id
        assert stored_thesis.title == "Kept"
    finally:
        session.close()
    theses = await client.get(f"/api/v1/instruments/{instrument_id}/theses")
    assert [row["id"] for row in theses.json()] == [thesis["id"]]

    again = await client.delete(_attributes_url(instrument_id))
    assert again.status_code == 404
    assert again.json() == _NO_ATTRIBUTES
    still = await client.get(f"/api/v1/instruments/{instrument_id}")
    assert still.status_code == 200
    assert still.json()["ticker"] == ticker
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
    """Creates honor the header. Delete does not call the helper.

    ``_is_seed_token`` returns false for a non-hex value before
    ``compare_digest``, so a Latin-1 header does not raise inside
    ``request_is_demo_seed``. The patch raises on any call. A 500
    means DELETE started to read the header, including a call with
    ``enabled=True``.
    """
    monkeypatch.setattr(settings, "DEMO_SEED_ENABLED", True)
    token = demo_seed_token(settings.SECRET_KEY)
    instrument_id = await _instrument(client, "SEED", "ETF")
    created = await _store_attributes(
        client, instrument_id, headers={DEMO_SEED_HEADER: token}
    )
    assert created.json()["source"] == "demo"
    assert created.json()["is_synthetic"] is True

    def _refuse_demo_seed(*args, **kwargs):
        raise RuntimeError("DELETE must not call request_is_demo_seed")

    original = instruments_api.request_is_demo_seed
    monkeypatch.setattr(
        instruments_api, "request_is_demo_seed", _refuse_demo_seed
    )
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

    monkeypatch.setattr(instruments_api, "request_is_demo_seed", original)
    other_id = await _instrument(client, "SEED2", "ETF")
    await _store_attributes(client, other_id)
    monkeypatch.setattr(
        instruments_api, "request_is_demo_seed", _refuse_demo_seed
    )
    # httpx refuses a non-ASCII header, so this call is raw ASGI.
    # 64 Latin-1 characters is the token length. ``_is_seed_token``
    # rejects that text before ``compare_digest``, so this request
    # alone does not prove DELETE skips the helper. The patch does.
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


def _attribute_rows(client):
    session = client.app.state.testing_session_local()
    try:
        return list(session.query(FundAttributesDB).all())
    finally:
        session.close()


async def assert_http_delete_leaves_the_other_fund(client):
    """A body and a company_id query do not choose another row."""
    keeper_id = await _instrument(client, "KEEP", "ETF")
    victim_id = await _instrument(client, "DROP", "ETF")
    kept = await _store_attributes(client, keeper_id, issuer="Keeper")
    gone = await _store_attributes(client, victim_id, issuer="Victim")
    deleted = await client.request(
        "DELETE",
        _attributes_url(victim_id),
        params={"company_id": keeper_id},
        json={"company_id": keeper_id, "issuer": "Victim"},
    )
    assert deleted.status_code == 204
    assert deleted.content == b""
    rows = _attribute_rows(client)
    assert len(rows) == 1
    assert rows[0].id == kept.json()["id"]
    assert rows[0].company_id == keeper_id
    assert rows[0].issuer == "Keeper"
    assert all(row.id != gone.json()["id"] for row in rows)
    victim = await client.get(f"/api/v1/instruments/{victim_id}")
    assert victim.json()["fund_attributes"] is None
    assert victim.json()["ticker"] == "DROP"
    keeper = await client.get(f"/api/v1/instruments/{keeper_id}")
    assert keeper.json()["fund_attributes"]["issuer"] == "Keeper"
    assert keeper.json()["fund_attributes"]["id"] == kept.json()["id"]


async def assert_etc_without_a_row_is_404(client):
    instrument_id = await _instrument(client, "ETC0", "ETC")
    deleted = await client.delete(_attributes_url(instrument_id))
    assert deleted.status_code == 404
    assert deleted.json() == _NO_ATTRIBUTES
    detail = await client.get(f"/api/v1/instruments/{instrument_id}")
    assert detail.status_code == 200
    assert detail.json()["instrument_type"] == "ETC"
    assert detail.json()["fund_attributes"] is None


@pytest.mark.asyncio
async def test_http_delete_leaves_the_keeper_fund(client):
    await assert_http_delete_leaves_the_other_fund(client)


@pytest.mark.asyncio
async def test_delete_an_etc_returns_204_and_keeps_prices_and_notes(client):
    await assert_delete_keeps_the_instrument(client, "ETC1", "ETC")


@pytest.mark.asyncio
async def test_first_delete_of_an_etc_with_no_row_is_404(client):
    await assert_etc_without_a_row_is_404(client)


async def assert_http_delete_constraint_rolls_back(client, monkeypatch):
    """A failed commit is 400 and the same row is still stored.

    ``commit`` flushes, so the DELETE reaches the database, then
    raises ``IntegrityError``. The repository rolls that back. The
    route answers 400 with the fixed sentence. The row id and the
    issuer are the ones ``POST`` stored.
    """
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    instrument_id = await _instrument(client, "ROLL", "ETF")
    created = await _store_attributes(client, instrument_id, issuer="Stay")
    row_id = created.json()["id"]
    driver = "secret-driver-token"

    def commit_flushes_then_fails(self):
        self.flush()
        raise IntegrityError("DELETE", {}, Exception(driver))

    original = Session.commit
    monkeypatch.setattr(Session, "commit", commit_flushes_then_fails)
    try:
        response = await client.delete(_attributes_url(instrument_id))
    finally:
        monkeypatch.setattr(Session, "commit", original)
    assert response.status_code == 400
    assert response.json() == {
        "detail": "Delete failed due to constraint violation"
    }
    assert driver not in response.text
    session = client.app.state.testing_session_local()
    try:
        row = session.get(FundAttributesDB, row_id)
        assert row is not None
        assert row.id == row_id
        assert row.issuer == "Stay"
        assert row.company_id == instrument_id
    finally:
        session.close()


async def assert_delete_does_not_echo_a_value_error(client, monkeypatch):
    """A ``ValueError`` from delete is not copied into the response.

    The constraint 400 uses one fixed sentence. Any other
    ``ValueError`` stays Starlette's plain 500, so a future message
    cannot become the JSON ``detail``.
    """
    from httpx import ASGITransport, AsyncClient

    instrument_id = await _instrument(client, "LEAK", "ETF")
    await _store_attributes(client, instrument_id, issuer="Stay")
    secret = "driver said unique violation"

    def boom(self, company_id):
        raise ValueError(secret)

    original_delete = FundAttributesRepository.delete
    monkeypatch.setattr(FundAttributesRepository, "delete", boom)
    try:
        transport = ASGITransport(app=client.app, raise_app_exceptions=False)
        async with AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as quiet:
            response = await quiet.delete(_attributes_url(instrument_id))
    finally:
        monkeypatch.setattr(
            FundAttributesRepository, "delete", original_delete
        )
    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert secret not in response.text
    session = client.app.state.testing_session_local()
    try:
        row = (
            session.query(FundAttributesDB)
            .filter(FundAttributesDB.company_id == instrument_id)
            .one()
        )
        assert row.issuer == "Stay"
    finally:
        session.close()


def _forbid_demo_seed_header_read(monkeypatch):
    """Raise when code reads ``X-IAC-Demo-Seed`` from request headers.

    ``get``, ``__getitem__``, ``getlist``, and ``in`` are the lookups
    on that key. A route that calls any of them fails the delete.
    Reading a different header, such as ``host``, still works.
    """
    from starlette.datastructures import Headers

    forbidden = "x-iac-demo-seed"

    def forbidden_key(key):
        return str(key).lower() == forbidden

    real_get = Headers.get
    real_getitem = Headers.__getitem__
    real_getlist = Headers.getlist
    real_contains = Headers.__contains__

    def guarded_get(self, key, default=None):
        if forbidden_key(key):
            raise RuntimeError("DELETE must not read X-IAC-Demo-Seed")
        return real_get(self, key, default)

    def guarded_getitem(self, key):
        if forbidden_key(key):
            raise RuntimeError("DELETE must not read X-IAC-Demo-Seed")
        return real_getitem(self, key)

    def guarded_getlist(self, key):
        if forbidden_key(key):
            raise RuntimeError("DELETE must not read X-IAC-Demo-Seed")
        return real_getlist(self, key)

    def guarded_contains(self, key):
        if forbidden_key(key):
            raise RuntimeError("DELETE must not read X-IAC-Demo-Seed")
        return real_contains(self, key)

    monkeypatch.setattr(Headers, "get", guarded_get)
    monkeypatch.setattr(Headers, "__getitem__", guarded_getitem)
    monkeypatch.setattr(Headers, "getlist", guarded_getlist)
    monkeypatch.setattr(Headers, "__contains__", guarded_contains)
    return (real_get, real_getitem, real_getlist, real_contains)


async def assert_delete_does_not_read_the_demo_seed_header(
    client, monkeypatch
):
    """DELETE does not read ``X-IAC-Demo-Seed`` off the request.

    Patching ``request_is_demo_seed`` misses a route that calls
    ``request.headers.get("X-IAC-Demo-Seed")`` itself. The header
    spy fails that read. The row is still deleted.
    """
    from httpx import ASGITransport, AsyncClient
    from starlette.datastructures import Headers

    instrument_id = await _instrument(client, "HEAD", "ETF")
    created = await _store_attributes(client, instrument_id, issuer="Stay")
    originals = _forbid_demo_seed_header_read(monkeypatch)
    try:
        transport = ASGITransport(app=client.app, raise_app_exceptions=False)
        async with AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as quiet:
            deleted = await quiet.delete(
                _attributes_url(instrument_id),
                headers={DEMO_SEED_HEADER: "ab" * 32},
            )
    finally:
        (
            real_get,
            real_getitem,
            real_getlist,
            real_contains,
        ) = originals
        monkeypatch.setattr(Headers, "get", real_get)
        monkeypatch.setattr(Headers, "__getitem__", real_getitem)
        monkeypatch.setattr(Headers, "getlist", real_getlist)
        monkeypatch.setattr(Headers, "__contains__", real_contains)
    assert deleted.status_code == 204
    assert deleted.content == b""
    session = client.app.state.testing_session_local()
    try:
        assert session.get(FundAttributesDB, created.json()["id"]) is None
    finally:
        session.close()


@pytest.mark.asyncio
async def test_delete_maps_a_constraint_error_to_400(client, monkeypatch):
    await assert_http_delete_constraint_rolls_back(client, monkeypatch)


@pytest.mark.asyncio
async def test_delete_does_not_echo_a_value_error(client, monkeypatch):
    await assert_delete_does_not_echo_a_value_error(client, monkeypatch)


@pytest.mark.asyncio
async def test_delete_does_not_read_the_demo_seed_header(client, monkeypatch):
    await assert_delete_does_not_read_the_demo_seed_header(client, monkeypatch)
