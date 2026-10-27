"""Locale-aware numbers and dates, without setlocale."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.ui.formatting import (
    format_change,
    format_date,
    format_day,
    format_number,
    format_price,
)


def test_missing_and_non_finite_numbers_are_not_zero():
    assert format_number(None, "pl") is None
    assert format_number(True, "en") is None
    assert format_number(False, "pl") is None
    assert format_number(float("nan"), "pl") is None
    assert format_number(float("inf"), "en") is None
    assert format_number("100", "pl") is None


def test_zero_stays_zero_in_both_languages():
    assert format_number(0, "pl") == "0"
    assert format_number(0.0, "en") == "0"
    assert format_number(-0.0, "pl") == "0"


def test_thousands_and_decimals_follow_the_language():
    assert format_number(10000000, "pl") == "10\u00a0000\u00a0000"
    assert format_number(10000000, "en") == "10,000,000"
    assert format_number(-2000000, "pl") == "-2\u00a0000\u00a0000"
    assert format_number(-2000000, "en") == "-2,000,000"
    assert format_number(15.6, "pl") == "15,6"
    assert format_number(15.6, "en") == "15.6"
    assert format_number(100000, "de") == "100\u00a0000"


def test_dates_use_the_utc_calendar_day():
    instant = datetime(2025, 12, 31, tzinfo=timezone.utc)
    assert format_date(instant, "pl") == "31.12.2025"
    assert format_date(instant, "en") == "Dec 31, 2025"
    assert format_date(instant, "de") == "31.12.2025"
    # 00:30 at UTC+2 is still the previous UTC date.
    shifted = datetime(2026, 4, 1, 0, 30, tzinfo=timezone(timedelta(hours=2)))
    assert format_date(shifted, "pl") == "31.03.2026"
    assert format_date(shifted, "en") == "Mar 31, 2026"
    naive = datetime(2026, 3, 31)
    assert format_date(naive, "en") == "Mar 31, 2026"
    assert format_date(None, "pl") is None
    assert format_date("2026-03-31", "en") is None


def test_price_keeps_two_to_four_decimals_from_decimal():
    assert format_price(Decimal("227.50000000"), "pl") == "227,50"
    assert format_price(Decimal("7.37600000"), "pl") == "7,376"
    assert format_price(Decimal("3487.97090000"), "pl") == "3\u00a0487,9709"
    assert format_price(Decimal("3487.97090000"), "en") == "3,487.9709"
    # Rounded half-even in Decimal, not through float.
    assert format_price(Decimal("1.23456789"), "en") == "1.2346"
    assert format_price(None, "pl") is None


def test_tiny_price_is_not_shown_as_zero():
    """Four places would turn this price into 0.0000."""
    assert format_price(Decimal("0.00001234"), "en") == "0.00001234"
    assert format_price(Decimal("0E-8"), "en") == "0.00"


def test_price_never_goes_through_float():
    """Near 1e12 a float is 999999999999.000244..., which reads .0002."""
    assert (
        format_price(Decimal("999999999999.0003"), "en")
        == "999,999,999,999.0003"
    )


def test_change_has_a_sign_and_two_decimals():
    assert format_change(Decimal("1.2449"), "pl") == "+1,24"
    assert format_change(Decimal("-0.625"), "en") == "-0.62"
    assert format_change(Decimal("0"), "en") == "0.00"
    assert format_change(None, "en") is None


def test_day_formats_a_calendar_date():
    assert format_day(date(2026, 9, 28), "pl") == "28.09.2026"
    assert format_day(date(2026, 9, 28), "en") == "Sep 28, 2026"
    assert format_day(None, "pl") is None
