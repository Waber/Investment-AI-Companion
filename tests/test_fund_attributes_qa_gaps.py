"""Locks for mutants QA found on the attribute slice.

The behavior under test is already in the code. These cases are the
ones a one-character edit used to survive.
"""

import math
from datetime import date

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, create_db_engine
from app.demo_seed_auth import DEMO_SEED_HEADER, demo_seed_token
from app.models.database_models import RECORD_SOURCE_MANUAL
from app.models.fund_attributes import AUM_MAX, TER_MAX, FundAttributesCreate
from app.price_metrics import REASON_INSUFFICIENT_HISTORY, derive_price_metrics
from app.repositories.fund_attributes_repository import (
    FundAttributesRepository,
)
from tests.test_fund_attributes_api import _company, _payload, _stored


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


# Lengths are read from the write model, then checked against the
# column widths. A test that only multiplied a constant would still
# pass if that constant were wrong.
_TEXT_FIELDS = (
    "issuer",
    "underlying",
    "domicile",
    "replication_method",
    "distribution_policy",
)
_EXPECTED_MAX = {
    "issuer": 255,
    "underlying": 255,
    "domicile": 100,
    "replication_method": 64,
    "distribution_policy": 64,
}


def _declared_max(field_name):
    """The ``max_length`` declared on ``FundAttributesCreate``."""
    field = FundAttributesCreate.model_fields[field_name]
    for item in field.metadata:
        max_length = getattr(item, "max_length", None)
        if max_length is not None:
            return max_length
    raise AssertionError(f"{field_name} has no max_length")


def _field_error(response, field_name):
    detail = response.json()["detail"]
    matched = [
        item for item in detail if item.get("loc", [None])[-1] == field_name
    ]
    assert len(matched) == 1
    return matched[0]


def test_three_closes_have_a_volatility():
    """Two log returns are enough. ``len(returns) < 3`` would hide it.

    The closes are 2025-01-02, 2025-07-01, and 2026-01-02. The
    one-year anchor is the first of those dates, so all three sit
    in the window.
    """
    result = derive_price_metrics(
        [
            (date(2025, 1, 2), 100),
            (date(2025, 7, 1), 80),
            (date(2026, 1, 2), 120),
        ],
        "demo",
    )
    assert result.volatility.reason is None
    assert result.volatility.value is not None
    assert result.volatility.value > 0
    assert result.volatility.start == date(2025, 1, 2)
    assert result.volatility.end == date(2026, 1, 2)


def test_anchor_uses_the_latest_close_on_or_before_the_target():
    """No maximum gap. The start date shows how far back the anchor is.

    The series ends on 2027-02-28. The only earlier close is
    2024-02-29. The one-year target is 2026-02-28, so that close is
    the one-year anchor and the return is 100 / 80 - 1. The
    three-year target is 2024-02-28, and 2024-02-29 is after it, so
    the three-year return is missing.
    """
    result = derive_price_metrics(
        [
            (date(2024, 2, 29), 80),
            (date(2027, 2, 28), 100),
        ],
        "demo",
    )
    assert result.as_of == date(2027, 2, 28)
    assert result.return_1y.reason is None
    assert result.return_1y.start == date(2024, 2, 29)
    assert result.return_1y.end == date(2027, 2, 28)
    assert result.return_1y.value == pytest.approx(0.25, abs=1e-12)
    assert result.return_3y.value is None
    assert result.return_3y.reason == REASON_INSUFFICIENT_HISTORY
    assert result.return_3y.start is None


def test_a_multi_month_gap_keeps_the_older_start_date():
    """2024-01-02 is a year before the one-year target, and it is used.

    The return is 80 / 50 - 1. The start date is 2024-01-02, not a
    closer date that does not exist.
    """
    result = derive_price_metrics(
        [
            (date(2024, 1, 2), 50),
            (date(2026, 1, 2), 80),
        ],
        "demo",
    )
    assert result.return_1y.reason is None
    assert result.return_1y.start == date(2024, 1, 2)
    assert result.return_1y.value == pytest.approx(0.6, abs=1e-12)


def _value_error(response):
    """The one model ``value_error``. A repository 400 is a string."""
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    matched = [item for item in detail if item.get("type") == "value_error"]
    assert len(matched) == 1
    return matched[0]


@pytest.mark.asyncio
async def test_ter_and_aum_accept_the_cap_and_reject_the_next_float(client):
    """``1`` and ``1e15`` are the caps. The next float above each is 422.

    The numbers are literals. A test that sent ``AUM_MAX`` would still
    pass if that constant became ``1e30``. The 422 is the write model's
    ``value_error``, not a repository 400.
    """
    assert TER_MAX == 1
    assert AUM_MAX == 1e15
    created = await client.post(
        "/api/v1/companies/",
        json={"name": "Fund", "ticker": "CAP1", "instrument_type": "ETF"},
    )
    company_id = created.json()["id"]
    at_cap = await client.post(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json=_payload(ter=1, aum=1e15),
    )
    assert at_cap.status_code == 201
    assert at_cap.json()["ter"] == pytest.approx(1)
    assert at_cap.json()["aum"] == pytest.approx(1e15)

    over_ter = await client.post(
        "/api/v1/companies/",
        json={"name": "Fund", "ticker": "CAP2", "instrument_type": "ETF"},
    )
    rejected_ter = await client.post(
        f"/api/v1/instruments/{over_ter.json()['id']}/fund-attributes",
        json=_payload(ter=math.nextafter(1, math.inf)),
    )
    ter_error = _value_error(rejected_ter)
    assert "fraction from 0 to 1" in ter_error["msg"]

    over_aum = await client.post(
        "/api/v1/companies/",
        json={"name": "Fund", "ticker": "CAP3", "instrument_type": "ETF"},
    )
    rejected_aum = await client.post(
        f"/api/v1/instruments/{over_aum.json()['id']}/fund-attributes",
        json=_payload(aum=math.nextafter(1e15, math.inf)),
    )
    aum_error = _value_error(rejected_aum)
    assert "1e15" in aum_error["msg"]


