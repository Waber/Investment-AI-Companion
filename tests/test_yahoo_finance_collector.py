"""YahooFinanceCollector unit tests with a fake yfinance Ticker.

No network: every test replaces yfinance.Ticker for the module under test.
"""

import logging

import pandas as pd
import pytest

from app.data_collectors import yahoo_finance
from app.data_collectors.yahoo_finance import YahooFinanceCollector

STATEMENT_ATTRIBUTES = {
    "income_statement": "financials",
    "balance_sheet": "balance_sheet",
    "cash_flow": "cashflow",
    "quarterly_income": "quarterly_financials",
    "quarterly_balance": "quarterly_balance_sheet",
    "quarterly_cashflow": "quarterly_cashflow",
}


class FakeTicker:
    """Stands in for yfinance.Ticker. Attributes are set per test."""

    def __init__(self, symbol, **attributes):
        self.symbol = symbol
        self.history_calls = []
        self._history = attributes.pop("history_frame", pd.DataFrame())
        for name, value in attributes.items():
            setattr(self, name, value)

    def history(self, period, interval):
        self.history_calls.append((period, interval))
        return self._history


class ExplodingTicker:
    """Every data attribute raises, like a network or parsing failure."""

    def __init__(self, symbol):
        self.symbol = symbol

    def __getattr__(self, name):
        raise RuntimeError(f"provider failure reading {name}")


@pytest.fixture
def install_ticker(monkeypatch):
    created = []

    def install(**attributes):
        def factory(symbol):
            ticker = FakeTicker(symbol, **attributes)
            created.append(ticker)
            return ticker

        monkeypatch.setattr(yahoo_finance.yf, "Ticker", factory)
        return created

    return install


@pytest.fixture
def exploding_ticker(monkeypatch):
    monkeypatch.setattr(yahoo_finance.yf, "Ticker", ExplodingTicker)


@pytest.fixture
def collector():
    return YahooFinanceCollector()


# company-shaped pin, see #26
def test_company_info_maps_provider_fields(install_ticker, collector):
    created = install_ticker(
        info={
            "longName": "Apple Inc.",
            "shortName": "Apple",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "longBusinessSummary": "Designs devices.",
            "website": "https://www.apple.com",
            "country": "United States",
            "exchange": "NMS",
            "currency": "USD",
            "marketCap": 3_000_000_000_000,
            "fullTimeEmployees": 161000,
        }
    )

    info = collector.fetch_company_info("aapl")

    assert created[0].symbol == "aapl"
    assert info["name"] == "Apple Inc."
    assert info["ticker"] == "AAPL"
    assert info["sector"] == "Technology"
    assert info["industry"] == "Consumer Electronics"
    assert info["description"] == "Designs devices."
    assert info["website"] == "https://www.apple.com"
    assert info["country"] == "United States"
    assert info["exchange"] == "NMS"
    assert info["market_cap"] == 3_000_000_000_000
    assert info["employees"] == 161000
    assert info["founded"] is None
    assert info["logo_url"] is None


# company-shaped pin, see #26
def test_company_info_falls_back_to_short_name_and_usd(
    install_ticker, collector
):
    install_ticker(info={"shortName": "Short Co"})

    info = collector.fetch_company_info("shrt")

    assert info["name"] == "Short Co"
    assert info["currency"] == "USD"


def test_company_info_returns_none_and_logs_on_provider_error(
    exploding_ticker, collector, caplog
):
    with caplog.at_level(logging.ERROR, logger=yahoo_finance.__name__):
        assert collector.fetch_company_info("FAIL") is None

    assert "Error fetching company info for 'FAIL'" in caplog.text


def test_historical_data_passes_period_and_interval(install_ticker, collector):
    frame = pd.DataFrame({"Close": [1.0, 2.0]})
    created = install_ticker(history_frame=frame)

    result = collector.fetch_historical_data(
        "MSFT", period="5d", interval="1h"
    )

    assert result is frame
    assert created[0].history_calls == [("5d", "1h")]


def test_historical_data_uses_one_year_daily_by_default(
    install_ticker, collector
):
    created = install_ticker(history_frame=pd.DataFrame({"Close": [1.0]}))

    collector.fetch_historical_data("MSFT")

    assert created[0].history_calls == [("1y", "1d")]


def test_historical_data_returns_none_when_empty(install_ticker, collector):
    install_ticker(history_frame=pd.DataFrame())

    assert collector.fetch_historical_data("EMPTY") is None


def test_historical_data_returns_none_on_provider_error(
    exploding_ticker, collector
):
    assert collector.fetch_historical_data("FAIL") is None


