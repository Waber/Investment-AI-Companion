"""Number and date formatting for the two UI languages.

``locale.setlocale`` is process-wide. One request in English would
change the format used by a Polish request running in the same
process, and a missing locale on the machine would raise. These
functions take the language as an argument and do not touch the
process locale. Dates are the UTC calendar date. The API still
returns ISO strings; this module is only for HTML.
"""

import math
from datetime import datetime

from app.core.utc_datetime import as_utc

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
