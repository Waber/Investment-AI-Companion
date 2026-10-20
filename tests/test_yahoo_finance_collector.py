"""YahooFinanceCollector unit tests with a fake yfinance Ticker.

No network: every test replaces yfinance.Ticker for the module under test.
"""

import logging
import time
from datetime import date, datetime, timezone

import pandas as pd
import pytest

from app.data_collectors import yahoo_finance
from app.data_collectors.base import (
    COMPANY_INFO_FIELDS,
    KEY_METRIC_FIELDS,
    Fundamentals,
    FundAttributes,
    InstrumentLookup,
    PriceBar,
    PriceHistory,
    ProviderError,
    TransientProviderError,
)
from app.data_collectors.guard import GuardPolicy, guard_collector
from app.data_collectors.yahoo_finance import YahooFinanceCollector
from tests.collector_stubs import FakeClock

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
        self.timeouts = []
        self._history = attributes.pop("history_frame", pd.DataFrame())
        for name, value in attributes.items():
            setattr(self, name, value)

    def history(self, period, interval, timeout=None, **_ignored):
        self.history_calls.append((period, interval))
        self.timeouts.append(timeout)
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


NOW = datetime(2026, 5, 6, 7, 8, 9, tzinfo=timezone.utc)


@pytest.fixture
def collector():
    return YahooFinanceCollector(clock=lambda: NOW)


def assert_provider_error(call):
    """The call raises ProviderError and keeps the original as the cause."""
    with pytest.raises(ProviderError) as caught:
        call()
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert "provider failure" in str(caught.value.__cause__)
    # The wrapper's own text is fixed; the provider text is only the cause.
    assert "provider failure" not in str(caught.value)


def test_collector_implements_the_capabilities_yahoo_can_serve(collector):
    assert isinstance(collector, InstrumentLookup)
    assert isinstance(collector, PriceHistory)
    assert isinstance(collector, Fundamentals)
    assert not isinstance(collector, FundAttributes)


def test_default_clock_is_timezone_aware_utc(install_ticker):
    install_ticker(info={"longName": "Apple Inc."})

    result = YahooFinanceCollector().fetch_company_info("AAPL")

    assert result.provenance.retrieved_at.utcoffset().total_seconds() == 0


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

    result = collector.fetch_company_info("aapl")
    info = result.value

    # normalize_ticker runs before yf.Ticker, so Yahoo sees AAPL.
    assert created[0].symbol == "AAPL"
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

    info = collector.fetch_company_info("shrt").value

    assert info["name"] == "Short Co"
    assert info["currency"] == "USD"


def test_company_info_carries_provenance_and_the_shared_keys(
    install_ticker, collector
):
    install_ticker(info={"longName": "Apple Inc."})

    result = collector.fetch_company_info("AAPL")

    assert tuple(result.value) == COMPANY_INFO_FIELDS
    assert result.provenance.source == "yahoo_finance"
    assert result.provenance.as_of is None
    assert result.provenance.retrieved_at == NOW
    assert result.provenance.synthetic is False


def test_company_info_raises_provider_error_and_logs(
    exploding_ticker, collector, caplog
):
    with caplog.at_level(logging.ERROR, logger=yahoo_finance.__name__):
        assert_provider_error(lambda: collector.fetch_company_info("FAIL"))

    assert "Error fetching company info for 'FAIL'" in caplog.text


def test_historical_data_passes_period_and_interval(install_ticker, collector):
    frame = pd.DataFrame({"Close": [1.0, 2.0]})
    created = install_ticker(history_frame=frame)

    result = collector.fetch_historical_data(
        "MSFT", period="5d", interval="1h"
    )

    assert result is frame
    assert created[0].history_calls == [("5d", "1h")]
    assert created[0].timeouts == [yahoo_finance.YFINANCE_HTTP_TIMEOUT_SECONDS]


def test_historical_data_uses_one_year_daily_by_default(
    install_ticker, collector
):
    created = install_ticker(history_frame=pd.DataFrame({"Close": [1.0]}))

    collector.fetch_historical_data("MSFT")

    assert created[0].history_calls == [("1y", "1d")]


def test_historical_data_returns_none_when_empty(install_ticker, collector):
    install_ticker(history_frame=pd.DataFrame())

    assert collector.fetch_historical_data("EMPTY") is None


