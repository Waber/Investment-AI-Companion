"""Tests for the deterministic offline FakeCollector."""

import json
import socket
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.data_collectors.base import (
    COMPANY_INFO_FIELDS,
    FUND_ATTRIBUTE_FIELDS,
    KEY_METRIC_FIELDS,
    Fundamentals,
    FundAttributes,
    InstrumentLookup,
    PriceHistory,
)
from app.data_collectors.fake import (
    FAKE_AS_OF,
    FAKE_RETRIEVED_AT,
    FakeCollector,
)

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "demo-v1.json"
MARKER = "[IAC-DEMO-V1]"
STOCKS_WITH_METRICS = [
    "DEMO_PL_TECH",
    "DEMO_US_GROWTH",
    "DEMO_DE_INDUSTRY",
    "DEMO_JP_STABLE",
    "DEMO_SG_EARLY",
]
FUNDS = ["DEMO_ETF_WORLD", "DEMO_ETC_GOLD"]
ALL_TICKERS = STOCKS_WITH_METRICS + ["DEMO_PL_EMPTY"] + FUNDS
PERIOD_BARS = {
    "1mo": 21,
    "3mo": 63,
    "6mo": 126,
    "1y": 252,
    "2y": 504,
    "5y": 1260,
}


def _sweep(collector, ticker):
    return (
        collector.fetch_company_info(ticker),
        collector.fetch_key_metrics(ticker),
        collector.fetch_fund_attributes(ticker),
        collector.fetch_price_history(ticker),
    )


def test_implements_all_four_protocols():
    collector = FakeCollector()
    for protocol in (
        InstrumentLookup,
        PriceHistory,
        Fundamentals,
        FundAttributes,
    ):
        assert isinstance(collector, protocol)


def test_two_instances_return_equal_results():
    first, second = FakeCollector(), FakeCollector()
    for ticker in ALL_TICKERS + ["UNKNOWN"]:
        assert _sweep(first, ticker) == _sweep(second, ticker)


