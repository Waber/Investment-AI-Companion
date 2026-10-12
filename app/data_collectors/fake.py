"""
Deterministic, offline market-data collector for demos and tests.

``FakeCollector`` implements all four capability protocols from
``app.data_collectors.base`` without ``yfinance`` and without any network
access. Every number is synthetic and the output is identical on every
run, so tests and the demo UI can rely on it.
"""

import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.data_collectors.base import (
    COMPANY_INFO_FIELDS,
    FUND_ATTRIBUTE_FIELDS,
    KEY_METRIC_FIELDS,
    PriceBar,
    Provenance,
    Sourced,
)

SOURCE_NAME = "fake"
FAKE_AS_OF = date(2026, 9, 30)
FAKE_RETRIEVED_AT = datetime(2026, 9, 30, 18, 0, tzinfo=timezone.utc)

# Same marker as the demo fixture. The app must not import from
# ``scripts/``, so the value is repeated here (the UI does the same).
DEMO_MARKER = "[IAC-DEMO-V1]"

# The fixture path is resolved from this file, not from the working
# directory, so the collector works wherever the process is started.
FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "fixtures" / "demo-v1.json"
)

PROFILE_FIELDS = (
    "name",
    "sector",
    "industry",
    "description",
    "website",
    "country",
    "exchange",
    "currency",
)

# Trading days per supported period (a weekday-only calendar).
PERIOD_BARS = {
    "1mo": 21,
    "3mo": 63,
    "6mo": 126,
    "1y": 252,
    "2y": 504,
    "5y": 1260,
}
SUPPORTED_INTERVAL = "1d"

_FUND_DESCRIPTION = (
    f"{DEMO_MARKER} Synthetic {{kind}} for demos. "
    "Not market data and not an investment recommendation."
)

FUNDS: Dict[str, Dict[str, Any]] = {
    "DEMO_ETF_WORLD": {
        "profile": {
            "name": "Demo World Equity ETF",
            "sector": None,
            "industry": None,
            "description": _FUND_DESCRIPTION.format(kind="world equity ETF"),
            "website": None,
            "country": None,
            "exchange": "DEMO-XETRA",
            "currency": "EUR",
        },
        "attributes": {
            "fund_type": "ETF",
            "ter": 0.0022,
            "aum": 1250000000,
            "aum_currency": "EUR",
            "issuer": "Demo Issuer",
            "underlying": "Synthetic World Equity Index",
            "domicile": "Ireland",
            "distribution_policy": "accumulating",
        },
    },
    "DEMO_ETC_GOLD": {
        "profile": {
            "name": "Demo Physical Gold ETC",
            "sector": None,
            "industry": None,
            "description": _FUND_DESCRIPTION.format(kind="gold ETC"),
            "website": None,
            "country": None,
            "exchange": "DEMO-XETRA",
            "currency": "EUR",
        },
        "attributes": {
            "fund_type": "ETC",
            "ter": 0.0015,
            "aum": 450000000,
            "aum_currency": "EUR",
            "issuer": "Demo Issuer",
            "underlying": "Physical gold (synthetic)",
            "domicile": "Jersey",
            # Does not apply to an ETC.
            "distribution_policy": None,
        },
    },
}

# Hand-picked, plausible key metrics. Ratios are fractions (0.12 = 12%).
# DEMO_PL_EMPTY is deliberately absent: it models "no data".
STOCK_METRICS: Dict[str, Dict[str, float]] = {
    "DEMO_PL_TECH": {
        "pe_ratio": 24.5,
        "pb_ratio": 4.1,
        "roe": 0.14,
        "profit_margin": 0.14,
        "current_ratio": 2.1,
        "debt_to_equity": 45.0,
        "revenue_growth": 0.2,
        "debt_to_assets": 0.31,
    },
    "DEMO_US_GROWTH": {
        "pe_ratio": 38.0,
        "pb_ratio": 9.2,
        "roe": 0.22,
        "profit_margin": 0.18,
        "current_ratio": 1.8,
        "debt_to_equity": 60.0,
        "revenue_growth": 0.28,
        "debt_to_assets": 0.35,
    },
    "DEMO_DE_INDUSTRY": {
        "pe_ratio": 15.2,
        "pb_ratio": 2.0,
        "roe": 0.11,
        "profit_margin": 0.08,
        "current_ratio": 1.5,
        "debt_to_equity": 80.0,
        "revenue_growth": 0.04,
        "debt_to_assets": 0.42,
    },
    "DEMO_JP_STABLE": {
        "pe_ratio": 13.4,
        "pb_ratio": 1.2,
        "roe": 0.09,
        "profit_margin": 0.07,
        "current_ratio": 1.9,
        "debt_to_equity": 35.0,
        "revenue_growth": 0.02,
        "debt_to_assets": 0.25,
    },
    "DEMO_SG_EARLY": {
        "pe_ratio": 55.0,
        "pb_ratio": 6.5,
        "roe": 0.05,
        "profit_margin": 0.03,
        "current_ratio": 3.2,
        "debt_to_equity": 20.0,
        "revenue_growth": 0.45,
        "debt_to_assets": 0.15,
    },
}

# Per-ticker price curve: (base price, drift per bar, wave amplitude,
# wave period in bars, base volume).
PRICE_PARAMS: Dict[str, tuple] = {
    "DEMO_PL_TECH": (120.0, 0.0004, 0.05, 40.0, 150000),
    "DEMO_US_GROWTH": (210.0, 0.0007, 0.08, 55.0, 2500000),
    "DEMO_DE_INDUSTRY": (88.0, 0.0002, 0.04, 70.0, 600000),
    "DEMO_JP_STABLE": (3400.0, 0.0001, 0.02, 90.0, 900000),
    "DEMO_SG_EARLY": (6.5, 0.0009, 0.12, 30.0, 400000),
    "DEMO_ETF_WORLD": (95.0, 0.0003, 0.03, 80.0, 300000),
    "DEMO_ETC_GOLD": (55.0, 0.0002, 0.025, 65.0, 120000),
}


