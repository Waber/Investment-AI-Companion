"""Pins for bugs that were open on master.

The period_end case (#20) treats the same instant with another UTC
offset as a duplicate. The PostgreSQL run of that case is
``tests/integration/test_postgres.py`` (issue #9).

The fetch-company 500 (#18) returns a fixed detail and logs the
exception with the ticker. ``debt_to_assets`` (#21) is total debt
divided by total assets when both numbers are already on the provider
info, and None otherwise. It is never a per-share amount. Issue #19
is not covered here.
"""

import logging

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


@pytest.mark.asyncio
async def test_fetch_company_500_does_not_leak_exception_text(client):
    client.app.dependency_overrides[get_yahoo_finance_collector] = (
        lambda: FakeCollector(RuntimeError("password=hunter2"))
    )

    response = await client.post(FETCH, json={"ticker": "FAIL"})

    assert response.status_code == 500
    assert "hunter2" not in response.text


class NullCollector:
    """Provider stand-in that has no company payload (the 404 path)."""

    def fetch_company_info(self, ticker):
        return None


class _Ticker:
    """yfinance.Ticker stand-in whose info only has a per-share debt field."""

    def __init__(self, symbol):
        self.info = {"totalDebtPerShare": 7.5}


class _InfoTicker:
    """yfinance.Ticker stand-in. Tests set ``info`` before patching."""

    info = {}

    def __init__(self, symbol):
        self.info = dict(self.info)


def test_debt_to_assets_is_not_debt_per_share(monkeypatch):
    monkeypatch.setattr(yahoo_finance.yf, "Ticker", _Ticker)

    metrics = YahooFinanceCollector().fetch_key_metrics("AAPL")

    assert metrics["debt_to_assets"] is None


@pytest.mark.asyncio
async def test_fetch_company_500_logs_exception_with_ticker(client, caplog):
    """The 500 is logged with the ticker, and the body stays generic.

    ``logger.exception`` attaches the traceback, so the secret stays in
    the server log and is not copied into the HTTP detail.
    """
    client.app.dependency_overrides[get_yahoo_finance_collector] = (
        lambda: FakeCollector(RuntimeError("password=hunter2"))
    )

    with caplog.at_level(logging.ERROR, logger="app.api.data_collection"):
        response = await client.post(FETCH, json={"ticker": "fail"})

    assert response.status_code == 500
    assert "FAIL" in caplog.text
    assert any(
        record.exc_info is not None and record.exc_info[0] is RuntimeError
        for record in caplog.records
    )
    assert response.json()["detail"] == "Error fetching company data"
    assert "hunter2" not in response.text


@pytest.mark.asyncio
async def test_fetch_company_404_and_400_stay_unchanged(client):
    """No provider data stays 404. A ValueError stays 400 with its text."""
    client.app.dependency_overrides[get_yahoo_finance_collector] = (
        lambda: NullCollector()
    )
    missing = await client.post(FETCH, json={"ticker": "miss"})
    assert missing.status_code == 404
    assert missing.json()["detail"] == (
        "Company with ticker MISS not found on Yahoo Finance"
    )

    client.app.dependency_overrides[get_yahoo_finance_collector] = (
        lambda: FakeCollector(
            ValueError("Company name or ticker already exists")
        )
    )
    conflict = await client.post(FETCH, json={"ticker": "dupe"})
    assert conflict.status_code == 400
    assert conflict.json()["detail"] == (
        "Company name or ticker already exists"
    )


def _patch_info(monkeypatch, info):
    # setattr restores the class attribute after the test. Assigning
    # _InfoTicker.info directly would leak into the next test.
    monkeypatch.setattr(_InfoTicker, "info", info)
    monkeypatch.setattr(yahoo_finance.yf, "Ticker", _InfoTicker)


