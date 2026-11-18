"""JSON score and weight-set routes.

The score is computed when the route is called. Nothing is stored
except the weight set. A missing instrument is 404. An id ItemId
rejects is 422, the same body as the other instrument routes. Weight
errors are one fixed sentence and do not repeat the payload. PUT
does not read the demo-seed header and does not require a browser
origin: those are the rules the other JSON writes already use.
"""

import json
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.datastructures import Headers

import app.api.scores as scores_api
from app.demo_seed_auth import DEMO_SEED_HEADER, demo_seed_token
from app.models.company import CompanyCreate
from app.models.database_models import (
    RECORD_SOURCE_DEMO,
    RECORD_SOURCE_MANUAL,
    FinancialMetricsDB,
    FundAttributesDB,
    ScoreWeightsDB,
)
from app.models.fund_attributes import FundAttributesCreate
from app.models.price_bar import PriceBarCreate
from app.price_metrics import derive_price_metrics
from app.repositories.company_repository import CompanyRepository
from app.repositories.fund_attributes_repository import (
    FundAttributesRepository,
)
from app.repositories.price_bar_repository import PriceBarRepository
from app.scoring import score_instrument
from tests.test_instrument_score import ON, STATEMENT_FRESH, default_weights

_NOT_FOUND = {"detail": "Instrument not found"}
_HUGE_ID = str(2**63)
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
_ADVICE = re.compile(
    r"\b("
    r"buy|sell|hold|recommendation|recommend|"
    r"kupuj|kup|sprzedaj|trzymaj|"
    r"rekomendacja|rekomendacje|rekomenduj|"
    r"sygnal|signal|sygnał"
    r")\b",
    re.IGNORECASE,
)
_STOCK_WEIGHTS = {
    "profitability": 1,
    "valuation": 1,
    "balance_sheet": 1,
    "growth": 1,
}
_FUND_WEIGHTS = {
    "cost": 1,
    "size": 1,
    "volatility": 1,
    "max_drawdown": 1,
}


