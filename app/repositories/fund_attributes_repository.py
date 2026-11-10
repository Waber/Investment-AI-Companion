"""Read and write the one fund-attribute row of an instrument.

Only an ETF or an ETC may have that row. A stock is rejected. The
public write payload cannot carry ``source`` or ``is_synthetic``.
Those are arguments of ``create``, and an update always records
``manual`` without changing the synthetic flag.
"""

import math
from datetime import date, datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.models.company import normalize_currency
from app.models.database_models import (
    RECORD_SOURCE_MANUAL,
    CompanyDB,
    FundAttributesDB,
    require_record_source,
)
from app.models.fund_attributes import AUM_MAX, TER_MAX
from app.repositories.company_errors import CompanyNotFoundError

_FUND_TYPES = frozenset({"ETF", "ETC"})
_TEXT_FIELDS = (
    "issuer",
    "underlying",
    "domicile",
    "replication_method",
    "distribution_policy",
)
_DATE_FIELDS = ("aum_as_of", "as_of")
_AUM_NEEDS = "aum requires a currency and an as-of date"
_AUM_EXTRA = "aum currency and aum_as_of require aum"


class FundAttributesRepository:
    """The one attributes row for a company, or none."""

    def __init__(self, db):
        self.db = db

    def get_by_company(self, company_id):
        """The row for this company, or None."""
        return (
            self.db.query(FundAttributesDB)
            .filter(FundAttributesDB.company_id == company_id)
            .first()
        )

    def create(
        self,
        company_id,
        attributes,
        *,
        record_source=RECORD_SOURCE_MANUAL,
        is_synthetic=False,
    ):
        """Insert the row. A second row for the same company is an error.

        ``attributes`` is a dict or a write model. Date values may be
        ``date`` objects or ISO strings. ``eur`` is stored as ``EUR``.
        """
        company = self._company(company_id)
        self._require_fund(company)
        if self.get_by_company(company_id) is not None:
            raise ValueError(
                "Fund attributes for this instrument already exist"
            )
        if not isinstance(is_synthetic, bool):
            raise ValueError("is_synthetic must be true or false")
        source = require_record_source(record_source)
        data = _fields(attributes)
        if data.get("as_of") is None:
            raise ValueError("as_of is required")
        _check_numbers(data)
        _check_aum(data)
        row = FundAttributesDB(
            company_id=company_id,
            source=source,
            is_synthetic=is_synthetic,
            **data,
        )
        self.db.add(row)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ValueError("Failed to create fund attributes")
        self.db.refresh(row)
        return row

    def update(self, company_id, attributes):
        """Change the fields that were sent.

        Returns None when this company has no attribute row. The
        company must still be an ETF or an ETC. ``source`` becomes
        ``manual``. ``is_synthetic`` is left as stored. A ``source``
        key in ``attributes`` is ignored.
        """
        company = self._company(company_id)
        self._require_fund(company)
        row = self.get_by_company(company_id)
        if row is None:
            return None
        data = _fields(attributes)
        data.pop("source", None)
        data.pop("is_synthetic", None)
        _check_numbers(data)
        _check_aum(data, partial=True)
        for field, value in data.items():
            setattr(row, field, value)
        row.source = RECORD_SOURCE_MANUAL
        row.updated_at = datetime.now(timezone.utc)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ValueError("Update failed due to constraint violation")
        self.db.refresh(row)
        return row

    def _company(self, company_id):
        company = self.db.get(CompanyDB, company_id)
        if company is None:
            raise CompanyNotFoundError(company_id)
        return company

    @staticmethod
    def _require_fund(company):
        if company.instrument_type not in _FUND_TYPES:
            raise ValueError(
                "fund attributes are only stored for an ETF or an ETC"
            )


def _mapping(attributes):
    if hasattr(attributes, "model_dump"):
        return attributes.model_dump(exclude_unset=True)
    return dict(attributes)


def _fields(attributes):
    """The fact columns, with blanks and provenance removed."""
    raw = _mapping(attributes)
    data = {}
    for field in _TEXT_FIELDS:
        if field not in raw:
            continue
        value = raw[field]
        if isinstance(value, str):
            value = value.strip() or None
        data[field] = value
    for field in ("ter", "aum"):
        if field in raw:
            data[field] = raw[field]
    if "aum_currency" in raw:
        data["aum_currency"] = _currency(raw["aum_currency"])
    for field in _DATE_FIELDS:
        if field in raw:
            data[field] = _date(raw[field])
    return data


def _currency(value):
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return normalize_currency(value)


def _date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        raise ValueError("as_of must be a date")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise ValueError("as_of must be a date") from error
    raise ValueError("as_of must be a date")


def _check_numbers(data):
    for field in ("ter", "aum"):
        if field not in data:
            continue
        value = data[field]
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field} must be a number")
        if not math.isfinite(float(value)) or float(value) < 0:
            raise ValueError(f"{field} must not be negative")
        if field == "ter" and float(value) > TER_MAX:
            raise ValueError("ter is a fraction from 0 to 1; 1 is 100 percent")
        if field == "aum" and float(value) > AUM_MAX:
            raise ValueError("aum must not be greater than 1e15")
        data[field] = float(value)


def _check_aum(data, partial=False):
    """AUM, its currency, and its as-of date travel together.

    On a partial update, a request that does not mention any of the
    three leaves the stored trio alone. Sending an amount requires
    the currency and the date in the same request. Sending a currency
    or a date without an amount is rejected. Clearing the amount
    clears the other two.
    """
    mentioned = [
        name for name in ("aum", "aum_currency", "aum_as_of") if name in data
    ]
    if partial and not mentioned:
        return
    amount = data.get("aum")
    if amount is None:
        if data.get("aum_currency") is not None or data.get("aum_as_of"):
            raise ValueError(_AUM_EXTRA)
        if not partial:
            data["aum_currency"] = None
            data["aum_as_of"] = None
        return
    if data.get("aum_currency") is None or data.get("aum_as_of") is None:
        raise ValueError(_AUM_NEEDS)
