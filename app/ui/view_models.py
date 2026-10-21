"""Read-side instrument view-models built from company rows.

Templates bind to these objects. They do not read ``CompanyDB``.
Issue #26 can swap the query that loads rows; the field names here
already match an instrument (type, source, synthetic flag, as-of).
A description that starts with the ``[IAC-DEMO-`` prefix is
synthetic. The type on the page is the stored ``instrument_type``
(``STOCK``, ``ETF``, or ``ETC``), shown through the catalog ids
``stock``, ``etf``, and ``etc``.
"""

import math
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

from app.core.utc_datetime import as_utc

# Fixture descriptions start with this prefix. The V1 marker is
# "[IAC-DEMO-V1]". Later fixtures, including V2, use the same
# prefix. Kept here so the UI does not import the seeder. The
# comparison in ``to_instrument`` is case-sensitive and does not
# strip the stored description.
DEMO_MARKER = "[IAC-DEMO-"
# Used when the marker has no short version token. A real token
# becomes ``demo-`` plus that token, such as ``demo-v2``.
DEMO_SOURCE = "demo"
# ``V1`` and ``V2`` are two characters. Sixteen is enough for a
# version word and too short for a pasted sentence.
_DEMO_TOKEN_MAX_LENGTH = 16
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
        metrics_id=getattr(row, "id", None),
    )


def demo_source_label(description):
    """Return the source label for one synthetic description.

    ``description`` already starts with ``[IAC-DEMO-``. The token
    is the text from there to the next ``]``. It is kept only when
    it is 1 to 16 ASCII letters or digits. The label is ``demo-``
    plus that token in lowercase, so ``[IAC-DEMO-V2]`` is
    ``demo-v2``. A missing ``]``, a space, a hyphen, or a longer
    token uses the neutral label ``demo``.
    """
    marker_length = len(DEMO_MARKER)
    rest = description[marker_length:]
    end = rest.find("]")
    if end < 1 or end > _DEMO_TOKEN_MAX_LENGTH:
        return DEMO_SOURCE
    token = rest[:end]
    if not token.isascii() or not token.isalnum():
        return DEMO_SOURCE
    return "demo-" + token.lower()


def catalog_instrument_type(value):
    """Return the catalog id for a stored instrument type.

    ``CompanyDB.instrument_type`` is ``STOCK``, ``ETF``, or ``ETC``.
    The templates look up ``type.`` plus ``stock``, ``etf``, or
    ``etc``, and the list filter compares those same ids. A missing
    value, or one outside the three names, is ``None`` so the page
    can show "no data" instead of calling the row a stock.
    ``InstrumentType`` is a ``str`` enum, so a member is accepted
    here too.
    """
    if not isinstance(value, str):
        return None
    return _CATALOG_INSTRUMENT_TYPES.get(value.strip().upper())


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
        source=demo_source_label(description) if is_synthetic else None,
        is_synthetic=is_synthetic,
        as_of=latest,
        annual=annual,
        quarterly=quarterly,
        other=other,
    )