def test_full_sweep_opens_no_connection(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    collector = FakeCollector()
    for ticker in ALL_TICKERS:
        _sweep(collector, ticker)


def test_provenance_is_synthetic_fake():
    collector = FakeCollector()
    for ticker in ALL_TICKERS:
        for result in _sweep(collector, ticker):
            if result is None:
                continue
            assert result.provenance.source == "fake"
            assert result.provenance.synthetic is True
            assert result.provenance.retrieved_at == FAKE_RETRIEVED_AT
            assert result.provenance.as_of == FAKE_AS_OF


def test_history_as_of_is_last_bar_day():
    result = FakeCollector().fetch_price_history("DEMO_US_GROWTH", "1mo")
    assert result.provenance.as_of == result.value[-1].day == date(2026, 9, 30)


def test_injected_clock_sets_retrieved_at():
    moment = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
    result = FakeCollector(clock=lambda: moment).fetch_company_info(
        "DEMO_PL_TECH"
    )
    assert result.provenance.retrieved_at == moment


def test_descriptions_carry_marker():
    collector = FakeCollector()
    for ticker in ALL_TICKERS:
        info = collector.fetch_company_info(ticker).value
        assert info["description"].startswith(MARKER)


def test_company_info_has_all_fields_and_ticker():
    collector = FakeCollector()
    for ticker in ALL_TICKERS:
        info = collector.fetch_company_info(ticker).value
        assert tuple(info) == COMPANY_INFO_FIELDS
        assert info["ticker"] == ticker
        assert info["market_cap"] is None


def test_stock_profiles_equal_fixture():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    collector = FakeCollector()
    assert len(fixture["companies"]) == 6
    for entry in fixture["companies"]:
        profile = entry["company"]
        info = collector.fetch_company_info(profile["ticker"]).value
        for key, value in profile.items():
            assert info[key] == value


def test_fund_profiles():
    collector = FakeCollector()
    for ticker in FUNDS:
        info = collector.fetch_company_info(ticker).value
        assert info["exchange"] == "DEMO-XETRA"
        assert info["currency"] == "EUR"
        assert "synthetic" in info["description"].lower()
        assert "not market data" in info["description"].lower()


def test_required_coverage_exchanges():
    collector = FakeCollector()
    assert (
        collector.fetch_company_info("DEMO_PL_TECH").value["exchange"]
        == "DEMO-WSE"
    )
    assert collector.fetch_company_info("DEMO_US_GROWTH") is not None
    assert collector.fetch_company_info("DEMO_DE_INDUSTRY") is not None


def test_key_metrics_debt_to_assets_for_stocks():
    collector = FakeCollector()
    for ticker in STOCKS_WITH_METRICS:
        metrics = collector.fetch_key_metrics(ticker).value
        assert tuple(metrics) == KEY_METRIC_FIELDS
        for key in (
            "pe_ratio",
            "pb_ratio",
            "roe",
            "profit_margin",
            "current_ratio",
            "debt_to_equity",
            "revenue_growth",
        ):
            assert metrics[key] is not None
        assert 0 < metrics["debt_to_assets"] < 1


def test_key_metrics_none_for_empty_company():
    collector = FakeCollector()
    assert collector.fetch_key_metrics("DEMO_PL_EMPTY") is None
    assert collector.fetch_price_history("DEMO_PL_EMPTY") is None


def test_funds_have_all_none_key_metrics():
    collector = FakeCollector()
    for ticker in FUNDS:
        metrics = collector.fetch_key_metrics(ticker).value
        assert tuple(metrics) == KEY_METRIC_FIELDS
        assert all(value is None for value in metrics.values())


def test_fund_attributes():
    collector = FakeCollector()
    etf = collector.fetch_fund_attributes("DEMO_ETF_WORLD").value
    etc = collector.fetch_fund_attributes("DEMO_ETC_GOLD").value
    assert tuple(etf) == FUND_ATTRIBUTE_FIELDS
    assert etf == {
        "fund_type": "ETF",
        "ter": 0.0022,
        "aum": 1250000000,
        "aum_currency": "EUR",
        "issuer": "Demo Issuer",
        "underlying": "Synthetic World Equity Index",
        "domicile": "Ireland",
        "distribution_policy": "accumulating",
    }
    assert etc["fund_type"] == "ETC"
    assert etc["ter"] == 0.0015
    assert etc["aum"] == 450000000
    assert etc["underlying"] == "Physical gold (synthetic)"
    assert etc["domicile"] == "Jersey"
    assert etc["distribution_policy"] is None


def test_fund_attributes_none_for_stocks():
    collector = FakeCollector()
    for ticker in STOCKS_WITH_METRICS + ["DEMO_PL_EMPTY"]:
        assert collector.fetch_fund_attributes(ticker) is None


@pytest.mark.parametrize("period,count", PERIOD_BARS.items())
def test_bar_counts_per_period(period, count):
    bars = FakeCollector().fetch_price_history("DEMO_PL_TECH", period).value
    assert len(bars) == count


def test_default_period_is_one_year():
    bars = FakeCollector().fetch_price_history("DEMO_PL_TECH").value
    assert len(bars) == 252


def test_bars_are_weekdays_oldest_first_ending_at_as_of():
    for ticker in ALL_TICKERS:
        result = FakeCollector().fetch_price_history(ticker, "1y")
        if result is None:
            continue
        days = [bar.day for bar in result.value]
        assert days == sorted(set(days))
        assert days[-1] == FAKE_AS_OF
        assert all(day.weekday() < 5 for day in days)


def test_bars_are_consistent_and_positive():
    collector = FakeCollector()
    for ticker in ALL_TICKERS:
        result = collector.fetch_price_history(ticker, "5y")
        if result is None:
            continue
        for bar in result.value:
            assert min(bar.open, bar.high, bar.low, bar.close) > 0
            assert bar.low <= min(bar.open, bar.close)
            assert max(bar.open, bar.close) <= bar.high
            assert isinstance(bar.volume, int) and bar.volume > 0


@pytest.mark.parametrize(
    "period,interval", [("10y", "1d"), ("1y", "1wk"), ("", "1d"), ("1y", "")]
)
def test_unsupported_period_or_interval_raises_value_error(period, interval):
    with pytest.raises(ValueError) as error:
        FakeCollector().fetch_price_history("DEMO_PL_TECH", period, interval)
    assert "1d" in str(error.value) or "1mo" in str(error.value)


def test_mutating_results_does_not_change_next_result():
    collector = FakeCollector()
    info = collector.fetch_company_info("DEMO_PL_TECH")
    info.value["name"] = "Changed"
    metrics = collector.fetch_key_metrics("DEMO_PL_TECH")
    metrics.value["pe_ratio"] = -1
    attrs = collector.fetch_fund_attributes("DEMO_ETF_WORLD")
    attrs.value["ter"] = 9
    bars = collector.fetch_price_history("DEMO_PL_TECH", "1mo")
    bars.value.clear()
    assert (
        collector.fetch_company_info("DEMO_PL_TECH").value["name"] != "Changed"
    )
    assert collector.fetch_key_metrics("DEMO_PL_TECH").value["pe_ratio"] != -1
    assert collector.fetch_fund_attributes("DEMO_ETF_WORLD").value["ter"] != 9
    assert (
        len(collector.fetch_price_history("DEMO_PL_TECH", "1mo").value) == 21
    )


def test_ticker_lookup_is_case_insensitive():
    collector = FakeCollector()
    assert collector.fetch_company_info(
        "demo_pl_tech"
    ) == collector.fetch_company_info("DEMO_PL_TECH")


def test_unknown_ticker_returns_none_everywhere():
    assert _sweep(FakeCollector(), "NOPE") == (None, None, None, None)
