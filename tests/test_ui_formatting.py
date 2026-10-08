"""Locale-aware numbers and dates, without setlocale."""

from datetime import datetime, timedelta, timezone

from app.ui.formatting import format_date, format_number


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
