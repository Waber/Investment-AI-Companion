"""Price returns, volatility, and drawdown from stored closes.

These numbers are computed here from closes the caller already has.
This module does not call a market-data provider.

A close is usable only when it is a finite number greater than zero.
``None``, zero, a negative number, and a non-finite value are
skipped. They are not turned into a price of zero. When two closes
share a date, the later one in the input is kept.

The as-of date is the date of the last usable close.

One-year and three-year total price return
-------------------------------------------
``T`` is the as-of date. The one-year anchor is the latest usable
close on or before the same calendar day one year earlier. The
three-year anchor uses three years. When that earlier year has no
February 29, February 29 steps back to February 28.

The total price return is ``end / start - 1``. It is not annualized.
A price bar has no dividend, so this is a price return, not a total
return with distributions reinvested. When no usable close falls on
or before the anchor date, the value is ``None`` and the reason is
``insufficient_history``.

Annualized volatility and maximum drawdown
-------------------------------------------
Both use the closes from the one-year anchor through the as-of date,
including both ends. They are one-year figures so two instruments
use the same kind of window. The start and end on the result are
that window.

Volatility is the sample standard deviation of the close-to-close
log returns, times the square root of how many of those gaps fit
into 365.25 days::

    mean_gap = average number of days between closes
    periods_per_year = 365.25 / mean_gap
    volatility = stdev(ln(close / previous)) * sqrt(periods_per_year)

The sample standard deviation divides by ``n - 1``, so two log
returns (three closes) are required. A one-day gap and a one-week
gap are both allowed. The average gap is what annualizes the
series, which is why weekly demo bars and daily bars share this
function. This is not the 252-trading-day convention.

Maximum drawdown is the smallest ``price / running_peak - 1`` in
that window. It is ``0`` when the price never falls, and negative
when it does. Two closes are enough. A window that cannot be
formed is not reported as zero.

When the input has no usable close, every metric has the reason
``no_prices``. When a series exists but one metric cannot be
computed, the reason is ``insufficient_history``. A computed
metric has reason ``None``. Each metric repeats the series source.
The as-of date is set once a usable close exists.
"""

import math
import statistics
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

REASON_NO_PRICES = "no_prices"
REASON_INSUFFICIENT_HISTORY = "insufficient_history"


@dataclass(frozen=True)
class DerivedMetric:
    """One computed number, or a reason it could not be computed.

    ``value`` and ``reason`` are never both set. ``start`` and
    ``end`` are the closes that were used, and they are set only
    together with a value. ``source`` is the price series the
    caller named.
    """

    value: float | None
    reason: str | None
    start: date | None
    end: date | None
    as_of: date | None
    source: str | None


@dataclass(frozen=True)
class PriceDerivedMetrics:
    """The four metrics for one price series."""

    source: str | None
    as_of: date | None
    return_1y: DerivedMetric
    return_3y: DerivedMetric
    volatility: DerivedMetric
    max_drawdown: DerivedMetric


def derive_price_metrics(points, source):
    """Return the four metrics for ``points``.

    ``points`` is an iterable of ``(date, close)``. The dates do
    not have to be sorted. ``source`` is the name of that series.
    A blank source is a caller error.
    """
    if source is None:
        # No series was chosen. A later usable close still needs a name.
        named = None
    elif not isinstance(source, str) or not source.strip():
        raise ValueError("source must not be blank")
    else:
        named = source
    source = named
    usable = _usable_closes(points)
    if usable and source is None:
        raise ValueError("source must not be blank")
    if not usable:
        missing = _missing(REASON_NO_PRICES, source, None)
        return PriceDerivedMetrics(
            source=source,
            as_of=None,
            return_1y=missing,
            return_3y=missing,
            volatility=missing,
            max_drawdown=missing,
        )
    as_of, end_price = usable[-1]
    one_year = _price_return(usable, as_of, 1, end_price, source)
    three_year = _price_return(usable, as_of, 3, end_price, source)
    volatility, drawdown = _one_year_risk(usable, one_year, as_of, source)
    return PriceDerivedMetrics(
        source=source,
        as_of=as_of,
        return_1y=one_year,
        return_3y=three_year,
        volatility=volatility,
        max_drawdown=drawdown,
    )