def _default_clock() -> datetime:
    return FAKE_RETRIEVED_AT


def _weekdays_ending_at(last_day: date, count: int) -> List[date]:
    """The last ``count`` weekdays up to ``last_day``, oldest first."""
    days: List[date] = []
    day = last_day
    while len(days) < count:
        if day.weekday() < 5:  # Monday=0 ... Friday=4
            days.append(day)
        day -= timedelta(days=1)
    days.reverse()
    return days


def _make_bar(day: date, index: int, params: tuple) -> PriceBar:
    """One bar from a closed-form formula of the bar's position in time.

    ``random`` is avoided on purpose: even a seeded generator makes a bar
    depend on how many numbers were drawn before it. A formula of the day
    alone gives the same bar for a "1mo" and a "5y" request.
    ``index`` counts weekdays since a fixed epoch, so it is stable.
    """
    base, drift, amplitude, wave_period, base_volume = params
    trend = base * (1 + drift * index)
    close = trend * (
        1 + amplitude * math.sin(2 * math.pi * index / wave_period)
    )
    open_ = trend * (
        1 + amplitude * math.sin(2 * math.pi * (index - 1) / wave_period)
    )
    spread = 1 + 0.01 * (1 + math.sin(index))  # 1% to 2% above/below
    high = max(open_, close) * spread
    low = min(open_, close) / spread
    volume = int(base_volume * (1 + 0.3 * math.sin(index / 3.0)))
    return PriceBar(
        day=day,
        open=round(open_, 4),
        high=round(high, 4),
        low=round(low, 4),
        close=round(close, 4),
        volume=volume,
    )


def _weekday_index(day: date) -> int:
    """Number of weekdays between a fixed Monday and ``day`` (a weekday)."""
    epoch = date(2020, 1, 6)  # a Monday
    full_weeks, extra_days = divmod((day - epoch).days, 7)
    return full_weeks * 5 + extra_days


class FakeCollector:
    """Offline collector: stocks from the demo fixture plus two demo funds.

    Python's ``Protocol`` is structural, so this class needs no
    ``implements`` clause: having the four ``fetch_*`` methods is enough.

    ``clock`` is injectable (a function returning "now") so a test can
    pin ``retrieved_at``. The default returns a fixed instant, which makes
    two runs produce equal results. Every call builds new dicts and
    lists: a ``Sourced`` is frozen, but freezing is shallow, so a shared
    dict could be changed by a caller and leak into later results.
    """

    def __init__(self, clock: Callable[[], datetime] = _default_clock) -> None:
        self._clock = clock
        self._stock_profiles = self._load_stock_profiles()

    @staticmethod
    def _load_stock_profiles() -> Dict[str, Dict[str, Any]]:
        data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        profiles: Dict[str, Dict[str, Any]] = {}
        for entry in data["companies"]:
            company = entry["company"]
            profiles[company["ticker"]] = {
                field: company.get(field) for field in PROFILE_FIELDS
            }
        return profiles

    def _provenance(self, as_of: date = FAKE_AS_OF) -> Provenance:
        return Provenance(
            source=SOURCE_NAME,
            retrieved_at=self._clock(),
            as_of=as_of,
            synthetic=True,
        )

    def fetch_company_info(
        self, ticker: str
    ) -> Optional[Sourced[Dict[str, Any]]]:
        key = ticker.upper()
        if key in self._stock_profiles:
            profile = self._stock_profiles[key]
        elif key in FUNDS:
            profile = FUNDS[key]["profile"]
        else:
            return None
        info: Dict[str, Any] = {field: None for field in COMPANY_INFO_FIELDS}
        info.update(profile)
        info["ticker"] = key
        return Sourced(info, self._provenance())

    def fetch_key_metrics(
        self, ticker: str
    ) -> Optional[Sourced[Dict[str, Any]]]:
        key = ticker.upper()
        metrics: Dict[str, Any] = {field: None for field in KEY_METRIC_FIELDS}
        if key in STOCK_METRICS:
            metrics.update(STOCK_METRICS[key])
        elif key not in FUNDS:
            # Unknown ticker, or DEMO_PL_EMPTY (a company without data).
            return None
        return Sourced(metrics, self._provenance())

    def fetch_fund_attributes(
        self, ticker: str
    ) -> Optional[Sourced[Dict[str, Any]]]:
        fund = FUNDS.get(ticker.upper())
        if fund is None:
            return None
        attributes = {field: None for field in FUND_ATTRIBUTE_FIELDS}
        attributes.update(fund["attributes"])
        return Sourced(attributes, self._provenance())

    def fetch_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> Optional[Sourced[List[PriceBar]]]:
        # Bad arguments are a caller bug (ValueError), checked before the
        # lookup so they fail the same way for every ticker.
        if period not in PERIOD_BARS:
            raise ValueError(
                f"Unsupported period {period!r}; supported: "
                f"{', '.join(PERIOD_BARS)}"
            )
        if interval != SUPPORTED_INTERVAL:
            raise ValueError(
                f"Unsupported interval {interval!r}; supported: "
                f"{SUPPORTED_INTERVAL}"
            )
        params = PRICE_PARAMS.get(ticker.upper())
        if params is None:
            return None
        days = _weekdays_ending_at(FAKE_AS_OF, PERIOD_BARS[period])
        bars = [_make_bar(day, _weekday_index(day), params) for day in days]
        return Sourced(bars, self._provenance(as_of=bars[-1].day))
