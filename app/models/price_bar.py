"""Stored price bar, as the API accepts it and returns it.

The collector has its own ``PriceBar`` dataclass (one day from a
provider, with no currency and no source). This module is the row
that is saved: the same day plus the instrument, the currency, and
the provenance (source and retrieval time). The two types are easy
to mix up because they share the name. Import this one when the
value is going into the database or out through the API.
"""

from datetime import date as DateType
from datetime import datetime
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.core.utc_datetime import as_utc
from app.models.company import normalize_currency

# Provenance source, for example "fake" or the demo marker. The
# column is String(64). A longer value would be a 500 on PostgreSQL
# and a silent store on SQLite, so the limit lives on the write model.
SOURCE_MAX_LENGTH = 64


class PriceBarBase(BaseModel):
    """Fields of one bar, without the generated id.

    ``allow_inf_nan`` is false so ``NaN`` and infinity are rejected
    here. They are not prices, and they must not be stored as a
    number or rewritten to zero.
    """

    model_config = ConfigDict(allow_inf_nan=False)

    date: DateType = Field(..., description="Session date of this bar")
    open: Optional[float] = Field(None, description="Opening price")
    high: Optional[float] = Field(None, description="Highest price")
    low: Optional[float] = Field(None, description="Lowest price")
    close: Optional[float] = Field(None, description="Closing price")
    volume: Optional[int] = Field(
        None, description="Volume for the session, or null when unknown"
    )
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Currency of the prices on this bar",
    )
    source: str = Field(
        ...,
        max_length=SOURCE_MAX_LENGTH,
        description="Where this bar came from",
    )
    retrieved_at: datetime = Field(
        ..., description="When this bar was retrieved, in UTC"
    )

    @field_validator("open", "high", "low", "close", "volume", mode="before")
    @classmethod
    def _reject_bool(cls, value: object) -> object:
        """A JSON boolean is not a price or a volume.

        ``True`` is a subclass of ``int`` in Python. Without this
        check, volume ``true`` would be stored as 1.
        """
        if isinstance(value, bool):
            raise ValueError("boolean is not a number")
        return value

    @field_validator("volume")
    @classmethod
    def _volume_not_negative(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value < 0:
            raise ValueError("volume must be zero or greater")
        return value

    @field_validator("currency", mode="before")
    @classmethod
    def _normalize_currency(cls, value: object) -> object:
        return normalize_currency(value)

    @field_validator("source", mode="before")
    @classmethod
    def _normalize_source(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("source must not be blank")
        return stripped

    @field_validator("retrieved_at")
    @classmethod
    def _retrieved_at_utc(cls, value: datetime) -> datetime:
        """Store the retrieval instant in UTC.

        A value with no offset is treated as UTC, the same rule as
        ``period_end`` on financial metrics. The instant does not
        move. Only the clock is written in UTC.
        """
        return as_utc(value)

    @model_validator(mode="after")
    def _high_not_below_low(self) -> "PriceBarBase":
        if (
            self.high is not None
            and self.low is not None
            and self.high < self.low
        ):
            raise ValueError("high must be greater than or equal to low")
        return self


class PriceBarCreate(PriceBarBase):
    """One bar to insert. The instrument id is the URL, not the body."""


class PriceBar(PriceBarBase):
    """One stored bar, including the id the database assigned."""

    id: int = Field(..., description="Unique identifier")
    instrument_id: int = Field(
        ...,
        description=(
            "Instrument this bar belongs to. Today that is companies.id."
        ),
    )

    model_config = ConfigDict(from_attributes=False, allow_inf_nan=False)
