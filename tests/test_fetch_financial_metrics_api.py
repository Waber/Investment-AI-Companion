"""POST /data-collection/fetch-financial-metrics stores one TTM row.

A stub collector replaces Yahoo, so no test touches the network.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.api.data_collection import get_collector
from app.data_collectors.base import Provenance, ProviderError, Sourced
from app.models.database_models import FinancialMetricsDB

URL = "/api/v1/data-collection/fetch-financial-metrics"
FULL = {
    "pe_ratio": 20.0,
    "pb_ratio": 3.0,
    "ev_ebitda": 12.0,
    "roe": 0.10,
    "roa": 0.05,
    "profit_margin": 0.20,
    "gross_margin": 0.40,
    "revenue_growth": 0.05,
    "current_ratio": 1.25,
    "quick_ratio": 1.0,
    "debt_to_equity": 100.0,
}
RETRIEVED = datetime(2026, 11, 1, tzinfo=timezone.utc)


class StubCollector:
    """Returns a fixed snapshot, or raises the given exception."""

    def __init__(
        self,
        values=FULL,
        as_of=date(2026, 9, 30),
        source="yahoo_finance",
        error=None,
        empty=False,
    ):
        self.values = values
        self.as_of = as_of
        self.source = source
        self.error = error
        self.empty = empty

    def fetch_key_metrics(self, ticker):
        if self.error:
            raise self.error
        if self.empty:
            return None
        return Sourced(
            value=dict(self.values),
            provenance=Provenance(
                source=self.source, retrieved_at=RETRIEVED, as_of=self.as_of
            ),
        )


def use(client, **kwargs):
    stub = StubCollector(**kwargs)
    client.app.dependency_overrides[get_collector] = lambda: stub


async def make_company(client, ticker="AAPL", instrument_type="STOCK"):
    response = await client.post(
        "/api/v1/companies/",
        json={
            "name": ticker,
            "ticker": ticker,
            "instrument_type": instrument_type,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def rows(client, company_id):
    response = await client.get(
        f"/api/v1/financial-metrics/company/{company_id}"
    )
    assert response.status_code == 200
    return response.json()


def stored_sources(client, company_id):
    """Read ``source`` from the database: the API model does not show it."""
    with client.app.state.testing_session_local() as db:
        found = db.query(FinancialMetricsDB).filter_by(company_id=company_id)
        return [row.source for row in found]


@pytest.mark.asyncio
async def test_full_snapshot_is_stored_and_scores_four_of_four(client):
    company_id = await make_company(client)
    # The score has a 548-day freshness window, so date the snapshot
    # relative to today instead of a fixed date.
    recent = datetime.now(timezone.utc).date() - timedelta(days=30)
    use(client, as_of=recent)

    response = await client.post(URL, json={"ticker": "AAPL"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["period_type"] == "ttm"
    assert body["period_end"].startswith(f"{recent.isoformat()}T00:00:00")
    # Every stored column as a literal, so a column typo cannot hide.
    assert body["roe"] == 0.10
    assert body["roa"] == 0.05
    assert body["gross_margin"] == 0.40
    assert body["net_margin"] == 0.20
    assert body["current_ratio"] == 1.25
    assert body["quick_ratio"] == 1.0
    assert body["debt_to_equity"] == 100.0
    assert body["debt_to_assets"] is None
    assert body["revenue_growth"] == 0.05
    assert body["pe_ratio"] == 20.0
    assert body["pb_ratio"] == 3.0
    assert body["ev_ebitda"] == 12.0
    assert stored_sources(client, company_id) == ["yahoo_finance"]
    score = await client.get(f"/api/v1/instruments/{company_id}/score")
    assert score.status_code == 200
    assert score.json()["coverage"]["label"] == "4 of 4"


@pytest.mark.asyncio
async def test_lowercase_ticker_is_accepted(client):
    await make_company(client)
    use(client)
    response = await client.post(URL, json={"ticker": "aapl"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_same_quarter_refreshes_the_one_row(client):
    company_id = await make_company(client)
    use(client)
    await client.post(URL, json={"ticker": "AAPL"})
    use(client, values={**FULL, "roe": 0.5})

    response = await client.post(URL, json={"ticker": "AAPL"})

    assert response.status_code == 200
    stored = await rows(client, company_id)
    assert len(stored) == 1
    assert stored[0]["roe"] == 0.5


@pytest.mark.asyncio
async def test_an_unchanged_refresh_still_moves_updated_at(client):
    # updated_at is the stored refresh time, so it must move even when
    # every value is the same.
    company_id = await make_company(client)
    use(client)
    await client.post(URL, json={"ticker": "AAPL"})
    first = (await rows(client, company_id))[0]["updated_at"]

    await client.post(URL, json={"ticker": "AAPL"})

    second = (await rows(client, company_id))[0]["updated_at"]
    assert datetime.fromisoformat(second) > datetime.fromisoformat(first)


@pytest.mark.asyncio
async def test_new_quarter_adds_a_second_row(client):
    company_id = await make_company(client)
    use(client)
    await client.post(URL, json={"ticker": "AAPL"})
    use(client, as_of=date(2026, 12, 31))

    response = await client.post(URL, json={"ticker": "AAPL"})

    assert response.status_code == 200
    assert len(await rows(client, company_id)) == 2


@pytest.mark.asyncio
async def test_manual_row_on_the_same_key_is_409_and_unchanged(client):
    company_id = await make_company(client)
    manual = await client.post(
        "/api/v1/financial-metrics/",
        json={
            "company_id": company_id,
            "period_end": "2026-09-30T00:00:00Z",
            "period_type": "ttm",
            "roe": 0.01,
        },
    )
    assert manual.status_code == 201, manual.text
    use(client)

    response = await client.post(URL, json={"ticker": "AAPL"})

    assert response.status_code == 409
    stored = await rows(client, company_id)
    assert len(stored) == 1
    assert stored[0]["roe"] == 0.01
    assert stored_sources(client, company_id) == ["manual"]


@pytest.mark.asyncio
async def test_unknown_company_is_404(client):
    use(client)
    response = await client.post(URL, json={"ticker": "NOPE"})
    assert response.status_code == 404
    assert "Fetch the company first." in response.json()["detail"]


@pytest.mark.asyncio
async def test_etf_is_400(client):
    await make_company(client, "VWCE", "ETF")
    use(client)
    response = await client.post(URL, json={"ticker": "VWCE"})
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Financial metrics are collected for stocks only"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"empty": True},
        {"as_of": None},
        {"values": {k: None for k in FULL}},
    ],
    ids=["nothing", "no-as-of", "no-score-figures"],
)
async def test_no_usable_data_is_404_and_stores_nothing(client, kwargs):
    company_id = await make_company(client)
    use(client, **kwargs)

    response = await client.post(URL, json={"ticker": "AAPL"})

    assert response.status_code == 404
    assert await rows(client, company_id) == []


@pytest.mark.asyncio
async def test_nan_bool_and_huge_int_are_stored_as_none(client):
    company_id = await make_company(client)
    # 10**400 is too big for a float; it must not fail the whole fetch.
    use(
        client,
        values={
            **FULL,
            "pe_ratio": float("nan"),
            "roe": True,
            "ev_ebitda": 10**400,
        },
    )

    response = await client.post(URL, json={"ticker": "AAPL"})

    assert response.status_code == 200
    stored = (await rows(client, company_id))[0]
    assert stored["pe_ratio"] is None
    assert stored["roe"] is None
    assert stored["ev_ebitda"] is None
    assert stored["roa"] == 0.05


@pytest.mark.asyncio
async def test_provider_error_is_502_without_provider_text(client, caplog):
    await make_company(client)
    use(client, error=ProviderError("secret text"))

    response = await client.post(URL, json={"ticker": "AAPL"})

    assert response.status_code == 502
    assert response.json() == {"detail": "Data provider error"}
    assert "secret text" not in response.text
    assert "secret text" not in caplog.text


@pytest.mark.asyncio
async def test_unknown_provenance_source_is_502_and_stores_nothing(client):
    company_id = await make_company(client)
    use(client, source="stub")

    response = await client.post(URL, json={"ticker": "AAPL"})

    assert response.status_code == 502
    assert response.json() == {"detail": "Data provider error"}
    assert await rows(client, company_id) == []
