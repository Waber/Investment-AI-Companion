"""ETF and ETC attributes as the API accepts them and returns them.

The write models have no ``source`` field and no ``is_synthetic``
field. A caller cannot choose those values. The repository records
``manual`` for an ordinary create or update. The demo seeder is the
only HTTP path that records ``demo``, and only on create.

A missing fact is null. The models do not replace it with zero.
``ter`` is a fraction: 0.0022 means 0.22 percent. ``aum`` is the
amount in ``aum_currency`` as of ``aum_as_of``. ``as_of`` is the
date of the whole snapshot.
"""

from datetime import date, datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.company import normalize_currency

# Column lengths. SQLite would store a longer string. PostgreSQL
# would answer 500, so the limit lives on the write model.
_SHORT_TEXT = 64
_PLACE = 100
_NAME = 255


def _blank_to_none(value):
    """Store an empty string as missing, not as text."""
    if value is None or not isinstance(value, str):
        return value
    stripped = value.strip()
    return stripped or None


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
    def _blank_text(cls, value):
        return _blank_to_none(value)

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


class FundAttributes(FundAttributesWrite):
    """One stored row, including the provenance the caller cannot set."""

    id: int
    company_id: int
    as_of: Optional[date] = None
    source: str
    is_synthetic: bool
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    model_config = ConfigDict(from_attributes=True, extra="ignore")
