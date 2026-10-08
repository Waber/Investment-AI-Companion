"""Read-side instrument view-models built from company rows.

Templates bind to these objects. They do not read ``CompanyDB``.
Issue #26 can swap the query that loads rows; the field names here
already match an instrument (type, source, synthetic flag, as-of).
Until that model exists, every company is presented as a stock, and
a description that starts with the demo-v1 marker is synthetic.
"""

import math
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

from app.core.utc_datetime import as_utc

# The fixture marker. Kept here so the UI does not import the seeder.
DEMO_MARKER = "[IAC-DEMO-V1]"
DEMO_SOURCE = "demo-v1"
# Every current row is a company. #26 introduces stock, ETF, and ETC.
COMPANY_INSTRUMENT_TYPE = "stock"
# Required on every external website link the view-model approves.
EXTERNAL_LINK_REL = "noopener noreferrer"
_LINK_SCHEMES = {"http", "https"}

MONETARY_FIELDS = (
    "revenue",
    "net_income",
    "total_assets",
    "total_liabilities",
    "total_equity",
)
RATIO_FIELDS = (
    "roe",
    "roa",
    "gross_margin",
    "net_margin",
    "current_ratio",
    "quick_ratio",
    "debt_to_equity",
    "debt_to_assets",
    "asset_turnover",
    "inventory_turnover",
    "revenue_growth",
    "net_income_growth",
    "pe_ratio",
    "pb_ratio",
    "ev_ebitda",
)
METRIC_FIELDS = MONETARY_FIELDS + RATIO_FIELDS


@dataclass(frozen=True)
class WebsiteView:
    """Text to show, and a link target only for an http(s) website.

    ``text`` is None when the stored value is empty. The page then
    uses the "no data" catalog string. ``href`` is None when the
    value must be shown as plain text. ``rel`` is set only together
    with ``href``.
    """

    text: str | None
    href: str | None
    rel: str | None


@dataclass(frozen=True)
class PeriodView:
    """One reporting period. ``values`` is keyed by ``METRIC_FIELDS``."""

    period_end: datetime
    period_key: str
    values: dict


@dataclass(frozen=True)
class InstrumentView:
    """One instrument, as the templates render it."""

    id: int
    instrument_type: str
    ticker: str | None
    name: str | None
    exchange: str | None
    currency: str | None
    country: str | None
    sector: str | None
    industry: str | None
    description: str | None
    website: WebsiteView
    source: str | None
    is_synthetic: bool
    as_of: datetime | None
    annual: list
    quarterly: list
    other: list


def http_website_href(value):
    """Return a link target only for http or https.

    Legacy rows store ``website`` as a plain string. ``javascript:``
    and ``data:`` must not become an ``href``. The steps are:

    1. ``None`` and whitespace-only values are not links.
    2. Surrounding whitespace is removed before the scheme is read.
    3. A value that still contains whitespace or a control character
       is not a link.
    4. The scheme is compared case-insensitively. Only ``http`` and
       ``https`` pass, and only when a host is present.

    The returned string is the stripped URL. The template does not
    inspect the scheme.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if any(character.isspace() or ord(character) < 32 for character in text):
        return None
    parts = urlsplit(text)
    if parts.scheme.casefold() not in _LINK_SCHEMES:
        return None
    if not parts.netloc:
        return None
    return text


def website_view(value):
    """Build the website view from a stored string."""
    if value is None:
        text = None
    else:
        stripped = str(value).strip()
        text = stripped or None
    href = http_website_href(text)
    rel = EXTERNAL_LINK_REL if href else None
    return WebsiteView(text=text, href=href, rel=rel)


def _text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _finite_number(value):
    """Keep a real number, including zero. Drop missing and non-finite."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value
    return None


def _period_view(row):
    instant = as_utc(row.period_end)
    values = {
        field: _finite_number(getattr(row, field, None))
        for field in METRIC_FIELDS
    }
    return PeriodView(
        period_end=instant,
        period_key=instant.date().isoformat(),
        values=values,
    )


def to_instrument(company):
    """Map one company row and its metrics to an instrument view."""
    description = company.description
    is_synthetic = isinstance(description, str) and description.startswith(
        DEMO_MARKER
    )
    annual = []
    quarterly = []
    other = []
    latest = None
    for row in company.financial_metrics or []:
        period = _period_view(row)
        kind = (row.period_type or "").strip().casefold()
        if kind == "annual":
            annual.append(period)
        elif kind == "quarterly":
            quarterly.append(period)
        else:
            other.append(period)
        if latest is None or period.period_end > latest:
            latest = period.period_end
    annual.sort(key=lambda item: item.period_end, reverse=True)
    quarterly.sort(key=lambda item: item.period_end, reverse=True)
    other.sort(key=lambda item: item.period_end, reverse=True)
    return InstrumentView(
        id=company.id,
        instrument_type=COMPANY_INSTRUMENT_TYPE,
        ticker=_text(company.ticker),
        name=_text(company.name),
        exchange=_text(company.exchange),
        currency=_text(company.currency),
        country=_text(company.country),
        sector=_text(company.sector),
        industry=_text(company.industry),
        description=_text(description),
        website=website_view(company.website),
        source=DEMO_SOURCE if is_synthetic else None,
        is_synthetic=is_synthetic,
        as_of=latest,
        annual=annual,
        quarterly=quarterly,
        other=other,
    )