def test_historical_data_raises_provider_error(exploding_ticker, collector):
    assert_provider_error(lambda: collector.fetch_historical_data("FAIL"))


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


def test_financial_statements_raise_provider_error(
    exploding_ticker, collector
):
    assert_provider_error(lambda: collector.fetch_financial_statements("FAIL"))


# company-shaped pin, see #26
def test_key_metrics_map_ratios_from_provider_info(install_ticker, collector):
    install_ticker(
        info={
            "longName": "Apple Inc.",
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

    metrics = collector.fetch_key_metrics("AAPL").value

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
    install_ticker(info={"longName": "Apple Inc."})

    metrics = collector.fetch_key_metrics("BARE").value

    assert metrics["pe_ratio"] is None
    assert metrics["market_cap"] is None


def test_key_metrics_carry_provenance_and_the_shared_keys(
    install_ticker, collector
):
    install_ticker(info={"longName": "Apple Inc."})

    result = collector.fetch_key_metrics("BARE")

    assert tuple(result.value) == KEY_METRIC_FIELDS
    assert result.provenance.source == "yahoo_finance"
    assert result.provenance.as_of is None
    assert result.provenance.retrieved_at == NOW
    assert result.provenance.synthetic is False


@pytest.mark.parametrize("quote_type", ["ETF", "MUTUALFUND"])
def test_debt_to_assets_is_none_for_funds(
    install_ticker, collector, quote_type
):
    # For a fund, totalAssets is assets under management, not a balance
    # sheet total, so the ratio would be meaningless.
    install_ticker(
        info={
            "longName": "Some Fund",
            "quoteType": quote_type,
            "totalDebt": 10.0,
            "totalAssets": 100.0,
        }
    )

    metrics = collector.fetch_key_metrics("FUND").value

    assert metrics["debt_to_assets"] is None


def test_debt_to_assets_is_kept_for_equity(install_ticker, collector):
    install_ticker(
        info={
            "longName": "Apple Inc.",
            "quoteType": "EQUITY",
            "totalDebt": 10.0,
            "totalAssets": 100.0,
        }
    )

    assert collector.fetch_key_metrics("EQ").value["debt_to_assets"] == 0.1


def test_key_metrics_raise_provider_error(exploding_ticker, collector):
    assert_provider_error(lambda: collector.fetch_key_metrics("FAIL"))


def make_history():
    index = pd.to_datetime(["2026-01-02", "2026-01-05"])
    return pd.DataFrame(
        {
            "Open": [10.0, float("nan")],
            "High": [11.0, 13.0],
            "Low": [9.5, 12.0],
            "Close": [10.5, 12.5],
            "Volume": [1000, 2000],
        },
        index=index,
    )


def test_price_history_converts_rows_to_bars(install_ticker, collector):
    created = install_ticker(history_frame=make_history())

    result = collector.fetch_price_history("MSFT", period="5d", interval="1d")

    assert created[0].history_calls == [("5d", "1d")]
    assert result.value == [
        PriceBar(date(2026, 1, 2), 10.0, 11.0, 9.5, 10.5, 1000),
        PriceBar(date(2026, 1, 5), None, 13.0, 12.0, 12.5, 2000),
    ]
    assert result.provenance.source == "yahoo_finance"
    assert result.provenance.as_of == date(2026, 1, 5)
    assert result.provenance.retrieved_at == NOW
    assert result.provenance.synthetic is False
    assert isinstance(result.value[0].volume, int)


def test_price_history_volume_nan_is_none(install_ticker, collector):
    frame = make_history()
    frame["Volume"] = [float("nan"), 5.0]
    install_ticker(history_frame=frame)

    bars = collector.fetch_price_history("MSFT").value

    assert bars[0].volume is None
    assert bars[1].volume == 5


def test_price_history_is_none_for_empty_frame(install_ticker, collector):
    install_ticker(history_frame=pd.DataFrame())

    assert collector.fetch_price_history("EMPTY") is None


def test_price_history_raises_provider_error(exploding_ticker, collector):
    assert_provider_error(lambda: collector.fetch_price_history("FAIL"))


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


def test_news_raises_provider_error(exploding_ticker, collector):
    assert_provider_error(lambda: collector.fetch_news("FAIL"))


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


def test_recommendations_raise_provider_error(exploding_ticker, collector):
    assert_provider_error(lambda: collector.fetch_recommendations("FAIL"))


def test_price_history_raises_provider_error_for_unreadable_frame(
    install_ticker, collector
):
    # A frame without the OHLCV columns is a parse failure, not "no data".
    install_ticker(history_frame=pd.DataFrame({"Close": [1.0]}))

    with pytest.raises(ProviderError) as caught:
        collector.fetch_price_history("ODD")

    assert isinstance(caught.value.__cause__, KeyError)


def test_company_info_is_none_when_yfinance_returns_near_empty_info(
    install_ticker, collector
):
    # yfinance 1.7 sets hide_exceptions=True: an unknown ticker gives a
    # near-empty info dict instead of raising.
    install_ticker(info={"trailingPegRatio": None})

    assert collector.fetch_company_info("NOPE") is None


def test_company_info_naive_clock_is_a_value_error_not_provider_error(
    install_ticker,
):
    install_ticker(info={"longName": "Apple Inc."})
    naive = YahooFinanceCollector(clock=lambda: datetime(2026, 1, 1))

    with pytest.raises(ValueError):
        naive.fetch_company_info("AAPL")


def test_key_metrics_naive_clock_is_a_value_error_not_provider_error(
    install_ticker,
):
    install_ticker(info={"longName": "Apple Inc.", "trailingPE": 10.0})
    naive = YahooFinanceCollector(clock=lambda: datetime(2026, 1, 1))

    with pytest.raises(ValueError):
        naive.fetch_key_metrics("AAPL")


def test_key_metrics_are_none_when_yfinance_returns_near_empty_info(
    install_ticker, collector
):
    # Same yfinance 1.7 hide_exceptions case as for company info: an
    # all-None metrics dict would claim data that does not exist.
    install_ticker(info={"trailingPegRatio": None})

    assert collector.fetch_key_metrics("NOPE") is None


def test_yfinance_logs_do_not_keep_provider_text(caplog):
    """The yfinance logger is filtered. Its own lines can contain a URL."""
    caplog.set_level(logging.DEBUG)
    logging.getLogger("yfinance").error("token=%s", "hunter2")
    logging.getLogger("yfinance.scrapers").error(
        "url=%s", "https://secret.example/path"
    )

    assert "hunter2" not in caplog.text
    assert "secret.example" not in caplog.text
    assert "yfinance log redacted" in caplog.text


def test_history_timeout_uses_the_time_left_on_the_deadline(
    install_ticker, collector
):
    """A budget shorter than 10 s shrinks the history timeout."""
    from app.data_collectors.call_budget import pop_budget, push_budget

    created = install_ticker(history_frame=pd.DataFrame({"Close": [1.0]}))
    token = push_budget(time.monotonic() + 3, time.monotonic)
    try:
        collector.fetch_historical_data("MSFT")
    finally:
        pop_budget(token)

    assert created[0].timeouts[0] <= 3
    assert created[0].timeouts[0] > 0


def test_http_get_and_post_share_the_deadline(monkeypatch):
    """Chained HTTP calls inside one method use the time that is left."""
    from app.data_collectors.call_budget import pop_budget, push_budget
    from app.data_collectors.yahoo_finance import _install_http_cap

    seen = []

    class _Data:
        def get(self, url, params=None, timeout=30):
            seen.append(timeout)
            return {}

        def post(self, url, body=None, params=None, timeout=30, data=None):
            seen.append(timeout)
            return {}

    class _Stock:
        def __init__(self, symbol):
            self._data = _Data()
            self.info = {"longName": "Acme", "currency": "USD"}

    monkeypatch.setattr(yahoo_finance.yf, "Ticker", _Stock)
    token = push_budget(time.monotonic() + 4, time.monotonic)
    try:
        YahooFinanceCollector().fetch_company_info("ACME")
        stock = yahoo_finance.yf.Ticker("ACME")
        _install_http_cap(stock)
        stock._data.get("https://secret.example/quote", timeout=30)
        stock._data.post("https://secret.example/quote", timeout=30)
    finally:
        pop_budget(token)

    assert seen
    assert all(timeout <= 4 for timeout in seen)
    assert all(timeout > 0 for timeout in seen)


def test_session_calls_use_the_capped_timeout():
    """Cookie and crumb calls hit ``session.get``, not ``YfData.get``.

    yfinance 1.7 passes ``timeout=30`` straight into the session. No
    socket is opened: the session here only records the timeout.
    """
    from app.data_collectors.call_budget import pop_budget, push_budget
    from app.data_collectors.yahoo_finance import _install_http_cap

    seen = []

    class _Session:
        def get(self, url=None, **kwargs):
            seen.append(kwargs.get("timeout"))
            return {}

        def post(self, url=None, **kwargs):
            seen.append(kwargs.get("timeout"))
            return {}

    class _Data:
        def __init__(self):
            self._session = _Session()

        def get(self, url, params=None, timeout=30):
            seen.append(timeout)
            return {}

        def post(self, url, body=None, params=None, timeout=30, data=None):
            seen.append(timeout)
            return {}

    class _Stock:
        def __init__(self):
            self._data = _Data()

    stock = _Stock()
    _install_http_cap(stock)
    token = push_budget(time.monotonic() + 4, time.monotonic)
    try:
        stock._data.get("https://example.test/quote", timeout=30)
        stock._data.post("https://example.test/quote", timeout=30)
        stock._data._session.get(url="https://fc.yahoo.com", timeout=30)
        stock._data._session.post(
            url="https://consent.yahoo.com", timeout=30, data={}
        )
        stock._data._session.get(
            **{
                "url": "https://query1.finance.yahoo.com/v1/test/getcrumb",
                "timeout": 30,
            }
        )
        stock._data._session.get(url="https://fc.yahoo.com")
    finally:
        pop_budget(token)

    assert len(seen) == 6
    assert all(isinstance(timeout, float) for timeout in seen)
    assert all(0 < timeout <= 4 for timeout in seen)
    assert 30 not in seen


def test_a_replaced_session_is_capped_on_the_next_install():
    """The cap marker lives on the session, not only on ``YfData``.

    A later ``_session`` is a different object, so the next
    ``_install_http_cap`` wraps that one too. No socket is opened.
    """
    from app.data_collectors.call_budget import pop_budget, push_budget
    from app.data_collectors.yahoo_finance import _install_http_cap

    seen = []

    class _Session:
        def get(self, url=None, **kwargs):
            seen.append(kwargs.get("timeout"))
            return {}

        def post(self, url=None, **kwargs):
            seen.append(kwargs.get("timeout"))
            return {}

    class _Data:
        def __init__(self):
            self._session = _Session()

        def get(self, url, params=None, timeout=30):
            return {}

        def post(self, url, body=None, params=None, timeout=30, data=None):
            return {}

    class _Stock:
        def __init__(self):
            self._data = _Data()

    stock = _Stock()
    _install_http_cap(stock)
    replacement = _Session()
    stock._data._session = replacement
    _install_http_cap(stock)
    token = push_budget(time.monotonic() + 4, time.monotonic)
    try:
        replacement.get(url="https://fc.yahoo.com", timeout=30)
        replacement.post(url="https://consent.yahoo.com", timeout=30)
    finally:
        pop_budget(token)

    assert len(seen) == 2
    assert all(0 < timeout <= 4 for timeout in seen)


def test_spent_deadline_empty_result_is_not_cached(monkeypatch):
    """A swallowed timeout must not become a cached 404.

    The fake clock jumps past the deadline while Yahoo is reading
    ``info``. An empty payload is then a transient error, and the
    guard calls Yahoo again on the next request. A real name is kept.
    """
    clock = FakeClock()
    built = []

    class Spending:
        def __init__(self, symbol):
            built.append(symbol)
            self.symbol = symbol

        @property
        def info(self):
            clock.advance(100)
            if self.symbol == "REAL":
                return {"longName": "Acme", "currency": "USD"}
            return {}

    monkeypatch.setattr(yahoo_finance.yf, "Ticker", Spending)
    guarded = guard_collector(
        YahooFinanceCollector(),
        GuardPolicy(max_retries=0, total_deadline=15),
        clock=clock,
        sleep=clock.sleep,
        rand=lambda: 0.0,
    )

    with pytest.raises(TransientProviderError, match="deadline"):
        guarded.fetch_company_info("ACME")
    with pytest.raises(TransientProviderError, match="deadline"):
        guarded.fetch_company_info("ACME")

    assert built == ["ACME", "ACME"]
    kept = guarded.fetch_company_info("REAL")
    assert kept.value["name"] == "Acme"
    assert built[-1] == "REAL"
