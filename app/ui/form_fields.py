"""Turn an HTML form into the Pydantic models the API already uses.

The browser posts strings. Empty optional company fields become
``None`` (a blank website is "no website", not the empty string).
Empty metric numbers become ``None``, which is "no data" on the
detail page. ``normalized_company_name`` is the one name rule for
create and for edit. It calls ``clean_text`` with
``COMPANY_NAME_MAX``. ``TextValidationError.code`` is mapped to a
catalog key: ``blank`` is ``error.required``, ``too_long`` is
``error.too_long``, and ``control_char``, ``bidi``, and
``surrogate`` are ``error.invalid``.
The text the user typed is kept for the
other fields and handed to ``CompanyCreate``, ``CompanyUpdate``,
``FinancialMetricsCreate``, or ``FinancialMetricsUpdate``. Those
models own the ticker, currency, length, URL, date, and finite-number
rules. This module does not add a second copy of them.

``FinancialMetricsUpdate`` has no ``period_type`` and no
``company_id``. An edit form shows the period type and then drops it
before validation, so a posted value cannot move the row to another
type or another company. ``period_end`` is required on that model
when it is sent; a blank value is a validation error, not a cleared
column. A value with no time zone is stored as UTC by the repository.

Validation failures carry catalog keys, not the English sentence
from Pydantic, so the page can render Polish or English. The user's
raw strings are returned unchanged for the inputs.
"""

import math
from datetime import datetime

from pydantic import ValidationError

from app.core.utc_datetime import as_utc
from app.models.company import (
    COMPANY_NAME_MAX,
    CompanyCreate,
    CompanyUpdate,
    InstrumentType,
)
from app.models.financial_metrics import (
    FinancialMetricsCreate,
    FinancialMetricsUpdate,
)
from app.ui.view_models import METRIC_FIELDS
from app.validation.text import TextValidationError, clean_text

# The option values are the enum the write models already accept.
# The visible words are the ``type.*`` catalog entries.
INSTRUMENT_TYPE_CHOICES = tuple(member.value for member in InstrumentType)
COMPANY_FIELDS = (
    "name",
    "ticker",
    "isin",
    "instrument_type",
    "exchange",
    "currency",
    "country",
    "sector",
    "industry",
    "website",
    "description",
)
_OPTIONAL_COMPANY = frozenset(COMPANY_FIELDS) - {"name", "ticker"}
_NUMBER_KINDS = frozenset(
    {
        "float_parsing",
        "float_type",
        "int_parsing",
        "int_type",
        "finite_number",
        "decimal_parsing",
        "decimal_type",
    }
)
# Metric repository messages. A company duplicate is not decided
# here and not by the sentence. The form reads
# ``DuplicateTickerError.code`` and ``DuplicateIsinError.code``.
# An unknown message is error.constraint.
_VALUE_ERROR_KEYS = {
    (
        "Financial metrics for this company, period end, "
        "and period type must be unique"
    ): "error.duplicate_metrics",
    "Failed to create financial metrics": "error.constraint",
    "Update failed due to constraint violation": "error.constraint",
}


def field_label_key(field):
    """Catalog key for one form field's label.

    The type control posts ``instrument_type``. Its label is the
    same ``field.type`` string the detail page already uses.
    """
    if field in METRIC_FIELDS:
        return "metric." + field
    if field == "instrument_type":
        return "field.type"
    return "field." + field


def blank_company():
    """Empty strings for a create form."""
    return {field: "" for field in COMPANY_FIELDS}


def blank_metrics():
    """Empty strings for a create-metrics form."""
    values = {field: "" for field in METRIC_FIELDS}
    values["period_end"] = ""
    values["period_type"] = ""
    return values


def _text(value):
    if value is None:
        return ""
    return str(value)


def company_values(row):
    """Stored company columns, as the edit form should show them."""
    return {
        field: _text(getattr(row, field, None)) for field in COMPANY_FIELDS
    }


def _input_number(value):
    """A number the form can post back through Pydantic.

    Locale formatting is for the read-only table. A comma or a
    no-break space would fail float parsing on the way back in.
    """
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        if value.is_integer():
            return str(int(value))
        return format(value, ".12g")
    if isinstance(value, int):
        return str(value)
    return _text(value)


def _input_datetime(value):
    """UTC wall time to the second, with no zone suffix.

    ``datetime-local`` is not used. A plain text field lets an invalid
    value reach the server, which is what the validation tests post.
    The repository treats a zone-less value as UTC.
    """
    if not isinstance(value, datetime):
        return ""
    return as_utc(value).strftime("%Y-%m-%dT%H:%M:%S")


