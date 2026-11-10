"""ETF and ETC attributes as the API accepts them and returns them.

The write models have no ``source`` field and no ``is_synthetic``
field. A caller cannot choose those values. The repository records
``manual`` for an ordinary create or update. The demo seeder is the
only HTTP path that records ``demo``, and only on create.

A missing fact is null. The models do not replace it with zero.
``ter`` is a fraction of assets per year, not a percent. ``0.0022``
is 0.22 percent. The detail page multiplies that fraction by 100
and prints a percent sign, so ``1`` is 100 percent and is the
largest fee the write model accepts. A value such as ``100`` would
be ten thousand percent and is rejected. ``aum`` is the amount in
``aum_currency`` as of ``aum_as_of``, and it cannot exceed one
quadrillion (``1e15``). ``as_of`` is the date of the whole snapshot.

The five text fields use ``clean_text``. A bidi mark, a NUL, a
newline, or another control character is a 422 and is not stored.
A blank string is missing data (``None``).
"""

from datetime import date, datetime, timezone
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.company import normalize_currency
from app.validation.text import TextValidationError, clean_text

# Column lengths. SQLite would store a longer string. PostgreSQL
# would answer 500, so the limit lives on the write model.
_SHORT_TEXT = 64
_PLACE = 100
_NAME = 255
# 1 means 100 percent on the detail page (the page shows ter * 100).
TER_MAX = 1.0
# One quadrillion in the AUM currency. Larger than any real fund,
# and still a float ``format_number`` can print.
AUM_MAX = 1e15
_TEXT_LIMITS = {
    "issuer": _NAME,
    "underlying": _NAME,
    "domicile": _PLACE,
    "replication_method": _SHORT_TEXT,
    "distribution_policy": _SHORT_TEXT,
}


def _clean_optional(value, field_name):
    """Strip and check one optional fact. A blank becomes ``None``.

    ``too_long`` is handed back stripped so the field ``max_length``
    can report Pydantic ``string_too_long``. Every other
    ``clean_text`` failure is a 422. The read model does not call
    this: a row already stored is shown, not re-checked into a 500.
    """
    if value is None or not isinstance(value, str):
        return value
    try:
        return clean_text(
            value,
            field=field_name,
            max_len=_TEXT_LIMITS[field_name],
            allow_newlines=False,
            allow_blank=True,
        )
    except TextValidationError as exc:
        if exc.code == "too_long":
            return value.strip()
        raise


def _reject_bool(value):
    """``True`` is an ``int`` in Python. It is not a fee or an amount."""
    if isinstance(value, bool):
        raise ValueError("boolean is not a number")
    return value


class FundAttributesWrite(BaseModel):
    """Fields a caller may send. Provenance is not one of them.

    Extra keys, including ``source`` and ``is_synthetic``, are
    ignored. They are not a validation error, and they are not
    stored.
    """

    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)

    issuer: Optional[str] = Field(None, max_length=_NAME)
    underlying: Optional[str] = Field(None, max_length=_NAME)
    ter: Optional[float] = Field(None, ge=0)
    domicile: Optional[str] = Field(None, max_length=_PLACE)
    replication_method: Optional[str] = Field(None, max_length=_SHORT_TEXT)
    distribution_policy: Optional[str] = Field(None, max_length=_SHORT_TEXT)
    aum: Optional[float] = Field(None, ge=0)
    aum_currency: Optional[str] = None
    aum_as_of: Optional[date] = None
    as_of: Optional[date] = None

    @field_validator(
        "issuer",
        "underlying",
        "domicile",
        "replication_method",
        "distribution_policy",
        mode="before",
    )
    @classmethod
    def _blank_text(cls, value, info):
        return _clean_optional(value, info.field_name)

    @model_validator(mode="after")
    def _cap_amounts(self):
        """Reject a fee or an amount the page cannot mean.

        ``ter`` above 1 is more than 100 percent. ``aum`` above
        ``AUM_MAX`` is not a real fund size. Both stay floats.
        """
        if self.ter is not None and self.ter > TER_MAX:
            raise ValueError("ter is a fraction from 0 to 1; 1 is 100 percent")
        if self.aum is not None and self.aum > AUM_MAX:
            raise ValueError("aum must not be greater than 1e15")
        return self

    @field_validator("ter", "aum", mode="before")
    @classmethod
    def _number(cls, value):
        return _reject_bool(value)

    @field_validator("aum_currency", mode="before")
    @classmethod
    def _currency(cls, value):
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return normalize_currency(value)


class FundAttributesCreate(FundAttributesWrite):
    """A new snapshot. ``as_of`` is required."""

    as_of: date


class FundAttributesUpdate(FundAttributesWrite):
    """Fields to change. Omitted fields stay as stored."""


class FundAttributes(BaseModel):
    """One stored row, including the provenance the caller cannot set.

    This model does not repeat the write caps or ``clean_text``.
    A row planted outside the API can still be read. The page
    treats an undisplayable number as missing instead of failing.
    """

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: int
    company_id: int
    issuer: Optional[str] = None
    underlying: Optional[str] = None
    ter: Optional[float] = None
    domicile: Optional[str] = None
    replication_method: Optional[str] = None
    distribution_policy: Optional[str] = None
    aum: Optional[float] = None
    aum_currency: Optional[str] = None
    aum_as_of: Optional[date] = None
    as_of: Optional[date] = None
    source: str
    is_synthetic: bool
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
