"""Known-defect pins.

The period_end case (#20) is fixed: the same instant with another UTC
offset is a duplicate. PostgreSQL coverage of that case waits for
issue #9.

``test_fetch_company_500_does_not_leak_exception_text`` (#18) and
``test_debt_to_assets_is_not_debt_per_share`` (#21) are QA's strict
xfails. ``strict=True`` turns an unexpected pass into a failure, so
the fix commit deletes the markers. Issue #19 is not covered here.
"""

import pytest

from app.api.data_collection import get_yahoo_finance_collector
from app.data_collectors import yahoo_finance
from app.data_collectors.yahoo_finance import YahooFinanceCollector

COMPANIES = "/api/v1/companies/"
METRICS = "/api/v1/financial-metrics/"
FETCH = "/api/v1/data-collection/fetch-company"


class FakeCollector:
    """Stand-in for YahooFinanceCollector on the fetch-company route.

    Pass ``error`` to raise from ``fetch_company_info``. Otherwise the
    method returns a small company dict and does not touch the network.
    """

    def __init__(self, error=None):
        self.error = error

    def fetch_company_info(self, ticker):
        if self.error:
            raise self.error
        return {"name": f"Fetched {ticker}", "currency": "USD"}


@pytest.mark.asyncio
async def test_same_instant_with_other_offset_is_a_duplicate(client):
    company = (
        await client.post(COMPANIES, json={"name": "TZ", "ticker": "TZCO"})
    ).json()
    base = {"company_id": company["id"], "period_type": "annual"}
    first = await client.post(
        METRICS, json={**base, "period_end": "2025-12-31T00:00:00Z"}
    )
    assert first.status_code == 201

    response = await client.post(
        METRICS, json={**base, "period_end": "2025-12-31T02:00:00+02:00"}
    )

    assert response.status_code == 400


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="fetch-company 500 echoes the exception text (issue #18)",
)
@pytest.mark.asyncio
async def test_fetch_company_500_does_not_leak_exception_text(client):
    client.app.dependency_overrides[
        get_yahoo_finance_collector
    ] = lambda: FakeCollector(RuntimeError("password=hunter2"))

    response = await client.post(FETCH, json={"ticker": "FAIL"})

    assert response.status_code == 500
    assert "hunter2" not in response.text


class _Ticker:
    """yfinance.Ticker stand-in whose info only has a per-share debt field."""

    def __init__(self, symbol):
        self.info = {"totalDebtPerShare": 7.5}


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="debt_to_assets is read from totalDebtPerShare (issue #21)",
)
def test_debt_to_assets_is_not_debt_per_share(monkeypatch):
    monkeypatch.setattr(yahoo_finance.yf, "Ticker", _Ticker)

    metrics = YahooFinanceCollector().fetch_key_metrics("AAPL")

    assert metrics["debt_to_assets"] != 7.5