def metrics_values(row):
    """Stored metrics, as the edit form should show them."""
    values = {
        field: _input_number(getattr(row, field, None))
        for field in METRIC_FIELDS
    }
    values["period_end"] = _input_datetime(getattr(row, "period_end", None))
    values["period_type"] = _text(getattr(row, "period_type", None))
    return values


# clean_text codes for the company name, and the catalog key the
# form already has for that kind of failure. blank is "required":
# an empty name is a missing name. too_long is the sentence a
# 256-character name already showed. The other three are invalid
# characters. There is no separate sentence for each of them.
# A code that is not in this map uses error.invalid, so a new code
# cannot turn the page into a 500.
_NAME_ERROR_KEYS = {
    "blank": "error.required",
    "too_long": "error.too_long",
    "control_char": "error.invalid",
    "bidi": "error.invalid",
    "surrogate": "error.invalid",
}


def normalized_company_name(value):
    """Return the name ``clean_text`` stores, or raise.

    Create and edit both call this. ``TextValidationError`` means
    the form answers 422 and does not save. The caller reads
    ``code`` and picks a catalog key. A returned string is what
    ``normalize_name`` stores for the same input, except a name
    that is only too long: this function raises ``too_long``, and
    ``normalize_name`` returns the stripped text so the HTTP API
    can keep Pydantic's ``string_too_long``.

    ``None`` and any other non-string become ``""`` first. The HTML
    form posts strings. A missing name is blank, not a crash.
    ``str`` on an unexpected object is the same conversion the form
    used before this helper called ``clean_text``.

    Character rules live in ``clean_text``. A mark with no base
    letter is blank there, so the form and the API reject it with
    the same code. A format character beside a letter is kept,
    including ZWNJ (U+200C) in a Persian name.
    """
    if not isinstance(value, str):
        value = "" if value is None else str(value)
    return clean_text(
        value,
        field="name",
        max_len=COMPANY_NAME_MAX,
        allow_newlines=False,
        allow_blank=False,
    )


def company_name_error_key(value):
    """Catalog key for one company name, or None when it is acceptable.

    ``None`` means create and edit may store the name. A key means
    the form shows that sentence and does not save.
    """
    try:
        normalized_company_name(value)
    except TextValidationError as exc:
        return _NAME_ERROR_KEYS.get(exc.code, "error.invalid")
    return None


def instrument_type_for_payload(value):
    """Return the type to validate, or None when the field is omitted.

    None means the key stays out of the payload. Create then uses
    the ``CompanyCreate`` default (STOCK). Update leaves the stored
    column, because ``CompanyUpdate`` rejects an explicit null.
    Spaces count as omitted. A control character is returned
    unchanged: ``normalize_instrument_type`` rejects newline and
    DEL before ``strip``, and ``str.strip`` would hide a trailing
    newline and store ETF.
    Any other text is stripped. The model still uppercases it, so
    ``etf`` and `` ETF `` become ETF.
    """
    if not isinstance(value, str):
        value = "" if value is None else str(value)
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return value
    text = value.strip()
    if not text:
        return None
    return text


def company_payload(values):
    """Map posted strings onto company create/update fields.

    The name goes through ``normalized_company_name``, the helper
    create and edit share. When that helper accepts the name, the
    payload is the same string ``clean_text`` returns. A rejected
    name stays a string (the stripped text) so the write model
    still receives ``str``. The 422 is applied in
    ``validate_company``, which reads the error code. Ticker text
    is left as typed;
    ``normalize_ticker`` strips and uppercases that field. A blank
    ISIN is ``None`` (unknown), not the empty string. The instrument
    type goes through ``instrument_type_for_payload``.
    """
    payload = {}
    for field in COMPANY_FIELDS:
        raw = values.get(field, "")
        if not isinstance(raw, str):
            raw = "" if raw is None else str(raw)
        if field == "name":
            try:
                payload[field] = normalized_company_name(raw)
            except TextValidationError:
                # raw is already a str. strip() removes whitespace
                # only. A control in the middle stays in the string
                # the model receives. validate_company still rejects
                # the original text, including a newline that
                # strip() would have hidden.
                payload[field] = raw.strip()
        elif field == "instrument_type":
            typed = instrument_type_for_payload(raw)
            if typed is not None:
                payload[field] = typed
        elif field in _OPTIONAL_COMPANY and raw.strip() == "":
            payload[field] = None
        else:
            payload[field] = raw
    return payload


