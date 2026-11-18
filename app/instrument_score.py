"""Load the stored figures a score needs.

The arithmetic lives in ``app.scoring``. This module only reads rows
that are already in the database. It does not call a market-data
provider and it does not fill a missing figure with zero.
"""

import math

from app.core.utc_datetime import as_utc
from app.models.database_models import FinancialMetricsDB
from app.price_metrics import metrics_from_bars
from app.repositories.fund_attributes_repository import (
    FundAttributesRepository,
)
from app.repositories.price_bar_repository import PriceBarRepository
from app.scoring import figure_names

# When an annual row and another row end on the same instant, the
# annual row is the one the score uses. A later period still wins.
_PERIOD_RANK = {"annual": 2, "quarterly": 1}


def load_score_inputs(db, company):
    """``{figure: (value, source, as_of)}`` for this instrument's type.

    A stock reads the newest stored metric that actually has each
    ratio. An ETF or an ETC reads TER, AUM, and the price-derived
    volatility and maximum drawdown. A missing row is a missing
    figure, not a zero.
    """
    names = figure_names(company.instrument_type)
    if company.instrument_type == "STOCK":
        found = _stock_figures(db, company.id)
    else:
        found = _fund_figures(db, company.id)
    return {name: found.get(name, (None, None, None)) for name in names}


def _stock_figures(db, company_id):
    rows = (
        db.query(FinancialMetricsDB)
        .filter(FinancialMetricsDB.company_id == company_id)
        .order_by(FinancialMetricsDB.id.asc())
        .all()
    )
    chosen = {}
    for row in rows:
        period = as_utc(row.period_end)
        rank = (
            period,
            _PERIOD_RANK.get(row.period_type, 0),
            row.id or 0,
        )
        for name in figure_names("STOCK"):
            value = getattr(row, name)
            if not _finite_number(value):
                continue
            previous = chosen.get(name)
            if previous is None or rank > previous[0]:
                chosen[name] = (rank, value, row.source, period.date())
    return {
        name: (value, source, as_of)
        for name, (_rank, value, source, as_of) in chosen.items()
    }


def _fund_figures(db, company_id):
    row = FundAttributesRepository(db).get_by_company(company_id)
    figures = {}
    if row is not None:
        figures["ter"] = (row.ter, row.source, row.as_of)
        aum_as_of = row.aum_as_of if row.aum_as_of is not None else row.as_of
        figures["aum"] = (row.aum, row.source, aum_as_of)
    bars = PriceBarRepository(db).get_range(company_id)
    derived = metrics_from_bars(bars)
    figures["volatility"] = _derived(derived.volatility)
    figures["max_drawdown"] = _derived(derived.max_drawdown)
    return figures


def _derived(metric):
    """A computed metric, or no value when it could not be computed."""
    if metric.value is None:
        return (None, metric.source, metric.as_of)
    return (metric.value, metric.source, metric.as_of)


def _finite_number(value):
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, float) and not math.isfinite(value):
        return False
    return isinstance(value, (int, float))