def _advice_hits(value):
    """Advice words in any string of a JSON value, including keys."""
    found = []
    if isinstance(value, str):
        found.extend(_ADVICE.findall(value))
    elif isinstance(value, dict):
        for key, item in value.items():
            found.extend(_advice_hits(key))
            found.extend(_advice_hits(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_advice_hits(item))
    return found


def _assert_no_advice(payload):
    assert _advice_hits(payload) == []


def _session(client):
    return client.app.state.testing_session_local()


def _company(session, ticker, instrument_type):
    return CompanyRepository(session).create(
        CompanyCreate(
            name=ticker,
            ticker=ticker,
            instrument_type=instrument_type,
            currency="EUR",
        )
    )


def _metric(session, company_id, period_end, period_type, **fields):
    session.add(
        FinancialMetricsDB(
            company_id=company_id,
            period_end=period_end,
            period_type=period_type,
            **fields,
        )
    )
    session.commit()


def _hand_stock(session, ticker="SCORE"):
    """The stock behind the hand-worked 56.25 total."""
    company = _company(session, ticker, "STOCK")
    moment = datetime(
        STATEMENT_FRESH.year,
        STATEMENT_FRESH.month,
        STATEMENT_FRESH.day,
        tzinfo=timezone.utc,
    )
    _metric(
        session,
        company.id,
        moment,
        "annual",
        roe=0.1,
        net_margin=0.2,
        pe_ratio=20,
        pb_ratio=3,
        debt_to_equity=100,
        current_ratio=1.25,
        revenue_growth=0.05,
    )
    return company


def _freeze(monkeypatch):
    monkeypatch.setattr(scores_api, "utc_today", lambda: ON)


def _part(body, name):
    return next(item for item in body["components"] if item["name"] == name)


@pytest.fixture(autouse=True)
def _frozen_score_date(monkeypatch):
    _freeze(monkeypatch)


@pytest.mark.asyncio
async def test_stock_score_matches_the_hand_calculation(client):
    session = _session(client)
    try:
        company = _hand_stock(session)
        company_id = company.id
    finally:
        session.close()
    response = await client.get(f"/api/v1/instruments/{company_id}/score")
    assert response.status_code == 200
    body = response.json()
    _assert_no_advice(body)
    assert body["instrument_id"] == company_id
    assert body["ticker"] == "SCORE"
    assert body["instrument_type"] == "STOCK"
    assert body["status"] == "scored"
    assert body["total"] == "56.25"
    assert body["coverage"] == {
        "available": 4,
        "total": 4,
        "label": "4 of 4",
    }
    assert body["oldest_input_date"] == STATEMENT_FRESH.isoformat()
    assert body["weight_set_version"] == 1
    assert body["scored_on"] == ON.isoformat()
    profitability = _part(body, "profitability")
    assert profitability["normalized"] == "75.00"
    assert profitability["contribution"] == "18.75"
    assert profitability["effective_weight"] == "0.2500"
    assert profitability["weight"] == 1
    assert profitability["source"] == "manual"
    assert profitability["as_of"] == STATEMENT_FRESH.isoformat()
    assert profitability["label"] is None
    roe = next(
        item for item in profitability["inputs"] if item["name"] == "roe"
    )
    assert Decimal(roe["value"]) == Decimal("0.1")
    assert roe["normalized"] == "50.00"
    assert roe["status"] == "scored"
    assert "buy" not in json.dumps(body).casefold()


@pytest.mark.asyncio
async def test_latest_null_does_not_hide_an_older_figure(client):
    """The quarterly row has no ROE. The annual ROE is still used.

    When both rows end on the same day, the annual row wins.
    """
    session = _session(client)
    try:
        company = _company(session, "SPLIT", "STOCK")
        fresh = datetime(
            STATEMENT_FRESH.year,
            STATEMENT_FRESH.month,
            STATEMENT_FRESH.day,
            tzinfo=timezone.utc,
        )
        newer = datetime(ON.year, ON.month, ON.day, tzinfo=timezone.utc)
        _metric(
            session,
            company.id,
            fresh,
            "annual",
            roe=0.1,
            net_margin=0.2,
            pe_ratio=20,
            pb_ratio=3,
            debt_to_equity=100,
            current_ratio=1.25,
            revenue_growth=0.05,
        )
        _metric(
            session,
            company.id,
            newer,
            "quarterly",
            net_margin=0.2,
            pe_ratio=20,
            pb_ratio=3,
            debt_to_equity=100,
            current_ratio=1.25,
            revenue_growth=0.05,
        )
        tied = _company(session, "TIE", "STOCK")
        _metric(session, tied.id, fresh, "quarterly", roe=0.2, net_margin=0.2)
        _metric(
            session,
            tied.id,
            fresh,
            "annual",
            roe=0.1,
            net_margin=0.2,
            pe_ratio=20,
            pb_ratio=3,
            debt_to_equity=100,
            current_ratio=1.25,
            revenue_growth=0.05,
        )
        tied_id = tied.id
        company_id = company.id
    finally:
        session.close()
    kept = await client.get(f"/api/v1/instruments/{company_id}/score")
    assert kept.status_code == 200
    assert kept.json()["total"] == "56.25"
    annual = await client.get(f"/api/v1/instruments/{tied_id}/score")
    assert annual.json()["total"] == "56.25"


@pytest.mark.asyncio
async def test_custom_weights_change_the_score_and_the_version(client):
    session = _session(client)
    try:
        company = _hand_stock(session, "CUSTOM")
        company_id = company.id
    finally:
        session.close()
    before = await client.get(f"/api/v1/instruments/{company_id}/score")
    assert before.json()["total"] == "56.25"
    assert before.json()["weight_set_version"] == 1
    saved = await client.put(
        "/api/v1/score-weights/STOCK",
        json={
            "weights": {
                "profitability": 3,
                "valuation": 1,
                "balance_sheet": 1,
                "growth": 1,
            }
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    _assert_no_advice(body)
    assert body["instrument_type"] == "STOCK"
    assert body["version"] == 2
    assert body["stored"] is True
    assert body["weights"]["profitability"] == 3
    after = await client.get(f"/api/v1/instruments/{company_id}/score")
    assert after.json()["weight_set_version"] == 2
    # 75 * 3/6 + 50 * 1/6 + 50 * 1/6 + 50 * 1/6 = 62.50.
    assert after.json()["total"] == "62.50"
    etc = await client.get("/api/v1/score-weights/ETC")
    assert etc.status_code == 200
    assert etc.json()["version"] == 1
    assert etc.json()["stored"] is False
    assert etc.json()["weights"] == _FUND_WEIGHTS


@pytest.mark.asyncio
async def test_missing_growth_is_renormalized(client):
    session = _session(client)
    try:
        company = _company(session, "PART", "STOCK")
        moment = datetime(
            STATEMENT_FRESH.year,
            STATEMENT_FRESH.month,
            STATEMENT_FRESH.day,
            tzinfo=timezone.utc,
        )
        _metric(
            session,
            company.id,
            moment,
            "annual",
            roe=0.1,
            net_margin=0.2,
            pe_ratio=20,
            pb_ratio=3,
            debt_to_equity=100,
            current_ratio=1.25,
        )
        company_id = company.id
    finally:
        session.close()
    response = await client.get(f"/api/v1/instruments/{company_id}/score")
    body = response.json()
    assert body["status"] == "scored"
    assert body["total"] == "58.33"
    assert body["coverage"]["label"] == "3 of 4"
    growth = _part(body, "growth")
    assert growth["status"] == "no_data"
    assert growth["label"] == "no data"
    assert growth["contribution"] is None
    _assert_no_advice(body)


@pytest.mark.asyncio
async def test_stale_price_metrics_are_excluded(client):
    session = _session(client)
    try:
        company = _company(session, "OLD", "ETF")
        FundAttributesRepository(session).create(
            company.id,
            FundAttributesCreate(
                ter=0,
                aum=1_000_000_000,
                aum_currency="EUR",
                aum_as_of=ON,
                as_of=ON,
            ),
        )
        end = ON - timedelta(days=93)
        bars = []
        day = end - timedelta(days=7 * 59)
        price = Decimal("100")
        retrieved = datetime(ON.year, ON.month, ON.day, tzinfo=timezone.utc)
        for _ in range(60):
            bars.append(
                PriceBarCreate(
                    date=day,
                    close=price,
                    currency="EUR",
                    source="fake",
                    retrieved_at=retrieved,
                )
            )
            day += timedelta(days=7)
            price += Decimal("0.5")
        PriceBarRepository(session).upsert_many(company.id, bars)
        company_id = company.id
    finally:
        session.close()
    response = await client.get(f"/api/v1/instruments/{company_id}/score")
    body = response.json()
    assert _part(body, "cost")["status"] == "scored"
    assert _part(body, "size")["status"] == "scored"
    assert _part(body, "volatility")["status"] == "no_data"
    volatility = _part(body, "volatility")["inputs"][0]
    assert volatility["status"] == "stale"
    assert volatility["label"] == "no data"
    assert _part(body, "max_drawdown")["inputs"][0]["status"] == "stale"
    assert body["coverage"]["label"] == "2 of 4"
    assert body["status"] == "scored"


@pytest.mark.asyncio
async def test_demo_v2_incomplete_instrument_has_partial_coverage(client):
    """``DEMO_ETF_GPW`` has no TER. The other three fund parts score.

    The prices and the attribute row come from the fixture. The score
    date is the fixture as-of date, so the series is not stale.
    """
    fixture = json.loads(
        (Path("fixtures/demo-v2.json")).read_text(encoding="utf-8")
    )
    entry = next(
        item
        for item in fixture["companies"]
        if item["company"]["ticker"] == "DEMO_ETF_GPW"
    )
    assert entry["attributes"]["ter"] is None
    session = _session(client)
    try:
        company = CompanyRepository(session).create(
            CompanyCreate(**entry["company"]),
            record_source=RECORD_SOURCE_DEMO,
            is_synthetic=True,
        )
        attributes = dict(entry["attributes"])
        attributes.pop("source")
        FundAttributesRepository(session).create(
            company.id,
            attributes,
            record_source=RECORD_SOURCE_DEMO,
            is_synthetic=True,
        )
        bars = [PriceBarCreate(**row) for row in entry["prices"]]
        PriceBarRepository(session).upsert_many(company.id, bars)
        company_id = company.id
    finally:
        session.close()
    response = await client.get(f"/api/v1/instruments/{company_id}/score")
    assert response.status_code == 200
    body = response.json()
    _assert_no_advice(body)
    assert body["instrument_type"] == "ETF"
    assert body["status"] == "scored"
    assert body["coverage"] == {
        "available": 3,
        "total": 4,
        "label": "3 of 4",
    }
    cost = _part(body, "cost")
    assert cost["status"] == "no_data"
    assert cost["label"] == "no data"
    assert cost["inputs"][0]["value"] is None
    assert _part(body, "size")["status"] == "scored"
    assert Decimal(_part(body, "size")["inputs"][0]["value"]) == Decimal(
        "250000000"
    )
    assert _part(body, "size")["source"] == "demo"
    assert _part(body, "volatility")["source"] == "[IAC-DEMO-V2]"
    derived = derive_price_metrics(
        [
            (date.fromisoformat(row["date"]), row["close"])
            for row in entry["prices"]
        ],
        "[IAC-DEMO-V2]",
    )
    assert derived.volatility.value is not None
    assert derived.max_drawdown.value is not None
    volatility = _part(body, "volatility")["inputs"][0]
    drawdown = _part(body, "max_drawdown")["inputs"][0]
    assert Decimal(volatility["value"]) == Decimal(
        str(derived.volatility.value)
    )
    assert Decimal(drawdown["value"]) == Decimal(
        str(derived.max_drawdown.value)
    )
    assert volatility["as_of"] == derived.volatility.as_of.isoformat()
    expected = score_instrument(
        "ETF",
        {
            "ter": (None, None, None),
            "aum": (Decimal("250000000"), "demo", date(2026, 9, 30)),
            "volatility": (
                Decimal(str(derived.volatility.value)),
                "[IAC-DEMO-V2]",
                derived.volatility.as_of,
            ),
            "max_drawdown": (
                Decimal(str(derived.max_drawdown.value)),
                "[IAC-DEMO-V2]",
                derived.max_drawdown.as_of,
            ),
        },
        default_weights("ETF"),
        ON,
    )
    assert body["total"] == format(expected.total, "f")


@pytest.mark.asyncio
async def test_empty_demo_stock_is_no_score(client):
    """``DEMO_PL_EMPTY`` has no metrics. The total is null, not zero."""
    session = _session(client)
    try:
        company = _company(session, "DEMO_PL_EMPTY", "STOCK")
        company_id = company.id
    finally:
        session.close()
    response = await client.get(f"/api/v1/instruments/{company_id}/score")
    body = response.json()
    _assert_no_advice(body)
    assert body["status"] == "no_score"
    assert body["total"] is None
    assert body["coverage"]["label"] == "0 of 4"
    assert body["oldest_input_date"] is None
    assert all(part["label"] == "no data" for part in body["components"])


@pytest.mark.asyncio
async def test_missing_instrument_is_404(client):
    response = await client.get("/api/v1/instruments/999999/score")
    assert response.status_code == 404
    assert response.json() == _NOT_FOUND
    _assert_no_advice(response.json())


@pytest.mark.asyncio
@pytest.mark.parametrize("instrument_id", ["0", "-1", _HUGE_ID])
async def test_score_rejects_an_id_item_id_rejects(client, instrument_id):
    response = await client.get(f"/api/v1/instruments/{instrument_id}/score")
    assert response.status_code == 422
    assert response.json()["detail"] == [_ID_ERRORS[instrument_id]]


@pytest.mark.asyncio
async def test_default_weights_are_version_1_until_put(client):
    response = await client.get("/api/v1/score-weights/STOCK")
    assert response.status_code == 200
    body = response.json()
    _assert_no_advice(body)
    assert body == {
        "instrument_type": "STOCK",
        "version": 1,
        "stored": False,
        "weights": _STOCK_WEIGHTS,
    }
    again = await client.put(
        "/api/v1/score-weights/STOCK",
        json={"weights": _STOCK_WEIGHTS},
    )
    assert again.status_code == 200
    assert again.json()["version"] == 2
    same = await client.put(
        "/api/v1/score-weights/STOCK",
        json={"weights": _STOCK_WEIGHTS},
    )
    assert same.json()["version"] == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("url", "payload", "detail"),
    [
        (
            "/api/v1/score-weights/buy",
            {"weights": _STOCK_WEIGHTS},
            "Unknown instrument type",
        ),
        (
            "/api/v1/score-weights/stock",
            {"weights": _STOCK_WEIGHTS},
            "Unknown instrument type",
        ),
        (
            "/api/v1/score-weights/STOCK",
            ["profitability"],
            "Score weights must be an object",
        ),
        (
            "/api/v1/score-weights/STOCK",
            {
                "weights": _STOCK_WEIGHTS,
                "note": "driver said unique violation",
            },
            "Unknown score field",
        ),
        (
            "/api/v1/score-weights/STOCK",
            {},
            "Score weights are required",
        ),
        (
            "/api/v1/score-weights/STOCK",
            {"weights": []},
            "Score weights must be an object",
        ),
        (
            "/api/v1/score-weights/STOCK",
            {"weights": {**_STOCK_WEIGHTS, "buy": 1}},
            "Unknown score component",
        ),
        (
            "/api/v1/score-weights/STOCK",
            {"weights": {"profitability": 1}},
            "Score weights must include every component",
        ),
        (
            "/api/v1/score-weights/ETF",
            {"weights": _STOCK_WEIGHTS},
            "Unknown score component",
        ),
        (
            "/api/v1/score-weights/STOCK",
            {
                "weights": {
                    **_STOCK_WEIGHTS,
                    "profitability": True,
                }
            },
            "Score weights must be finite numbers",
        ),
        (
            "/api/v1/score-weights/STOCK",
            {
                "weights": {
                    **_STOCK_WEIGHTS,
                    "profitability": "driver said unique violation",
                }
            },
            "Score weights must be finite numbers",
        ),
        (
            "/api/v1/score-weights/STOCK",
            {
                "weights": {
                    **_STOCK_WEIGHTS,
                    "profitability": -1,
                }
            },
            "A score weight must be from 0 to 1000000",
        ),
        (
            "/api/v1/score-weights/STOCK",
            {"weights": {name: 0 for name in _STOCK_WEIGHTS}},
            "Score weights cannot all be zero",
        ),
    ],
)
async def test_put_validation_uses_a_fixed_sentence(
    client, url, payload, detail
):
    response = await client.put(url, json=payload)
    assert response.status_code == 422
    assert response.json() == {"detail": detail}
    text = json.dumps(response.json())
    assert "driver said" not in text
    assert _advice_hits(response.json()) == []


@pytest.mark.asyncio
async def test_put_without_json_is_a_fixed_422(client):
    response = await client.put(
        "/api/v1/score-weights/STOCK",
        content=b"{",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "Score weights must be an object"}
    assert "input" not in response.json()


@pytest.mark.asyncio
async def test_put_ignores_origin_and_the_demo_seed_header(
    client, monkeypatch
):
    """JSON PUT is not a /ui form, so origin is not checked.

    The demo-seed header is not read. A patch that raises on that
    header still stores the weights.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "DEMO_SEED_ENABLED", True)
    token = demo_seed_token(settings.SECRET_KEY)
    real_get = Headers.get

    def _guard(self, key, default=None):
        if str(key).lower() == "x-iac-demo-seed":
            raise RuntimeError("PUT must not read X-IAC-Demo-Seed")
        return real_get(self, key, default)

    monkeypatch.setattr(Headers, "get", _guard)
    response = await client.put(
        "/api/v1/score-weights/ETF",
        json={"weights": _FUND_WEIGHTS},
        headers={
            DEMO_SEED_HEADER: token,
            "Origin": "https://evil.example",
        },
    )
    assert response.status_code == 200
    assert response.json()["version"] == 2
    assert response.json()["stored"] is True
    plain = await client.put(
        "/api/v1/score-weights/ETC",
        json={"weights": {**_FUND_WEIGHTS, "cost": 2}},
    )
    assert plain.status_code == 200
    assert plain.json()["version"] == 2


@pytest.mark.asyncio
async def test_a_failed_save_does_not_echo_the_driver(client, monkeypatch):
    def _explode(*_args, **_kwargs):
        raise IntegrityError(
            "INSERT", {}, Exception("driver said unique violation")
        )

    monkeypatch.setattr(Session, "commit", _explode)
    response = await client.put(
        "/api/v1/score-weights/STOCK",
        json={"weights": _STOCK_WEIGHTS},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Score weights could not be saved"}
    assert "driver said" not in response.text
    assert "unique violation" not in response.text


@pytest.mark.asyncio
async def test_unreadable_stored_weights_are_a_fixed_500(client):
    session = _session(client)
    try:
        session.add(
            ScoreWeightsDB(
                instrument_type="STOCK",
                version=2,
                weights="not-json driver said unique violation",
            )
        )
        session.commit()
    finally:
        session.close()
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=client.app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url="http://127.0.0.1"
    ) as quiet:
        response = await quiet.get("/api/v1/score-weights/STOCK")
    assert response.status_code == 500
    assert response.json() == {"detail": "Score weights could not be read"}
    assert "driver said" not in response.text
    assert "not-json" not in response.text


@pytest.mark.asyncio
async def test_a_fractional_weight_is_returned_as_sent(client):
    saved = await client.put(
        "/api/v1/score-weights/STOCK",
        json={"weights": {**_STOCK_WEIGHTS, "valuation": 1.5}},
    )
    assert saved.status_code == 200
    assert saved.json()["weights"]["valuation"] == 1.5
    assert saved.json()["weights"]["profitability"] == 1


@pytest.mark.asyncio
async def test_put_with_an_empty_body_is_a_fixed_422(client):
    response = await client.put("/api/v1/score-weights/STOCK")
    assert response.status_code == 422
    assert response.json() == {"detail": "Score weights must be an object"}


@pytest.mark.asyncio
async def test_an_older_metric_row_does_not_replace_a_newer_one(client):
    session = _session(client)
    try:
        company = _company(session, "NEWER", "STOCK")
        newer = datetime(ON.year, ON.month, ON.day, tzinfo=timezone.utc)
        older = datetime(
            STATEMENT_FRESH.year,
            STATEMENT_FRESH.month,
            STATEMENT_FRESH.day,
            tzinfo=timezone.utc,
        )
        _metric(
            session,
            company.id,
            newer,
            "annual",
            roe=0.2,
            net_margin=0.2,
            pe_ratio=20,
            pb_ratio=3,
            debt_to_equity=100,
            current_ratio=1.25,
            revenue_growth=0.05,
        )
        _metric(
            session,
            company.id,
            older,
            "annual",
            roe=0.1,
            net_margin=0.2,
            pe_ratio=20,
            pb_ratio=3,
            debt_to_equity=100,
            current_ratio=1.25,
            revenue_growth=0.05,
        )
        _metric(
            session,
            company.id,
            older,
            "quarterly",
            roe=float("nan"),
        )
        company_id = company.id
    finally:
        session.close()
    response = await client.get(f"/api/v1/instruments/{company_id}/score")
    body = response.json()
    roe = next(
        item
        for item in _part(body, "profitability")["inputs"]
        if item["name"] == "roe"
    )
    assert Decimal(roe["value"]) == Decimal("0.2")


@pytest.mark.asyncio
async def test_an_etf_with_no_attributes_and_no_prices_is_no_score(client):
    session = _session(client)
    try:
        company = _company(session, "BARE", "ETF")
        company_id = company.id
    finally:
        session.close()
    response = await client.get(f"/api/v1/instruments/{company_id}/score")
    body = response.json()
    assert body["status"] == "no_score"
    assert body["total"] is None
    assert all(part["status"] == "no_data" for part in body["components"])


@pytest.mark.asyncio
async def test_unreadable_weights_make_the_score_a_fixed_500(client):
    session = _session(client)
    try:
        company = _company(session, "BADW", "STOCK")
        session.add(
            ScoreWeightsDB(
                instrument_type="STOCK",
                version=2,
                weights="{",
            )
        )
        session.commit()
        company_id = company.id
    finally:
        session.close()
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=client.app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url="http://127.0.0.1"
    ) as quiet:
        response = await quiet.get(f"/api/v1/instruments/{company_id}/score")
    assert response.status_code == 500
    assert response.json() == {"detail": "Score weights could not be read"}
    assert "{" not in response.json()["detail"]


def test_a_stored_type_outside_the_three_is_422():
    from types import SimpleNamespace

    from fastapi import HTTPException

    from app.api.scores import get_instrument_score

    class _Db:
        def get(self, _model, _ident):
            return SimpleNamespace(id=1, ticker="ODD", instrument_type="FUND")

    with pytest.raises(HTTPException) as caught:
        get_instrument_score(1, _Db())
    assert caught.value.status_code == 422
    assert caught.value.detail == "Unknown instrument type"


@pytest.mark.asyncio
async def test_aum_without_its_own_date_uses_the_snapshot_date(client):
    """A raw row can store AUM with no ``aum_as_of``.

    The snapshot date is the one the score uses.
    """
    session = _session(client)
    try:
        company = _company(session, "AUMD", "ETF")
        session.add(
            FundAttributesDB(
                company_id=company.id,
                ter=0,
                aum=1_000_000_000,
                aum_currency="EUR",
                aum_as_of=None,
                as_of=ON,
                source=RECORD_SOURCE_MANUAL,
                is_synthetic=False,
            )
        )
        session.commit()
        company_id = company.id
    finally:
        session.close()
    response = await client.get(f"/api/v1/instruments/{company_id}/score")
    size = _part(response.json(), "size")
    assert size["status"] == "scored"
    assert size["as_of"] == ON.isoformat()


@pytest.mark.asyncio
async def test_get_weights_rejects_an_unknown_type(client):
    response = await client.get("/api/v1/score-weights/BOND")
    assert response.status_code == 422
    assert response.json() == {"detail": "Unknown instrument type"}


def test_a_metric_that_is_not_a_number_is_skipped():
    from app.instrument_score import _finite_number

    assert _finite_number("1.5") is False
    assert _finite_number(0.2) is True


@pytest.mark.asyncio
async def test_openapi_score_text_has_no_advice_words(client):
    response = await client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = {
        path: item for path, item in schema["paths"].items() if "score" in path
    }
    assert "/api/v1/instruments/{instrument_id}/score" in paths
    assert "/api/v1/score-weights/{instrument_type}" in paths
    models = {
        name: body
        for name, body in schema["components"]["schemas"].items()
        if "Score" in name or "Weight" in name
    }
    assert models
    _assert_no_advice(paths)
    _assert_no_advice(models)


_TWO_DECIMALS = re.compile(r"^-?\d+\.\d{2}$")


def _assert_score_strings_have_two_decimals(body):
    """Totals and normalized scores are hundredths, not '12.5' or '0'."""
    assert _TWO_DECIMALS.fullmatch(body["total"])
    for part in body["components"]:
        if part["normalized"] is not None:
            assert _TWO_DECIMALS.fullmatch(part["normalized"])
        if part["contribution"] is not None:
            assert _TWO_DECIMALS.fullmatch(part["contribution"])
        for item in part["inputs"]:
            if item["normalized"] is not None:
                assert _TWO_DECIMALS.fullmatch(item["normalized"])


def _ratios(session, ticker, **fields):
    company = _company(session, ticker, "STOCK")
    moment = datetime(
        STATEMENT_FRESH.year,
        STATEMENT_FRESH.month,
        STATEMENT_FRESH.day,
        tzinfo=timezone.utc,
    )
    _metric(session, company.id, moment, "annual", **fields)
    return company.id


@pytest.mark.asyncio
async def test_equal_fifties_print_twelve_fifty(client):
    """Four components at 50 contribute '12.50' each, not '12.5'."""
    session = _session(client)
    try:
        instrument_id = _ratios(
            session,
            "FIFTY",
            roe=0.10,
            net_margin=0.10,
            pe_ratio=20,
            pb_ratio=3,
            debt_to_equity=100,
            current_ratio=1.25,
            revenue_growth=0.05,
        )
    finally:
        session.close()
    response = await client.get(f"/api/v1/instruments/{instrument_id}/score")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == "50.00"
    assert [part["contribution"] for part in body["components"]] == [
        "12.50",
        "12.50",
        "12.50",
        "12.50",
    ]
    _assert_score_strings_have_two_decimals(body)


@pytest.mark.asyncio
async def test_half_cent_contributions_print_zero_as_two_decimals(client):
    """Unrounded 0.005 cents still print a zero contribution as '0.00'."""
    session = _session(client)
    try:
        instrument_id = _ratios(
            session,
            "HALFC",
            roe=0.00004,
            net_margin=0.00004,
            pe_ratio=29.996,
            pb_ratio=4.9992,
            debt_to_equity=199.96,
            current_ratio=0.5003,
            revenue_growth=-0.10,
        )
    finally:
        session.close()
    response = await client.get(f"/api/v1/instruments/{instrument_id}/score")
    body = response.json()
    assert body["total"] == "0.02"
    contributions = [part["contribution"] for part in body["components"]]
    assert "0.00" in contributions
    assert all(item >= "0.00" for item in contributions)
    _assert_score_strings_have_two_decimals(body)


async def _put_raw(app, headers, receive):
    """One PUT through ASGI, so the test chooses Content-Length and chunks."""
    sent = []

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "PUT",
        "scheme": "http",
        "path": "/api/v1/score-weights/STOCK",
        "raw_path": b"/api/v1/score-weights/STOCK",
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 80),
    }
    await app(scope, receive, send)
    start = next(
        item for item in sent if item["type"] == "http.response.start"
    )
    chunks = [
        item.get("body", b"")
        for item in sent
        if item["type"] == "http.response.body"
    ]
    return start["status"], b"".join(chunks)


@pytest.mark.asyncio
async def test_oversized_content_length_is_413_before_the_body(client):
    """A declared length over 16 KiB is 413 even when the bytes are small.

    A Content-Length that is not a non-negative integer uses that same
    sentence. The bad header text is not copied into the answer.
    """
    reads = {"n": 0}

    async def receive():
        reads["n"] += 1
        return {
            "type": "http.request",
            "body": b'{"weights":{"profitability":1,"valuation":1,'
            b'"balance_sheet":1,"growth":1}}',
            "more_body": False,
        }

    host = (b"host", b"127.0.0.1")
    kind = (b"content-type", b"application/json")
    status, payload = await _put_raw(
        client.app,
        [host, kind, (b"content-length", b"100000")],
        receive,
    )
    assert status == 413
    assert json.loads(payload) == {"detail": "Score weights are too large"}
    assert reads["n"] == 0
    status, payload = await _put_raw(
        client.app,
        [host, kind, (b"content-length", b"nope")],
        receive,
    )
    assert status == 413
    assert json.loads(payload) == {"detail": "Score weights are too large"}
    assert b"nope" not in payload


@pytest.mark.asyncio
async def test_streamed_body_stops_at_the_size_cap(client):
    """A chunked body with no Content-Length is not read past the cap."""
    delivered = {"n": 0}
    chunk = b"x" * 1024

    async def receive():
        if delivered["n"] >= 64 * 1024:
            return {"type": "http.request", "body": b"", "more_body": False}
        delivered["n"] += len(chunk)
        return {"type": "http.request", "body": chunk, "more_body": True}

    status, payload = await _put_raw(
        client.app,
        [
            (b"host", b"127.0.0.1"),
            (b"content-type", b"application/json"),
        ],
        receive,
    )
    assert status == 413
    assert json.loads(payload) == {"detail": "Score weights are too large"}
    assert delivered["n"] <= 16 * 1024 + len(chunk)


@pytest.mark.asyncio
async def test_superscript_content_length_is_413(client):
    """``²`` counts as a digit in ``str.isdigit`` and then ``int`` fails.

    The header is a size only when every character is an ASCII digit.
    The answer is the same 413, and it does not repeat the character.
    """
    reads = {"n": 0}

    async def receive():
        reads["n"] += 1
        return {"type": "http.request", "body": b"{}", "more_body": False}

    status, payload = await _put_raw(
        client.app,
        [
            (b"host", b"127.0.0.1"),
            (b"content-type", b"application/json"),
            (b"content-length", "²".encode("latin-1")),
        ],
        receive,
    )
    assert status == 413
    assert json.loads(payload) == {"detail": "Score weights are too large"}
    assert "²".encode() not in payload
    assert reads["n"] == 0


@pytest.mark.asyncio
async def test_a_body_of_exactly_16_kib_is_accepted(client):
    """16 KiB is the largest body. One more byte is 413."""
    inner = '"profitability":1,"valuation":1,"balance_sheet":1,"growth":1'
    pad = (16 * 1024) - len(('{"weights":{' + inner + "}}").encode())
    exact = '{"weights":{' + (" " * pad) + inner + "}}"
    assert len(exact.encode()) == 16 * 1024
    ok = await client.put(
        "/api/v1/score-weights/STOCK",
        content=exact.encode(),
        headers={"content-type": "application/json"},
    )
    assert ok.status_code == 200
    assert ok.json()["stored"] is True
    over = exact.encode() + b" "
    rejected = await client.put(
        "/api/v1/score-weights/STOCK",
        content=over,
        headers={"content-type": "application/json"},
    )
    assert rejected.status_code == 413
    assert rejected.json() == {"detail": "Score weights are too large"}


@pytest.mark.asyncio
async def test_a_score_id_that_is_not_a_number_is_422(client):
    response = await client.get("/api/v1/instruments/abc/score")
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", "instrument_id"]


def _quiet(client):
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=client.app, raise_app_exceptions=False)
    return AsyncClient(transport=transport, base_url="http://127.0.0.1")


@pytest.mark.asyncio
async def test_put_rejects_bad_bytes_a_huge_integer_and_an_oversize_body(
    client,
):
    """A bad body is 422 or 413. It is not a 500, and it quotes nothing.

    Invalid UTF-8 and an integer of more than 4300 digits both make
    ``json.loads`` raise ``ValueError`` (``UnicodeDecodeError`` is a
    ``ValueError``). A body over 16 KiB is 413 before it is parsed.
    A nested array deep enough to overflow the parser is the same 422.
    """
    url = "/api/v1/score-weights/STOCK"
    huge = (
        '{"weights":{"profitability":'
        + ("1" * 5000)
        + ',"valuation":1,"balance_sheet":1,"growth":1}}'
    )
    assert len(huge.encode()) < 16 * 1024
    deep = "[" * 2000 + "]" * 2000
    assert len(deep.encode()) < 16 * 1024
    cases = [
        (b"\xff", 422, "Score weights must be an object"),
        (huge.encode(), 422, "Score weights must be an object"),
        (b"x" * (16 * 1024 + 1), 413, "Score weights are too large"),
        (deep.encode(), 422, "Score weights must be an object"),
    ]
    async with _quiet(client) as quiet:
        for content, status, detail in cases:
            response = await quiet.put(
                url,
                content=content,
                headers={"content-type": "application/json"},
            )
            assert response.status_code == status
            assert response.json() == {"detail": detail}
            text = response.text
            assert "UnicodeDecode" not in text
            assert "RecursionError" not in text
            assert "Exceeds the limit" not in text


def test_put_score_weights_is_a_sync_function():
    """The route runs SQLAlchemy. It must not be an async endpoint."""
    import inspect

    from app.api.scores import put_score_weights

    assert not inspect.iscoroutinefunction(put_score_weights)


# What a score request on 2026-11-18 should report for demo-v2.
# Prices end on 2026-09-28 (51 days earlier). Statements used here
# are the 2025 annual ratios. TER is missing only on DEMO_ETF_GPW.
LIVE_ON = date(2026, 11, 18)
LIVE_COVERAGE = {
    "DEMO_PL_TECH": ("scored", "4 of 4"),
    "DEMO_US_GROWTH": ("scored", "4 of 4"),
    "DEMO_DE_INDUSTRY": ("scored", "4 of 4"),
    "DEMO_JP_STABLE": ("scored", "4 of 4"),
    "DEMO_SG_EARLY": ("scored", "3 of 4"),
    "DEMO_PL_EMPTY": ("no_score", "0 of 4"),
    "DEMO_ETF_WORLD": ("scored", "4 of 4"),
    "DEMO_ETF_GPW": ("scored", "3 of 4"),
    "DEMO_ETC_GOLD": ("scored", "4 of 4"),
    "DEMO_ETC_SILVER": ("scored", "4 of 4"),
}


@pytest.mark.asyncio
async def test_demo_v2_scores_on_a_date_after_the_fixture(client, monkeypatch):
    """18 November 2026 is not the fixture date of 30 September.

    The clock is not frozen on the fixture as-of date. Stocks carry
    the collector ratios, and the one-year price figures are still
    inside their freshness window, so the funds are not reduced to
    cost and size alone.
    """
    monkeypatch.setattr(scores_api, "utc_today", lambda: LIVE_ON)
    fixture = json.loads(
        Path("fixtures/demo-v2.json").read_text(encoding="utf-8")
    )
    session = _session(client)
    ids = {}
    try:
        for entry in fixture["companies"]:
            company = CompanyRepository(session).create(
                CompanyCreate(**entry["company"]),
                record_source=RECORD_SOURCE_DEMO,
                is_synthetic=True,
            )
            ids[company.ticker] = company.id
            if entry["attributes"] is not None:
                attributes = dict(entry["attributes"])
                attributes.pop("source", None)
                FundAttributesRepository(session).create(
                    company.id,
                    attributes,
                    record_source=RECORD_SOURCE_DEMO,
                    is_synthetic=True,
                )
            if entry["metrics"]:
                for row in entry["metrics"]:
                    moment = datetime.fromisoformat(
                        row["period_end"].replace("Z", "+00:00")
                    )
                    fields = {
                        key: value
                        for key, value in row.items()
                        if key not in ("period_end", "period_type")
                    }
                    _metric(
                        session,
                        company.id,
                        moment,
                        row["period_type"],
                        **fields,
                    )
            if entry["prices"]:
                PriceBarRepository(session).upsert_many(
                    company.id,
                    [PriceBarCreate(**row) for row in entry["prices"]],
                )
    finally:
        session.close()
    found = {}
    for ticker, instrument_id in ids.items():
        response = await client.get(
            f"/api/v1/instruments/{instrument_id}/score"
        )
        assert response.status_code == 200
        body = response.json()
        found[ticker] = (body["status"], body["coverage"]["label"])
        assert body["scored_on"] == LIVE_ON.isoformat()
    assert found == LIVE_COVERAGE


@pytest.mark.asyncio
async def test_a_deep_stored_weight_row_is_a_fixed_500(client):
    """``json.loads`` of a 10000-deep array raises ``RecursionError``."""
    raw = "[" * 10000 + "]" * 10000
    session = _session(client)
    try:
        session.add(
            ScoreWeightsDB(
                instrument_type="STOCK",
                version=2,
                weights=raw,
            )
        )
        session.commit()
    finally:
        session.close()
    async with _quiet(client) as quiet:
        response = await quiet.get("/api/v1/score-weights/STOCK")
    assert response.status_code == 500
    assert response.json() == {"detail": "Score weights could not be read"}
    assert "RecursionError" not in response.text
    assert "Internal Server Error" not in response.text