def metrics_payload(values, company_id, *, include_period_type):
    """Map posted strings onto a metrics create or update model.

    ``company_id`` comes from the URL. A hidden form field cannot
    point the row at another company. ``period_type`` is included
    only on create, because the update model does not have it.
    """
    payload = {}
    period_end = values.get("period_end", "")
    if not isinstance(period_end, str):
        period_end = ""
    payload["period_end"] = period_end.strip()
    if include_period_type:
        period_type = values.get("period_type", "")
        if not isinstance(period_type, str):
            period_type = ""
        payload["period_type"] = period_type
        payload["company_id"] = company_id
    for field in METRIC_FIELDS:
        raw = values.get(field, "")
        if not isinstance(raw, str):
            raw = "" if raw is None else str(raw)
        if raw.strip() == "":
            payload[field] = None
        else:
            payload[field] = raw.strip()
    return payload


def catalog_key_for(field, kind, message):
    """Pick a catalog key for one Pydantic error."""
    if kind == "missing":
        return "error.required"
    if kind == "string_too_long":
        return "error.too_long"
    if kind in {"string_too_short", "too_short"}:
        return "error.too_short"
    if field == "instrument_type" and kind == "value_error":
        return "error.instrument_type"
    if field == "ticker" or kind == "string_pattern_mismatch":
        return "error.ticker"
    if field == "currency" or (
        kind == "value_error" and "currency" in message
    ):
        return "error.currency"
    if field == "website" or kind.startswith("url"):
        return "error.website"
    if field == "period_end" or "datetime" in kind or kind.startswith("date"):
        return "error.datetime"
    if (
        field in METRIC_FIELDS
        or kind in _NUMBER_KINDS
        or kind == "finite_number"
    ):
        return "error.number"
    if kind == "value_error" and "ticker" in message:
        return "error.ticker"
    return "error.invalid"


def errors_from_validation(exc, field_order):
    """Return ``(field_errors, form_error_key)``.

    ``field_errors`` keeps the form's field order. The value is a
    catalog key. The first error for a field wins.
    """
    found = {}
    form_key = None
    for error in exc.errors():
        loc = error.get("loc") or ()
        field = loc[-1] if loc else None
        if not isinstance(field, str):
            field = None
        key = catalog_key_for(
            field,
            str(error.get("type") or ""),
            str(error.get("msg") or ""),
        )
        if field is None:
            if form_key is None:
                form_key = key
            continue
        if field not in found:
            found[field] = key
    ordered = {}
    for name in field_order:
        if name in found:
            ordered[name] = found.pop(name)
    ordered.update(found)
    return ordered, form_key


def catalog_key_for_repository_error(exc):
    """Map a metrics repository ``ValueError`` to a catalog key.

    Company duplicates are not in this table. The form reads
    ``code`` on ``DuplicateTickerError`` and ``DuplicateIsinError``.
    """
    return _VALUE_ERROR_KEYS.get(str(exc), "error.constraint")


def validate_company(values, *, update):
    """Return ``(model, field_errors, form_error_key)``.

    ``model`` is None when validation failed. The raw ``values`` stay
    with the caller for the inputs. Create (``update`` false) and
    edit (``update`` true) both use ``normalized_company_name``.
    The catalog key comes from ``TextValidationError.code``. A name
    the checker rejects is not saved, including when ``strip`` would
    have turned the posted text into a name the model accepts.
    """
    model_type = CompanyUpdate if update else CompanyCreate
    try:
        model = model_type.model_validate(company_payload(values))
    except ValidationError as exc:
        errors, form_key = errors_from_validation(exc, COMPANY_FIELDS)
        model = None
    else:
        errors, form_key = {}, None
    name_key = company_name_error_key(values.get("name", ""))
    if name_key is not None:
        rest = {key: value for key, value in errors.items() if key != "name"}
        errors = {"name": name_key, **rest}
        model = None
    return model, errors, form_key


def validate_metrics(values, company_id, *, update):
    """Return ``(model, field_errors, form_error_key)`` for one period."""
    model_type = FinancialMetricsUpdate if update else FinancialMetricsCreate
    payload = metrics_payload(
        values, company_id, include_period_type=not update
    )
    order = ("period_end",) if update else ("period_end", "period_type")
    order = order + METRIC_FIELDS
    try:
        model = model_type.model_validate(payload)
    except ValidationError as exc:
        errors, form_key = errors_from_validation(exc, order)
        return None, errors, form_key
    return model, {}, None


def described_by(field, errors, form_error, invalid_fields, hints):
    """Space-separated ids for ``aria-describedby``, or an empty string."""
    parts = []
    hint = hints.get(field)
    if hint:
        parts.append(hint)
    if field in errors:
        parts.append("field-" + field + "-error")
    elif form_error and field in invalid_fields:
        parts.append("form-error")
    return " ".join(parts)