def _usable_closes(points):
    """Positive closes, one per date, oldest first.

    A later row for the same date replaces the earlier close.
    """
    latest = {}
    for day, raw in points:
        if not isinstance(day, date):
            continue
        price = _positive_price(raw)
        if price is None:
            continue
        latest[day] = price
    return [(day, latest[day]) for day in sorted(latest)]


def _positive_price(raw):
    """A finite price above zero, or None when the close is unusable."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, Decimal):
        number = raw
    elif isinstance(raw, (int, float)):
        if isinstance(raw, float) and not math.isfinite(raw):
            return None
        number = Decimal(str(raw))
    else:
        return None
    if not number.is_finite() or number <= 0:
        return None
    return number


def _years_before(day, years):
    """The same month and day, ``years`` earlier.

    February 29 becomes February 28 when the target year is not a
    leap year. ``date.replace`` raises ``ValueError`` for that one
    case.
    """
    try:
        return day.replace(year=day.year - years)
    except ValueError:
        return day.replace(year=day.year - years, day=28)


def _anchor(closes, target):
    """The latest close on or before ``target``, or None."""
    chosen = None
    for day, price in closes:
        if day <= target:
            chosen = (day, price)
        else:
            break
    return chosen


def _missing(reason, source, as_of):
    return DerivedMetric(
        value=None,
        reason=reason,
        start=None,
        end=None,
        as_of=as_of,
        source=source,
    )


def _price_return(closes, as_of, years, end_price, source):
    start = _anchor(closes, _years_before(as_of, years))
    if start is None:
        return _missing(REASON_INSUFFICIENT_HISTORY, source, as_of)
    start_day, start_price = start
    return DerivedMetric(
        value=float(end_price / start_price - 1),
        reason=None,
        start=start_day,
        end=as_of,
        as_of=as_of,
        source=source,
    )


def _one_year_risk(closes, one_year, as_of, source):
    """Volatility and drawdown on the one-year window.

    Drawdown needs two closes. Volatility needs two log returns.
    Either one can be missing while the other is present.
    """
    if one_year.start is None:
        missing = _missing(REASON_INSUFFICIENT_HISTORY, source, as_of)
        return missing, missing
    # The anchor is on or before as-of minus one year, and as-of is
    # the last close, so the window always holds at least those two.
    window = [row for row in closes if row[0] >= one_year.start]
    drawdown = DerivedMetric(
        value=float(_max_drawdown(window)),
        reason=None,
        start=one_year.start,
        end=as_of,
        as_of=as_of,
        source=source,
    )
    volatility = _volatility(window, one_year.start, as_of, source)
    return volatility, drawdown


def _volatility(window, start, as_of, source):
    returns = []
    gaps = []
    previous_day, previous_price = window[0]
    for day, price in window[1:]:
        gap = (day - previous_day).days
        if gap > 0:
            returns.append(math.log(float(price / previous_price)))
            gaps.append(gap)
        previous_day, previous_price = day, price
    if len(returns) < 2:
        return _missing(REASON_INSUFFICIENT_HISTORY, source, as_of)
    mean_gap = sum(gaps) / len(gaps)
    periods_per_year = 365.25 / mean_gap
    value = statistics.stdev(returns) * math.sqrt(periods_per_year)
    return DerivedMetric(
        value=value,
        reason=None,
        start=start,
        end=as_of,
        as_of=as_of,
        source=source,
    )


def _max_drawdown(window):
    """The worst peak-to-trough change, as a fraction of the peak.

    Zero means the close never fell below a peak. A fall is negative.
    """
    peak = window[0][1]
    worst = Decimal(0)
    for _day, price in window:
        if price > peak:
            peak = price
        change = price / peak - 1
        if change < worst:
            worst = change
    return worst