@pytest.mark.parametrize(
    ("total_debt", "total_assets", "expected"),
    [
        (50, 200, 0.25),
        (0, 200, 0.0),
    ],
)
def test_debt_to_assets_is_total_debt_over_total_assets(
    monkeypatch, total_debt, total_assets, expected
):
    """The ratio is total debt / total assets, never the per-share figure.

    ``totalDebtPerShare`` is left in the payload as a decoy. The mapping
    ignores it.
    """
    _patch_info(
        monkeypatch,
        {
            "totalDebt": total_debt,
            "totalAssets": total_assets,
            "totalDebtPerShare": 7.5,
        },
    )

    metrics = YahooFinanceCollector().fetch_key_metrics("AAPL")

    assert metrics["debt_to_assets"] == expected


@pytest.mark.parametrize(
    "info",
    [
        {"totalDebtPerShare": 7.5},
        {"totalDebt": 50, "totalDebtPerShare": 7.5},
        {"totalAssets": 200, "totalDebtPerShare": 7.5},
        {"totalDebt": 50, "totalAssets": 0, "totalDebtPerShare": 7.5},
        {
            "totalDebt": "50",
            "totalAssets": "200",
            "totalDebtPerShare": 7.5,
        },
        {"totalDebt": True, "totalAssets": 200, "totalDebtPerShare": 7.5},
        {"totalDebt": 50, "totalAssets": False, "totalDebtPerShare": 7.5},
        {
            "totalDebt": float("nan"),
            "totalAssets": 200,
            "totalDebtPerShare": 7.5,
        },
        {
            "totalDebt": 50,
            "totalAssets": float("nan"),
            "totalDebtPerShare": 7.5,
        },
        {
            "totalDebt": float("inf"),
            "totalAssets": 200,
            "totalDebtPerShare": 7.5,
        },
        {
            "totalDebt": 50,
            "totalAssets": float("inf"),
            "totalDebtPerShare": 7.5,
        },
        {
            "totalDebt": 50,
            "totalAssets": -200,
            "totalDebtPerShare": 7.5,
        },
        {
            "totalDebt": -10,
            "totalAssets": 200,
            "totalDebtPerShare": 7.5,
        },
    ],
    ids=[
        "per_share_only",
        "debt_only",
        "assets_only",
        "zero_assets",
        "non_numeric",
        "bool_debt",
        "bool_assets",
        "nan_debt",
        "nan_assets",
        "inf_debt",
        "inf_assets",
        "negative_assets",
        "negative_debt",
    ],
)
def test_debt_to_assets_is_none_when_inputs_are_missing(monkeypatch, info):
    """Missing or unusable totals are None, not per-share debt.

    Each payload still carries ``totalDebtPerShare``. Assets that are
    zero or negative cannot be a denominator. Strings, booleans, NaN,
    and infinity are not amounts. Negative debt is not a ratio input.
    """
    _patch_info(monkeypatch, info)

    metrics = YahooFinanceCollector().fetch_key_metrics("AAPL")

    assert metrics is not None
    assert metrics["debt_to_assets"] is None


def test_debt_to_assets_overflow_keeps_the_other_metrics(monkeypatch):
    """A huge int must not raise and wipe the metrics dict.

    ``10**400`` cannot be converted to float. The ratio is None and
    the other fields from the same payload are still returned.
    """
    _patch_info(
        monkeypatch,
        {
            "totalDebt": 10**400,
            "totalAssets": 1,
            "totalDebtPerShare": 7.5,
            "trailingPE": 12.5,
        },
    )

    metrics = YahooFinanceCollector().fetch_key_metrics("AAPL")

    assert metrics is not None
    assert metrics["debt_to_assets"] is None
    assert metrics["pe_ratio"] == 12.5


def test_debt_to_assets_accepts_numpy_reals(monkeypatch):
    """NumPy integers and floats are real numbers, not missing data."""
    numpy = pytest.importorskip("numpy")
    _patch_info(
        monkeypatch,
        {
            "totalDebt": numpy.int64(50),
            "totalAssets": numpy.float64(200),
            "totalDebtPerShare": 7.5,
            "trailingPE": 30.1,
        },
    )

    metrics = YahooFinanceCollector().fetch_key_metrics("AAPL")

    assert metrics is not None
    assert metrics["debt_to_assets"] == 0.25
    assert metrics["pe_ratio"] == 30.1
