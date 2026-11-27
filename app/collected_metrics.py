"""Names shared by the collected-metrics code.

A collector (for example Yahoo Finance) fills one "TTM" row per
company in ``financial_metrics``. These constants say which period
type that row uses and which columns a collector is allowed to set.
"""

import math
from datetime import date, datetime, timezone
from typing import Optional

TTM_PERIOD = "ttm"

# The ratio columns a collector fills, in a fixed order. Raw statement
# values (revenue, total assets, ...) stay manual-only.
COLLECTED_METRIC_COLUMNS = (
    "roe",
    "roa",
    "gross_margin",
    "net_margin",
    "current_ratio",
    "quick_ratio",
    "debt_to_equity",
    "debt_to_assets",
    "revenue_growth",
    "pe_ratio",
    "pb_ratio",
    "ev_ebitda",
)

# The seven figures the stock score reads. A snapshot with none of them
# is "no data": storing it would write a row of empty values.
SCORE_FIGURES = (
    "roe",
    "net_margin",
    "pe_ratio",
    "pb_ratio",
    "debt_to_equity",
    "current_ratio",
    "revenue_growth",
)

# Yahoo's key-metric name -> column name, only where they differ.
_RENAMED = {"profit_margin": "net_margin"}


def _finite_number(value: object) -> Optional[float]:
    """Return ``value`` as a float, or None when it is not a real number.

    ``bool`` is a subclass of ``int`` in Python, so ``True`` would pass
    an ``isinstance(value, int)`` check. It is rejected on purpose.
    NaN and infinity are rejected because the database must never
    hold them.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def columns_from_key_metrics(values: dict) -> dict:
    """Map a collector's key metrics to ``financial_metrics`` columns.

    The result has all 12 ``COLLECTED_METRIC_COLUMNS`` as keys. A
    missing or unusable value becomes None, never zero.
    """
    source_name = {column: column for column in COLLECTED_METRIC_COLUMNS}
    for yahoo_name, column in _RENAMED.items():
        source_name[column] = yahoo_name
    return {
        column: _finite_number(values.get(source_name[column]))
        for column in COLLECTED_METRIC_COLUMNS
    }


def ttm_period_end(as_of: date) -> datetime:
    """The row's ``period_end``: the snapshot date at 00:00 UTC."""
    return datetime(as_of.year, as_of.month, as_of.day, tzinfo=timezone.utc)