def test_repository_rejects_the_float_just_above_each_cap(session):
    """The repository guard uses the same literals, not a second cap.

    It imports ``TER_MAX`` and ``AUM_MAX``. It does not keep its own
    copies. ``1`` and ``1e15`` are stored. The next float raises.
    """
    assert TER_MAX == 1
    assert AUM_MAX == 1e15
    repo = FundAttributesRepository(session)
    fund = _company(session, "CAPR", "ETF")
    stored = repo.create(fund.id, _payload(ter=1, aum=1e15))
    assert stored.ter == pytest.approx(1)
    assert stored.aum == pytest.approx(1e15)
    other = _company(session, "CAPQ", "ETF")
    with pytest.raises(ValueError, match="fraction from 0 to 1"):
        repo.create(other.id, _payload(ter=math.nextafter(1, math.inf)))
    with pytest.raises(ValueError, match="1e15"):
        repo.create(other.id, _payload(aum=math.nextafter(1e15, math.inf)))


@pytest.mark.asyncio
@pytest.mark.parametrize("field_name", _TEXT_FIELDS, ids=list(_TEXT_FIELDS))
async def test_text_field_stores_its_max_length_and_rejects_one_more(
    client, field_name
):
    """``max+1`` is Pydantic ``string_too_long``, not a value error.

    The limit is the model's ``max_length``. The expected widths are
    the column sizes: 255, 255, 100, 64, and 64.
    """
    limit = _declared_max(field_name)
    assert limit == _EXPECTED_MAX[field_name]
    exact = "a" * limit
    created = await client.post(
        "/api/v1/companies/",
        json={
            "name": "Fund",
            "ticker": field_name[:6].upper(),
            "instrument_type": "ETF",
        },
    )
    company_id = created.json()["id"]
    stored = await client.post(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json=_payload(**{field_name: exact}),
    )
    assert stored.status_code == 201
    assert stored.json()[field_name] == exact
    rejected = await client.post(
        "/api/v1/companies/",
        json={
            "name": "Fund",
            "ticker": (field_name[:5] + "X").upper(),
            "instrument_type": "ETF",
        },
    )
    over = await client.post(
        f"/api/v1/instruments/{rejected.json()['id']}/fund-attributes",
        json=_payload(**{field_name: "a" * (limit + 1)}),
    )
    assert over.status_code == 422
    error = _field_error(over, field_name)
    assert error["type"] == "string_too_long"
    assert error["ctx"]["max_length"] == limit


@pytest.mark.asyncio
async def test_stock_detail_has_null_attributes_and_no_prices(client):
    """GET of a stock is 200. Only POST and PUT of attributes are 400."""
    created = await client.post(
        "/api/v1/companies/",
        json={"name": "Share", "ticker": "SHR", "instrument_type": "STOCK"},
    )
    company_id = created.json()["id"]
    detail = await client.get(f"/api/v1/instruments/{company_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["fund_attributes"] is None
    assert body["instrument_type"] == "STOCK"
    for name in ("return_1y", "return_3y", "volatility", "max_drawdown"):
        assert body["price_metrics"][name]["value"] is None
        assert body["price_metrics"][name]["reason"] == "no_prices"
    posted = await client.post(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json=_payload(),
    )
    assert posted.status_code == 400
    updated = await client.put(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json={"issuer": "Nope"},
    )
    assert updated.status_code == 400


@pytest.mark.asyncio
async def test_a_public_update_keeps_the_synthetic_flag(client, monkeypatch):
    """A manual edit records ``manual`` and leaves ``is_synthetic``.

    The demo-seed header is not an update. Sending it on PUT does
    not keep ``source=demo``. The flag stays true because the row
    was created as demo data. Clearing it would make that fixture
    look hand-entered after one field change.
    """
    monkeypatch.setattr(settings, "DEMO_SEED_ENABLED", True)
    token = demo_seed_token(settings.SECRET_KEY)
    created = await client.post(
        "/api/v1/companies/",
        json={"name": "Fund", "ticker": "SYN1", "instrument_type": "ETF"},
        headers={DEMO_SEED_HEADER: token},
    )
    company_id = created.json()["id"]
    seeded = await client.post(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json=_payload(),
        headers={DEMO_SEED_HEADER: token},
    )
    assert seeded.status_code == 201
    assert seeded.json()["is_synthetic"] is True

    public = await client.put(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json={"issuer": "Edited by hand"},
    )
    assert public.status_code == 200
    assert public.json()["source"] == "manual"
    assert public.json()["is_synthetic"] is True
    row = _stored(client, public.json()["id"])
    assert row.source == RECORD_SOURCE_MANUAL
    assert row.is_synthetic is True

    with_header = await client.put(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json={"issuer": "Edited with the header"},
        headers={DEMO_SEED_HEADER: token},
    )
    assert with_header.status_code == 200
    assert with_header.json()["source"] == "manual"
    assert with_header.json()["is_synthetic"] is True
