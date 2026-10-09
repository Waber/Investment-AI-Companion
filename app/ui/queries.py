"""Load company rows and hand instrument view-models to the pages.

Filtering happens in Python. The demo file has a handful of rows, and
SQLite ``LIKE`` is not the same case-fold as ``str.casefold`` for every
character. A later instrument table can push this into SQL without a
template change. ``selectinload`` fetches metrics in one extra query
instead of one query per company.
"""

from dataclasses import dataclass

from sqlalchemy.orm import selectinload

from app.models.database_models import CompanyDB
from app.ui.view_models import to_instrument


@dataclass(frozen=True)
class ListFilters:
    """The list form. Empty strings mean "do not filter"."""

    search: str
    instrument_type: str
    exchange: str
    currency: str


def _ordered_text(values):
    cleaned = {value for value in values if value}
    return sorted(cleaned, key=str.casefold)


def _load_companies(db):
    return (
        db.query(CompanyDB)
        .options(selectinload(CompanyDB.financial_metrics))
        .all()
    )


def list_instruments(db, filters):
    """Return the matching instruments and the dropdown values.

    Dropdowns come from the full table, so a selected type or
    exchange does not hide the other options from the form.
    """
    instruments = [to_instrument(company) for company in _load_companies(db)]
    # Options come from the rows, not a fixed list. Today that is
    # "stock". A later model can add ETF and ETC without a template
    # change. An empty type means "every type".
    instrument_types = _ordered_text(
        item.instrument_type for item in instruments
    )
    exchanges = _ordered_text(item.exchange for item in instruments)
    currencies = _ordered_text(item.currency for item in instruments)
    needle = filters.search.casefold()
    selected = []
    for item in instruments:
        if needle:
            name = (item.name or "").casefold()
            ticker = (item.ticker or "").casefold()
            if needle not in name and needle not in ticker:
                continue
        if (
            filters.instrument_type
            and (item.instrument_type or "") != filters.instrument_type
        ):
            continue
        if filters.exchange and (item.exchange or "") != filters.exchange:
            continue
        if filters.currency and (item.currency or "") != filters.currency:
            continue
        selected.append(item)
    selected.sort(key=lambda item: (item.ticker or "").casefold())
    return selected, instrument_types, exchanges, currencies


def get_instrument(db, instrument_id):
    """Return one instrument view, or None when the id is unknown."""
    company = (
        db.query(CompanyDB)
        .options(selectinload(CompanyDB.financial_metrics))
        .filter(CompanyDB.id == instrument_id)
        .first()
    )
    if company is None:
        return None
    return to_instrument(company)
