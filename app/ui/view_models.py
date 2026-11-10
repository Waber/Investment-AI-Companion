"""Read-side instrument view-models built from company rows.

Templates bind to these objects. They do not read ``CompanyDB``.
Issue #26 can swap the query that loads rows; the field names here
already match an instrument (type, source, synthetic flag, as-of).
``is_synthetic`` is the stored column. The description prefix is not
read. A synthetic row shows the one label ``demo``. A manual row
shows no source, so the word ``manual`` stays off the page. The type
on the page is the stored ``instrument_type`` (``STOCK``, ``ETF``, or
``ETC``), shown through the catalog ids ``stock``, ``etf``, and
``etc``.
"""

import math
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

from app.core.utc_datetime import as_utc

# One runtime label for every synthetic company. The owner chose this
# on 2026-11-08 instead of ``demo-v1`` and ``demo-v2``. It is not
# parsed from the description.
DEMO_SOURCE = "demo"
# The column stores the enum in uppercase. The pages and the list
# filter use the lowercase catalog id (``type.stock``, and the same
# for ETF and ETC). Anything else is missing data, not a stock.
_CATALOG_INSTRUMENT_TYPES = {
    "STOCK": "stock",
    "ETF": "etf",
    "ETC": "etc",
}
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
    """One reporting period. ``values`` is keyed by ``METRIC_FIELDS``.

    ``metrics_id`` is the financial-metrics row id when the row has
    one. The detail page uses it for the edit and delete links. A
    stand-in row with no id leaves it empty, and the template then
    shows the numbers without those links.
    """

    period_end: datetime
    period_key: str
    values: dict
    metrics_id: int | None = None


@dataclass(frozen=True)
class FundAttributesView:
    """ETF or ETC facts. A missing value is None, never zero.

    ``source`` is the word ``demo`` when the row is synthetic, and
    None for a manual row, matching the company badge. ``ter`` is
    the stored fraction (0.0022 means 0.22 percent).
    """

    issuer: str | None
    underlying: str | None
    ter: float | None
    domicile: str | None
    replication_method: str | None
    distribution_policy: str | None
    aum: float | None
    aum_currency: str | None
    aum_as_of: datetime | None
    as_of: datetime | None
    source: str | None
    is_synthetic: bool


@dataclass(frozen=True)
class DerivedMetricView:
    """One price-derived number, or a reason it is missing."""

    value: float | None
    reason: str | None
    start: datetime | None
    end: datetime | None
    source: str | None


@dataclass(frozen=True)
class PriceMetricsView:
    """The four metrics for the instrument's default price series."""

    source: str | None
    as_of: datetime | None
    return_1y: DerivedMetricView
    return_3y: DerivedMetricView
    volatility: DerivedMetricView
    max_drawdown: DerivedMetricView


@dataclass(frozen=True)
class InstrumentView:
    """One instrument, as the templates render it."""

    id: int
    instrument_type: str | None
    ticker: str | None
    isin: str | None
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
    fund_attributes: FundAttributesView | None = None
    price_metrics: PriceMetricsView | None = None


def http_website_href(value):
    """Return a link target only for http or https.

    Legacy rows store ``website`` as a plain string. ``javascript:``
    and ``data:`` must not become an ``href``. The steps are:

    1. ``None`` and whitespace-only values are not links.
    2. Surrounding whitespace is removed before the scheme is read.
    3. A value that still contains whitespace, a control character
       (including DEL), or a Unicode format character (category
       ``Cf``, such as U+202E or U+200B) is not a link.
    4. The scheme is compared case-insensitively. Only ``http`` and
       ``https`` pass, and only when a host is present.
       ``javascript://example.com/...`` has a host and is still
       rejected here.

    The returned string is the stripped URL. The template does not
    inspect the scheme.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if any(_blocks_website_link(character) for character in text):
        return None
    parts = urlsplit(text)
    if parts.scheme.casefold() not in _LINK_SCHEMES:
        return None
    if not parts.netloc:
        return None
    return text


def _blocks_website_link(character):
    """True when this character must not appear inside an href.

    Format characters can reorder or hide the rest of the URL.
    DEL is a control character whose code point is 127, so a
    check for ``ord < 32`` does not see it.
    """
    code = ord(character)
    if character.isspace() or code < 32 or code == 127:
        return True
    return unicodedata.category(character) == "Cf"


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


# Same ceiling as ``AUM_MAX``. A larger float is still finite, and
# turning it into an int makes ``format_number`` overflow. The page
# shows that number as missing.
_DISPLAY_MAX = 1e15


def _finite_number(value):
    """Keep a real number, including zero. Drop missing and non-finite.

    A float whose absolute value is above ``_DISPLAY_MAX`` is not
    turned into an int. ``1e308`` is finite and ``is_integer()`` is
    true, and the resulting int is hundreds of digits. Multiplying
    that int by 100 then overflows ``float``.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        if abs(value) > _DISPLAY_MAX:
            return None
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
        metrics_id=getattr(row, "id", None),
    )


