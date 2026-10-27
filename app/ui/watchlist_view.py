"""Watchlist rows as the /ui templates render them.

Each row joins a watchlist item, its company, and the recent closes of
the company's default price series. Prices stay ``Decimal``. Only the
sparkline coordinates use ``float``, because they place pixels and are
never shown as text.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.database_models import WatchlistItemDB
from app.repositories.price_bar_repository import (
    PriceBarRepository,
    RecentCloses,
)
from app.repositories.watchlist_repository import WatchlistRepository
from app.ui.view_models import DEMO_MARKER

# The sparkline viewBox. The template draws it at this size.
SPARKLINE_WIDTH = 90
SPARKLINE_HEIGHT = 24
# Keeps the line off the top and bottom edge of the box.
_SPARKLINE_PADDING = 1


def utc_today() -> date:
    """Today's UTC date. Tests replace this to freeze the stale check."""
    return datetime.now(timezone.utc).date()


@dataclass(frozen=True)
class Sparkline:
    """``points`` for an SVG ``<polyline>``, and the colour to use."""

    points: str
    direction: str


@dataclass(frozen=True)
class WatchlistEntryView:
    """One watchlist row. ``None`` is shown as the "no data" dash."""

    company_id: int
    name: str | None
    ticker: str | None
    label: str | None
    is_synthetic: bool
    close: Decimal | None
    currency: str | None
    change: Decimal | None
    direction: str | None
    previous_date: date | None
    latest_date: date | None
    source: str | None
    is_stale: bool
    sparkline: Sparkline | None


def _direction(first: Decimal, last: Decimal) -> str:
    if last > first:
        return "up"
    if last < first:
        return "down"
    return "flat"


def _coordinate(value: float) -> str:
    """One decimal is enough for a 90 by 24 box. ``12.0`` is ``12``."""
    return f"{round(value, 1):g}"


def sparkline(
    closes: list[Decimal],
    width: int = SPARKLINE_WIDTH,
    height: int = SPARKLINE_HEIGHT,
) -> Sparkline | None:
    """Scale ``closes`` (oldest first) into the box, or None.

    Fewer than two closes cannot draw a line. SVG y grows downward,
    so a higher price gets a smaller y. A flat series is a line in
    the middle instead of a division by zero.
    """
    if len(closes) < 2:
        return None
    low = min(closes)
    high = max(closes)
    usable = height - 2 * _SPARKLINE_PADDING
    step = width / (len(closes) - 1)
    points = []
    for index, close in enumerate(closes):
        if high == low:
            y = height / 2
        else:
            share = float((close - low) / (high - low))
            y = _SPARKLINE_PADDING + (1 - share) * usable
        points.append(f"{_coordinate(index * step)},{_coordinate(y)}")
    return Sparkline(
        points=" ".join(points), direction=_direction(closes[0], closes[-1])
    )


def _change(recent: RecentCloses) -> Decimal | None:
    """Percent change of the latest close against the previous one."""
    previous = recent.previous
    if previous is None or previous.close_price == 0:
        return None
    latest = recent.latest.close_price
    return (latest - previous.close_price) / previous.close_price * 100


def to_entry(
    item: WatchlistItemDB,
    recent: RecentCloses | None,
    today: date,
    stale_days: int,
) -> WatchlistEntryView:
    """Build one row. ``recent`` is None when the company has no closes.

    A price is stale when its date is more than ``stale_days`` days
    before ``today``. A row without prices is not marked stale: it
    says "no prices" instead.
    """
    company = item.company
    description = company.description
    is_synthetic = isinstance(description, str) and description.startswith(
        DEMO_MARKER
    )
    common = {
        "company_id": company.id,
        "name": company.name,
        "ticker": company.ticker,
        "label": item.label,
        "is_synthetic": is_synthetic,
    }
    if recent is None:
        return WatchlistEntryView(
            **common,
            close=None,
            currency=None,
            change=None,
            direction=None,
            previous_date=None,
            latest_date=None,
            source=None,
            is_stale=False,
            sparkline=None,
        )
    latest = recent.latest
    change = _change(recent)
    return WatchlistEntryView(
        **common,
        close=latest.close_price,
        currency=latest.currency,
        change=change,
        direction=None if change is None else _direction(Decimal(0), change),
        previous_date=(
            None if recent.previous is None else recent.previous.bar_date
        ),
        latest_date=latest.bar_date,
        source=recent.source,
        is_stale=latest.bar_date < today - timedelta(days=stale_days),
        sparkline=sparkline([bar.close_price for bar in recent.window]),
    )


def list_entries(
    db: Session, today: date | None = None
) -> list[WatchlistEntryView]:
    """Every watchlist row, in the repository order (oldest first).

    One price query per row. The list is short, and the query reads
    only the last few months of one series.
    """
    if today is None:
        today = utc_today()
    prices = PriceBarRepository(db)
    stale_days = settings.WATCHLIST_STALE_PRICE_DAYS
    return [
        to_entry(
            item, prices.recent_closes(item.company_id), today, stale_days
        )
        for item in WatchlistRepository(db).list_items()
    ]
