"""Names shared by the collected-metrics code.

A collector (for example Yahoo Finance) fills one "TTM" row per
company in ``financial_metrics``. These constants say which period
type that row uses and which columns a collector is allowed to set.
"""

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
