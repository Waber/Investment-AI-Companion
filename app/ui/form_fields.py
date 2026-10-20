"""Turn an HTML form into the Pydantic models the API already uses.

The browser posts strings. Empty optional company fields become
``None`` (a blank website is "no website", not the empty string).
Empty metric numbers become ``None``, which is "no data" on the
detail page. The text the user typed is kept for the other fields
and handed to ``CompanyCreate``, ``CompanyUpdate``,
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
from app.models.company import CompanyCreate, CompanyUpdate
from app.models.financial_metrics import (
    FinancialMetricsCreate,
    FinancialMetricsUpdate,
)
from app.ui.view_models import METRIC_FIELDS

COMPANY_FIELDS = (
    "name",
    "ticker",
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
# here: the form looks up the stored ticker instead, so a changed
# sentence still shows the same page. An unknown message is
# error.constraint.
_VALUE_ERROR_KEYS = {
    (
        "Financial metrics for this company, period end, "
        "and period type must be unique"
    ): "error.duplicate_metrics",
    "Failed to create financial metrics": "error.constraint",
    "Update failed due to constraint violation": "error.constraint",
}


def field_label_key(field):
    """Catalog key for one form field's label."""
    if field in METRIC_FIELDS:
        return "metric." + field
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


def company_payload(values):
    """Map posted strings onto company create/update fields."""
    payload = {}
    for field in COMPANY_FIELDS:
        raw = values.get(field, "")
        if not isinstance(raw, str):
            raw = "" if raw is None else str(raw)
        if field in _OPTIONAL_COMPANY and raw.strip() == "":
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

    Company duplicates are not in this table. The form asks the
    database whether the ticker is already stored.
    """
    return _VALUE_ERROR_KEYS.get(str(exc), "error.constraint")


def _name_is_blank(values):
    """True when the posted name has no visible characters.

    ``CompanyCreate`` accepts ``""``. The form does not: a blank name
    is the same as a missing one. The check lives here so the model
    stays unchanged.
    """
    name = values.get("name", "")
    if not isinstance(name, str):
        name = "" if name is None else str(name)
    return name.strip() == ""


def validate_company(values, *, update):
    """Return ``(model, field_errors, form_error_key)``.

    ``model`` is None when validation failed. The raw ``values`` stay
    with the caller for the inputs. A whitespace-only name is
    ``error.required`` even when the write model would accept it.
    """
    model_type = CompanyUpdate if update else CompanyCreate
    try:
        model = model_type.model_validate(company_payload(values))
    except ValidationError as exc:
        errors, form_key = errors_from_validation(exc, COMPANY_FIELDS)
        model = None
    else:
        errors, form_key = {}, None
    if _name_is_blank(values):
        rest = {key: value for key, value in errors.items() if key != "name"}
        errors = {"name": "error.required", **rest}
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
