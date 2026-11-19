"""Load the stored figures a score needs.

The arithmetic lives in ``app.scoring``. This module only reads rows
that are already in the database. It does not call a market-data
provider and it does not fill a missing figure with zero.

A synthetic instrument stays synthetic after a person edits one of
its rows. The edit sets that row's source to ``manual``, so for a
synthetic company, and for a synthetic fund-attribute row, every
figure is reported with the source ``demo``. That is the one label
``/ui`` shows for synthetic data. A metric row has no synthetic
column of its own, so the company's flag decides.
"""

import math

from app.core.utc_datetime import as_utc
from app.models.database_models import RECORD_SOURCE_DEMO, FinancialMetricsDB
from app.price_metrics import metrics_from_bars
from app.repositories.fund_attributes_repository import (
    FundAttributesRepository,
)
from app.repositories.price_bar_repository import PriceBarRepository
from app.scoring import Figure, figure_names

# When an annual row and another row end on the same instant, the
# annual row is the one the score uses. A later period still wins.
# The forms store ``period_type`` as typed, so it is compared after
# ``strip`` and ``casefold``, the way ``app/ui/view_models.py`` sorts
# annual and quarterly rows.
_PERIOD_RANK = {"annual": 2, "quarterly": 1}


def is_synthetic(company):
    """True only for a stored ``True``, the rule ``/ui`` uses."""
    return getattr(company, "is_synthetic", False) is True


def _shown_source(source, synthetic):
    """``demo`` for synthetic data. A figure with no source keeps None."""
    if synthetic and source is not None:
        return RECORD_SOURCE_DEMO
    return source


def load_score_inputs(db, company):
    """``{figure: Figure}`` for this instrument's type.

    A stock reads the newest stored metric that actually has each
    ratio. An ETF or an ETC reads TER, AUM with its currency, and the
    price-derived volatility and maximum drawdown with the start of
    their window. A missing row is a missing figure, not a zero.
    """
    names = figure_names(company.instrument_type)
    synthetic = is_synthetic(company)
    if company.instrument_type == "STOCK":
        found = _stock_figures(db, company.id, synthetic)
    else:
        found = _fund_figures(db, company.id, synthetic)
    return {name: found.get(name, Figure(None, None, None)) for name in names}


def _period_rank(period_type):
    kind = period_type.strip().casefold() if period_type else ""
    return _PERIOD_RANK.get(kind, 0)


def _stock_figures(db, company_id, synthetic):
    rows = (
        db.query(FinancialMetricsDB)
        .filter(FinancialMetricsDB.company_id == company_id)
        .order_by(FinancialMetricsDB.id.asc())
        .all()
    )
    chosen = {}
    for row in rows:
        period = as_utc(row.period_end)
        rank = (period, _period_rank(row.period_type), row.id or 0)
        source = _shown_source(row.source, synthetic)
        for name in figure_names("STOCK"):
            value = getattr(row, name)
            if not _finite_number(value):
                continue
            previous = chosen.get(name)
            if previous is None or rank > previous[0]:
                chosen[name] = (rank, Figure(value, source, period.date()))
    return {name: figure for name, (_rank, figure) in chosen.items()}


def _fund_figures(db, company_id, synthetic):
    row = FundAttributesRepository(db).get_by_company(company_id)
    figures = {}
    if row is not None:
        demo = synthetic or row.is_synthetic is True
        source = _shown_source(row.source, demo)
        figures["ter"] = Figure(row.ter, source, row.as_of)
        # AUM is dated by its own date only. The snapshot ``as_of``
        # says when the row was checked, not when the fund had this
        # size, so an undated AUM is no data.
        figures["aum"] = Figure(
            row.aum, source, row.aum_as_of, currency=row.aum_currency
        )
    bars = PriceBarRepository(db).get_range(company_id)
    derived = metrics_from_bars(bars)
    figures["volatility"] = _derived(derived.volatility, synthetic)
    figures["max_drawdown"] = _derived(derived.max_drawdown, synthetic)
    return figures


def _derived(metric, synthetic):
    """A computed metric with its window start, or no value.

    ``start`` is the first close of the window. The score uses it to
    refuse a "one-year" figure whose window began years earlier.
    """
    source = _shown_source(metric.source, synthetic)
    return Figure(metric.value, source, metric.as_of, start=metric.start)


def _finite_number(value):
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, float) and not math.isfinite(value):
        return False
    return isinstance(value, (int, float))