def catalog_instrument_type(value):
    """Return the catalog id for a stored instrument type.

    ``CompanyDB.instrument_type`` is ``STOCK``, ``ETF``, or ``ETC``.
    The templates look up ``type.`` plus ``stock``, ``etf``, or
    ``etc``, and the list filter compares those same ids. A missing
    value, or one outside the three names, is ``None``. A stored
    row cannot be null: the column has a CHECK constraint and a
    STOCK default, so the list and the detail page always print
    one of those three words.
    ``InstrumentType`` is a ``str`` enum, so a member is accepted
    here too.
    """
    if not isinstance(value, str):
        return None
    return _CATALOG_INSTRUMENT_TYPES.get(value.strip().upper())


def _midnight(value):
    """A calendar date as midnight UTC, so the date formatter can show it."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return as_utc(value)
    if isinstance(value, date):
        return datetime(
            value.year, value.month, value.day, tzinfo=timezone.utc
        )
    return None


def _fund_view(row):
    if row is None:
        return None
    synthetic = getattr(row, "is_synthetic", False) is True
    return FundAttributesView(
        issuer=_text(row.issuer),
        underlying=_text(row.underlying),
        ter=_finite_number(row.ter),
        domicile=_text(row.domicile),
        replication_method=_text(row.replication_method),
        distribution_policy=_text(row.distribution_policy),
        aum=_finite_number(row.aum),
        aum_currency=_text(row.aum_currency),
        aum_as_of=_midnight(row.aum_as_of),
        as_of=_midnight(row.as_of),
        source=DEMO_SOURCE if synthetic else None,
        is_synthetic=synthetic,
    )


def _metric_view(metric):
    return DerivedMetricView(
        value=_finite_number(metric.value),
        reason=metric.reason,
        start=_midnight(metric.start),
        end=_midnight(metric.end),
        source=_text(metric.source),
    )


def _price_view(metrics):
    if metrics is None:
        return None
    return PriceMetricsView(
        source=_text(metrics.source),
        as_of=_midnight(metrics.as_of),
        return_1y=_metric_view(metrics.return_1y),
        return_3y=_metric_view(metrics.return_3y),
        volatility=_metric_view(metrics.volatility),
        max_drawdown=_metric_view(metrics.max_drawdown),
    )


def to_instrument(company, fund_attributes=None, price_metrics=None):
    """Map one company row and its metrics to an instrument view.

    ``fund_attributes`` is the stored ETF or ETC row, or None.
    ``price_metrics`` is the result of ``derive_price_metrics``, or
    None on the list, which does not compute them.
    """
    description = company.description
    # The column, not the description. A missing attribute (a stub
    # that predates the column) is not synthetic. Only a real True
    # counts, so a stored 0 or None stays off.
    is_synthetic = getattr(company, "is_synthetic", False) is True
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
        instrument_type=catalog_instrument_type(
            getattr(company, "instrument_type", None)
        ),
        ticker=_text(company.ticker),
        isin=_text(company.isin),
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
        fund_attributes=_fund_view(fund_attributes),
        price_metrics=_price_view(price_metrics),
    )
