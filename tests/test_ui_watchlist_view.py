"""Watchlist rows: change, stale flag, and the sparkline.

The rows and bars are built in memory. Nothing here opens a database
or calls a market-data provider.
"""

from datetime import date
from decimal import Decimal

from app.models.database_models import CompanyDB, PriceBarDB, WatchlistItemDB
from app.repositories.price_bar_repository import RecentCloses
from app.ui.watchlist_view import sparkline, to_entry

TODAY = date(2026, 10, 27)


def _item(description=None, label=None):
    company = CompanyDB(
        id=7, name="Apple Inc.", ticker="AAPL", description=description
    )
    return WatchlistItemDB(company_id=7, company=company, label=label)


def _bar(day, close):
    return PriceBarDB(
        bar_date=day,
        close_price=Decimal(close),
        currency="USD",
        source="fake",
    )


def _recent(*bars):
    """Bars oldest first. The last one is ``latest``."""
    return RecentCloses(
        source="fake",
        latest=bars[-1],
        previous=bars[-2] if len(bars) > 1 else None,
        window=list(bars),
    )


def test_change_is_percent_against_the_previous_close():
    entry = to_entry(
        _item(label="long term"),
        _recent(
            _bar(date(2026, 10, 19), "100"), _bar(date(2026, 10, 26), "101.24")
        ),
        TODAY,
        7,
    )
    assert entry.change == Decimal("1.24")
    assert entry.direction == "up"
    assert entry.close == Decimal("101.24")
    assert entry.currency == "USD"
    assert entry.previous_date == date(2026, 10, 19)
    assert entry.latest_date == date(2026, 10, 26)
    assert entry.source == "fake"
    assert entry.label == "long term"
    assert (entry.name, entry.ticker, entry.company_id) == (
        "Apple Inc.",
        "AAPL",
        7,
    )


def test_change_is_missing_without_a_usable_previous_close():
    zero = to_entry(
        _item(),
        _recent(_bar(date(2026, 10, 19), "0"), _bar(date(2026, 10, 26), "5")),
        TODAY,
        7,
    )
    assert zero.change is None
    assert zero.direction is None
    single = to_entry(
        _item(), _recent(_bar(date(2026, 10, 26), "5")), TODAY, 7
    )
    assert single.change is None
    assert single.close == Decimal("5")


def test_falling_and_flat_changes_have_a_direction():
    down = to_entry(
        _item(),
        _recent(
            _bar(date(2026, 10, 19), "100"), _bar(date(2026, 10, 26), "99")
        ),
        TODAY,
        7,
    )
    assert down.change == Decimal("-1")
    assert down.direction == "down"
    flat = to_entry(
        _item(),
        _recent(
            _bar(date(2026, 10, 19), "100"), _bar(date(2026, 10, 26), "100")
        ),
        TODAY,
        7,
    )
    assert flat.direction == "flat"


def test_stale_boundary_is_more_than_the_setting():
    on_the_line = to_entry(
        _item(), _recent(_bar(date(2026, 10, 20), "1")), TODAY, 7
    )
    assert on_the_line.is_stale is False
    one_day_older = to_entry(
        _item(), _recent(_bar(date(2026, 10, 19), "1")), TODAY, 7
    )
    assert one_day_older.is_stale is True


def test_entry_without_prices_has_no_numbers_and_is_not_stale():
    entry = to_entry(_item(), None, TODAY, 7)
    assert entry.close is None
    assert entry.change is None
    assert entry.latest_date is None
    assert entry.sparkline is None
    assert entry.source is None
    assert entry.is_stale is False


def test_sparkline_scales_and_picks_a_direction():
    line = sparkline([Decimal("1"), Decimal("2"), Decimal("3")])
    points = [
        tuple(map(float, pair.split(","))) for pair in line.points.split()
    ]
    assert len(points) == 3
    assert points[0][0] == 0
    assert points[-1][0] == 90
    # A higher price is a smaller y.
    assert points[0][1] > points[-1][1]
    assert line.direction == "up"
    assert sparkline([Decimal("3"), Decimal("1")]).direction == "down"
    assert sparkline([Decimal("1")]) is None
    assert sparkline([]) is None


def test_flat_sparkline_is_a_line_in_the_middle():
    line = sparkline([Decimal("5")] * 3)
    ys = {float(pair.split(",")[1]) for pair in line.points.split()}
    assert ys == {12.0}
    assert line.direction == "flat"


def test_synthetic_company_is_flagged():
    entry = to_entry(
        _item(description="[IAC-DEMO-V2] Synthetic"), None, TODAY, 7
    )
    assert entry.is_synthetic is True
    assert (
        to_entry(_item(description="Real"), None, TODAY, 7).is_synthetic
        is False
    )


def test_change_that_rounds_to_zero_is_flat():
    """-0.004% is shown as 0.00, so it must not carry a red arrow."""
    entry = to_entry(
        _item(),
        _recent(
            _bar(date(2026, 10, 19), "3487.9709"),
            _bar(date(2026, 10, 26), "3487.83"),
        ),
        TODAY,
        7,
    )
    assert entry.change < 0
    assert entry.direction == "flat"