# company-shaped pin, see #26
def test_financial_statements_return_all_six_frames(install_ticker, collector):
    frames = {
        attribute: pd.DataFrame({attribute: [1]})
        for attribute in STATEMENT_ATTRIBUTES.values()
    }
    install_ticker(**frames)

    statements = collector.fetch_financial_statements("MSFT")

    assert set(STATEMENT_ATTRIBUTES) <= set(statements)
    for key, attribute in STATEMENT_ATTRIBUTES.items():
        assert statements[key] is frames[attribute]


def test_financial_statements_return_none_on_provider_error(
    exploding_ticker, collector
):
    assert collector.fetch_financial_statements("FAIL") is None


# company-shaped pin, see #26
def test_key_metrics_map_ratios_from_provider_info(install_ticker, collector):
    install_ticker(
        info={
            "trailingPE": 30.1,
            "forwardPE": 27.5,
            "priceToBook": 45.2,
            "priceToSalesTrailing12Months": 7.9,
            "enterpriseToEbitda": 22.4,
            "enterpriseToRevenue": 7.7,
            "returnOnEquity": 1.56,
            "returnOnAssets": 0.28,
            "profitMargins": 0.25,
            "operatingMargins": 0.30,
            "grossMargins": 0.44,
            "revenueGrowth": 0.05,
            "earningsGrowth": 0.11,
            "earningsQuarterlyGrowth": 0.12,
            "currentRatio": 0.99,
            "quickRatio": 0.84,
            "debtToEquity": 181.3,
            "dividendYield": 0.005,
            "payoutRatio": 0.15,
            "dividendRate": 0.96,
            "beta": 1.29,
            "fiftyTwoWeekHigh": 199.6,
            "fiftyTwoWeekLow": 164.1,
            "averageVolume": 58_000_000,
            "marketCap": 3_000_000_000_000,
        }
    )

    metrics = collector.fetch_key_metrics("AAPL")

    # This fixture has no totalDebt or totalAssets, so the ratio is
    # None (issue #21). It must not fall back to a per-share field.
    assert metrics["debt_to_assets"] is None
    expected = {
        "pe_ratio": 30.1,
        "forward_pe": 27.5,
        "pb_ratio": 45.2,
        "ps_ratio": 7.9,
        "ev_ebitda": 22.4,
        "ev_revenue": 7.7,
        "roe": 1.56,
        "roa": 0.28,
        "profit_margin": 0.25,
        "operating_margin": 0.30,
        "gross_margin": 0.44,
        "revenue_growth": 0.05,
        "earnings_growth": 0.11,
        "earnings_quarterly_growth": 0.12,
        "current_ratio": 0.99,
        "quick_ratio": 0.84,
        "debt_to_equity": 181.3,
        "dividend_yield": 0.005,
        "payout_ratio": 0.15,
        "dividend_rate": 0.96,
        "beta": 1.29,
        "52_week_high": 199.6,
        "52_week_low": 164.1,
        "avg_volume": 58_000_000,
        "market_cap": 3_000_000_000_000,
    }
    for key, value in expected.items():
        assert metrics[key] == value, key


def test_key_metrics_are_none_when_provider_omits_them(
    install_ticker, collector
):
    install_ticker(info={})

    metrics = collector.fetch_key_metrics("BARE")

    assert metrics["pe_ratio"] is None
    assert metrics["market_cap"] is None


def test_key_metrics_return_none_on_provider_error(
    exploding_ticker, collector
):
    assert collector.fetch_key_metrics("FAIL") is None


def test_news_is_limited(install_ticker, collector):
    install_ticker(news=[{"title": f"n{i}"} for i in range(5)])

    news = collector.fetch_news("AAPL", limit=2)

    assert news == [{"title": "n0"}, {"title": "n1"}]


@pytest.mark.parametrize("provider_news", [None, []])
def test_news_is_empty_list_when_provider_has_none(
    install_ticker, collector, provider_news
):
    install_ticker(news=provider_news)

    assert collector.fetch_news("AAPL") == []


def test_news_returns_none_on_provider_error(exploding_ticker, collector):
    assert collector.fetch_news("FAIL") is None


def test_recommendations_return_frame(install_ticker, collector):
    frame = pd.DataFrame({"strongBuy": [10]})
    install_ticker(recommendations=frame)

    assert collector.fetch_recommendations("AAPL") is frame


@pytest.mark.parametrize("provider_value", [None, pd.DataFrame()])
def test_recommendations_return_none_when_missing_or_empty(
    install_ticker, collector, provider_value
):
    install_ticker(recommendations=provider_value)

    assert collector.fetch_recommendations("AAPL") is None


def test_recommendations_return_none_on_provider_error(
    exploding_ticker, collector
):
    assert collector.fetch_recommendations("FAIL") is None
