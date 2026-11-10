"""Price-derived metrics from a small series of closes.

The numbers below are calculated by hand from the formulas in
``app.price_metrics``. A series that does not reach the required
date returns None and a reason. A missing close is missing: it is
not stored or returned as zero.
"""

from datetime import date

import pytest

from app.price_metrics import (
    REASON_INSUFFICIENT_HISTORY,
    REASON_NO_PRICES,
    derive_price_metrics,
)

# ln(2) * sqrt(365.25 * 3 / 365), from the four-close series below.
# Intervals are 1, 1, and 363 days. The sample standard deviation of
# ln(2), -ln(2), and 0 is ln(2). See the module docstring.
_FOUR_CLOSE_VOLATILITY = 1.2009772162597356


def _values(points, source="fixture"):
    return derive_price_metrics(points, source)


def test_empty_series_has_no_prices():
    result = _values([])
    assert result.source == "fixture"
    assert result.as_of is None
    for metric in (
        result.return_1y,
        result.return_3y,
        result.volatility,
        result.max_drawdown,
    ):
        assert metric.value is None
        assert metric.reason == REASON_NO_PRICES
        assert metric.start is None
        assert metric.end is None
        assert metric.as_of is None
        assert metric.source == "fixture"


def test_non_positive_closes_are_not_a_series():
    """Zero and a negative close cannot be a ratio. They are skipped.

    When nothing usable remains, the result is no prices, not a zero
    return.
    """
    result = _values(
        [
            (date(2026, 1, 2), 0),
            (date(2026, 1, 3), -5),
            (date(2026, 1, 4), None),
        ]
    )
    assert result.as_of is None
    assert result.return_1y.value is None
    assert result.return_1y.reason == REASON_NO_PRICES


def test_one_close_is_insufficient_for_every_metric():
    result = _values([(date(2026, 1, 2), 100)])
    assert result.as_of == date(2026, 1, 2)
    assert result.source == "fixture"
    for metric in (
        result.return_1y,
        result.return_3y,
        result.volatility,
        result.max_drawdown,
    ):
        assert metric.value is None
        assert metric.reason == REASON_INSUFFICIENT_HISTORY
        assert metric.as_of == date(2026, 1, 2)
        assert metric.source == "fixture"
        assert metric.start is None
        assert metric.end is None


def test_hand_calculated_returns_volatility_and_drawdown():
    """Four closes. The one-year anchor is the first close.

    End close 100 over start close 100 is a 1y return of 0.
    Nothing is on or before 2023-01-02, so the 3y return is missing.

    Log returns are ln(2), ln(1/2), and ln(1). Drawdown from the
    peak of 200 back to 100 is -0.5.
    """
    points = [
        (date(2025, 1, 2), 100),
        (date(2025, 1, 3), 200),
        (date(2025, 1, 4), 100),
        (date(2026, 1, 2), 100),
    ]
    result = _values(list(reversed(points)), source="demo")
    assert result.as_of == date(2026, 1, 2)
    assert result.source == "demo"

    one_year = result.return_1y
    assert one_year.value == pytest.approx(0.0, abs=1e-12)
    assert one_year.reason is None
    assert one_year.start == date(2025, 1, 2)
    assert one_year.end == date(2026, 1, 2)
    assert one_year.as_of == date(2026, 1, 2)
    assert one_year.source == "demo"

    three_year = result.return_3y
    assert three_year.value is None
    assert three_year.reason == REASON_INSUFFICIENT_HISTORY
    assert three_year.start is None
    assert three_year.end is None

    assert result.volatility.value == pytest.approx(
        _FOUR_CLOSE_VOLATILITY, abs=1e-12
    )
    assert result.volatility.reason is None
    assert result.volatility.start == date(2025, 1, 2)
    assert result.volatility.end == date(2026, 1, 2)

    assert result.max_drawdown.value == pytest.approx(-0.5, abs=1e-12)
    assert result.max_drawdown.reason is None
    assert result.max_drawdown.start == date(2025, 1, 2)
    assert result.max_drawdown.end == date(2026, 1, 2)


