"""demo-v2 is synthetic, and it contains the cases issue #27 names.

The file is the source of the numbers. This test does not recompute
the price formula. It checks the shape the demo needs: stocks across
GPW, the US, and the EU, at least two ETFs and two ETCs, mixed
currencies, one instrument with no prices, one whose prices are
stale relative to the fixture's as-of date, and about three to five
years of weekly bars on the others. Every company description and
every price source carries the demo-v2 marker.
"""

import json
from datetime import date, datetime
from pathlib import Path

from app.models.company import CompanyCreate
from app.models.financial_metrics import FinancialMetricsCreate
from app.models.price_bar import PriceBarCreate

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "demo-v2.json"
)
V1_TICKERS = {
    "DEMO_PL_TECH",
    "DEMO_US_GROWTH",
    "DEMO_DE_INDUSTRY",
    "DEMO_JP_STABLE",
    "DEMO_SG_EARLY",
    "DEMO_PL_EMPTY",
}
# A series that ends more than this many days before as_of is stale.
STALE_AFTER_DAYS = 365


def _load():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_demo_v2_covers_the_score_ready_cases():
    fixture = _load()
    assert fixture["version"] == 2
    assert fixture["marker"] == "[IAC-DEMO-V2]"
    as_of = date.fromisoformat(fixture["as_of"])
    companies = fixture["companies"]
    tickers = set()
    currencies = set()
    missing = []
    stale = []
    fresh_spans = []
    types = {"STOCK": 0, "ETF": 0, "ETC": 0}
    for entry in companies:
        company = CompanyCreate(**entry["company"])
        assert company.ticker not in tickers
        tickers.add(company.ticker)
        assert company.description.startswith(fixture["marker"])
        assert "buy" not in company.description.lower()
        assert "sell" not in company.description.lower()
        types[company.instrument_type.value] += 1
        currencies.add(company.currency)
        for raw in entry["metrics"]:
            metrics = FinancialMetricsCreate(company_id=1, **raw)
            assert metrics.period_end.tzinfo is not None
        dates = []
        for raw in entry["prices"]:
            bar = PriceBarCreate(**raw)
            assert bar.source == fixture["marker"]
            assert bar.currency == company.currency
            assert bar.date.weekday() == 0
            assert bar.retrieved_at.tzinfo is not None
            dates.append(bar.date)
        if not dates:
            missing.append(company.ticker)
            continue
        assert dates == sorted(dates)
        assert len(dates) == len(set(dates))
        for earlier, later in zip(dates, dates[1:]):
            assert (later - earlier).days == 7
        age = (as_of - dates[-1]).days
        if age > STALE_AFTER_DAYS:
            stale.append(company.ticker)
        else:
            span = (dates[-1] - dates[0]).days
            fresh_spans.append(span)
            assert 3 * 365 <= span <= 5 * 365 + 2

    assert V1_TICKERS <= tickers
    assert types["ETF"] >= 2
    assert types["ETC"] >= 2
    assert types["STOCK"] >= 6
    exchanges = {
        entry["company"]["ticker"]: entry["company"]["exchange"]
        for entry in companies
    }
    assert exchanges["DEMO_PL_TECH"] == "GPW"
    assert exchanges["DEMO_US_GROWTH"] == "NASDAQ"
    assert exchanges["DEMO_DE_INDUSTRY"] == "XETRA"
    assert len(currencies) >= 3
    assert missing == ["DEMO_PL_EMPTY"]
    assert stale == ["DEMO_JP_STABLE"]
    assert fresh_spans


def test_demo_v2_stale_retrieval_is_older_than_the_as_of_date():
    """The stale instrument was retrieved when its series ended."""
    fixture = _load()
    as_of = date.fromisoformat(fixture["as_of"])
    stale = next(
        entry
        for entry in fixture["companies"]
        if entry["company"]["ticker"] == "DEMO_JP_STABLE"
    )
    retrieved = {
        datetime.fromisoformat(
            row["retrieved_at"].replace("Z", "+00:00")
        ).date()
        for row in stale["prices"]
    }
    assert retrieved == {date(2024, 9, 30)}
    assert (as_of - date(2024, 9, 30)).days > STALE_AFTER_DAYS
