"""Number and date formatting for the two UI languages.

``locale.setlocale`` is process-wide. One request in English would
change the format used by a Polish request running in the same
process, and a missing locale on the machine would raise. These
functions take the language as an argument and do not touch the
process locale. Dates are the UTC calendar date. The API still
returns ISO strings; this module is only for HTML.
"""

import math
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal

from app.core.utc_datetime import as_utc

# A price shows at least 2 decimals. Prices of 0.1 and up keep up to
# 4. A smaller price keeps enough places for 4 significant digits,
# up to 8, the stored scale, so 0.00006 is not shown as 0.0001.
_PRICE_MIN_PLACES = 2
_PRICE_MAX_PLACES = 4
_PRICE_SIGNIFICANT_DIGITS = 4
_PRICE_STORED_PLACES = 8

# Thousands separator, then the decimal mark.
_NUMBER_SEPARATORS = {
    "pl": ("\u00a0", ","),
    "en": (",", "."),
}
_ENGLISH_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def format_number(value, language):
    """Format a finite number, or return None when it is missing.

    Zero stays zero. ``None``, booleans, and non-finite values return
    None so the template can show the "no data" string instead of 0.
    Polish uses a non-breaking space between thousands and a comma as
    the decimal mark. English uses a comma and a dot.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    separators = _NUMBER_SEPARATORS.get(language, _NUMBER_SEPARATORS["pl"])
    thousands, decimal_mark = separators
    sign = "-" if number < 0 else ""
    rounded = round(abs(number), 4)
    if float(rounded).is_integer():
        whole = str(int(rounded))
        fraction = ""
    else:
        whole, fraction = f"{rounded:.4f}".rstrip("0").split(".")
    groups = []
    digits = whole
    while digits:
        groups.append(digits[-3:])
        digits = digits[:-3]
    body = thousands.join(reversed(groups))
    if fraction:
        body = f"{body}{decimal_mark}{fraction}"
    return f"{sign}{body}"


def format_date(value, language):
    """Format a datetime as a UTC calendar date, or return None.

    Polish is ``31.12.2025``. English is ``Dec 31, 2025``, with the
    month written out here so the result does not depend on
    ``LC_TIME``. Any language other than English uses the Polish form.
    """
    if not isinstance(value, datetime):
        return None
    utc = as_utc(value)
    if language == "en":
        month = _ENGLISH_MONTHS[utc.month - 1]
        return f"{month} {utc.day}, {utc.year}"
    return f"{utc.day:02d}.{utc.month:02d}.{utc.year}"


def _group_thousands(digits, separator):
    """Insert ``separator`` every three digits from the right."""
    groups = []
    while digits:
        groups.append(digits[-3:])
        digits = digits[:-3]
    return separator.join(reversed(groups)) or "0"


def _decimal_text(value, places, min_places, language):
    """``value`` rounded half-even to ``places``, in the UI language.

    Trailing zeros past ``min_places`` are dropped. Everything stays
    a ``Decimal`` or a string, so no digit passes through ``float``.
    """
    rounded = value.quantize(
        Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN
    )
    sign = "-" if rounded < 0 else ""
    whole, _, fraction = f"{abs(rounded):f}".partition(".")
    fraction = fraction.rstrip("0").ljust(min_places, "0")
    thousands, decimal_mark = _NUMBER_SEPARATORS.get(
        language, _NUMBER_SEPARATORS["pl"]
    )
    body = _group_thousands(whole, thousands)
    if fraction:
        body = f"{body}{decimal_mark}{fraction}"
    return f"{sign}{body}"


def format_price(value, language):
    """Format a ``Decimal`` price, or return None when it is missing.

    ``227.50000000`` is ``227,50`` in Polish and ``227.50`` in
    English. Up to four decimals are kept (``3 487,9709``). A price
    below 0.1 keeps four significant digits, up to eight places, so
    ``0.00123456`` is ``0,001235`` and ``0.00006`` is not
    ``0,0001``. A ``float`` is never used: prices are stored as
    exact decimals (#94).
    """
    if not isinstance(value, Decimal) or not value.is_finite():
        return None
    places = _PRICE_MAX_PLACES
    if value != 0:
        # ``adjusted`` is the exponent of the first significant digit:
        # -5 for 0.00006. Places to the 4th significant digit are
        # 3 - adjusted.
        needed = _PRICE_SIGNIFICANT_DIGITS - 1 - value.adjusted()
        places = min(_PRICE_STORED_PLACES, max(places, needed))
    return _decimal_text(value, places, _PRICE_MIN_PLACES, language)


def format_change(value, language):
    """Format a percent change with a sign and two decimals.

    ``1.2449`` is ``+1,24`` in Polish. Zero has no sign. The value is
    the percent itself, not a fraction. None stays None.
    """
    if not isinstance(value, Decimal) or not value.is_finite():
        return None
    text = _decimal_text(value, 2, 2, language)
    if value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN) > 0:
        return f"+{text}"
    return text


def format_day(value, language):
    """Format a calendar ``date`` the way ``format_date`` does.

    A price bar has a date and no time, so there is no UTC step.
    """
    if not isinstance(value, date) or isinstance(value, datetime):
        return None
    if language == "en":
        month = _ENGLISH_MONTHS[value.month - 1]
        return f"{month} {value.day}, {value.year}"
    return f"{value.day:02d}.{value.month:02d}.{value.year}"