def test_three_year_return_uses_the_close_on_or_before_the_anchor():
    """110 / 100 - 1 = 0.10 and 110 / 50 - 1 = 1.20.

    The one-year window has only two closes, so volatility needs
    another return and stays missing. The path never falls, so the
    drawdown is a real zero, not "no data".
    """
    result = _values(
        [
            (date(2023, 1, 2), 50),
            (date(2025, 1, 2), 100),
            (date(2026, 1, 2), 110),
        ]
    )
    assert result.return_1y.value == pytest.approx(0.10, abs=1e-12)
    assert result.return_1y.start == date(2025, 1, 2)
    assert result.return_3y.value == pytest.approx(1.20, abs=1e-12)
    assert result.return_3y.start == date(2023, 1, 2)
    assert result.return_3y.end == date(2026, 1, 2)
    assert result.volatility.value is None
    assert result.volatility.reason == REASON_INSUFFICIENT_HISTORY
    assert result.max_drawdown.value == pytest.approx(0.0, abs=1e-12)
    assert result.max_drawdown.reason is None


def test_anchor_is_the_latest_close_on_or_before_the_target_date():
    """2025-01-03 is after the one-year target, so it is not the start.

    80 / 40 - 1 = 1. The start date is 2024-12-31.
    """
    result = _values(
        [
            (date(2024, 12, 31), 40),
            (date(2025, 1, 3), 100),
            (date(2026, 1, 2), 80),
        ]
    )
    assert result.return_1y.value == pytest.approx(1.0, abs=1e-12)
    assert result.return_1y.start == date(2024, 12, 31)


def test_february_29_steps_back_to_february_28():
    """2024-02-29 minus one year is 2023-02-28. 100 / 80 - 1 = 0.25."""
    result = _values(
        [
            (date(2023, 2, 28), 80),
            (date(2024, 2, 29), 100),
        ]
    )
    assert result.as_of == date(2024, 2, 29)
    assert result.return_1y.value == pytest.approx(0.25, abs=1e-12)
    assert result.return_1y.start == date(2023, 2, 28)
    assert result.return_3y.value is None
    assert result.return_3y.reason == REASON_INSUFFICIENT_HISTORY


def test_duplicate_dates_keep_the_later_close():
    """The second close on 2025-01-02 replaces 10. 150 / 100 - 1 = 0.5."""
    result = _values(
        [
            (date(2025, 1, 2), 10),
            (date(2025, 1, 2), 100),
            (date(2026, 1, 2), 150),
        ]
    )
    assert result.return_1y.value == pytest.approx(0.5, abs=1e-12)
    assert result.return_1y.start == date(2025, 1, 2)


def test_a_non_positive_close_is_skipped_before_the_anchor_search():
    """The zero on the anchor date is ignored. 80 / 100 - 1 = -0.2."""
    result = _values(
        [
            (date(2024, 1, 2), 100),
            (date(2025, 1, 2), 0),
            (date(2026, 1, 2), 80),
        ]
    )
    assert result.return_1y.value == pytest.approx(-0.2, abs=1e-12)
    assert result.return_1y.start == date(2024, 1, 2)


def test_blank_source_is_rejected():
    with pytest.raises(ValueError, match="source"):
        derive_price_metrics([(date(2026, 1, 2), 1)], "  ")


def test_a_missing_source_is_kept_only_when_there_is_no_series():
    """The detail route has no series name when the instrument has no bars."""
    result = derive_price_metrics([], None)
    assert result.source is None
    assert result.return_1y.reason == REASON_NO_PRICES
    assert result.return_1y.source is None
    with pytest.raises(ValueError, match="source"):
        derive_price_metrics([(date(2026, 1, 2), 1)], None)
