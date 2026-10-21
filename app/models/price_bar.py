"""Stored price bar, as the API accepts it and returns it.

The collector has its own ``PriceBar`` dataclass (one day from a
provider, with no currency and no source). This module is the row
that is saved: the same day plus the instrument, the currency, and
the provenance (source and retrieval time). The two types are easy
to mix up because they share the name. Import this one when the
value is going into the database or out through the API.

OHLC prices are ``Decimal``, stored in ``Numeric(20, 8)``. FastAPI
asks Pydantic for JSON mode, and Pydantic encodes a ``Decimal`` as a
string. A very small value would otherwise become ``1E-8``.
``price_to_json`` writes fixed-point with 8 digits after the decimal
point, so the wire value matches the column. A JSON number on input
is still accepted and then rounded half-even to that scale.
"""

from datetime import date as DateType
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Annotated, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StrictInt,
    field_validator,
    model_validator,
)

from app.core.utc_datetime import as_utc
from app.models.company import normalize_currency

# Provenance source, for example "fake" or the demo marker. The
# column is String(64). A longer value would be a 500 on PostgreSQL
# and a silent store on SQLite, so the limit lives on the write model.
SOURCE_MAX_LENGTH = 64
# Signed 64-bit maximum. PostgreSQL BIGINT stores this value.
# A larger volume is rejected here so it never becomes a database error.
VOLUME_MAX = 2**63 - 1
# Numeric(20, 8): 12 digits before the decimal point, 8 after.
# 10**12 does not fit. Half-even matches the rounding SQLAlchemy
# applies when it reads the column back.
PRICE_PRECISION = 20
PRICE_SCALE = 8
_PRICE_QUANTUM = Decimal("0.00000001")
_PRICE_LIMIT = Decimal(10) ** (PRICE_PRECISION - PRICE_SCALE)
# Shown on each OHLC field. Input may be a JSON number or a numeric
# string. FastAPI's response is the fixed-point string from
# price_to_json, because Pydantic's JSON mode encodes Decimal as text.
_PRICE_JSON = (
    "A stored price is a JSON string with 8 decimal places, "
    "matching Numeric(20, 8). A JSON number or a numeric string "
    "is accepted on input. Null when unknown."
)


def price_to_json(value: Decimal) -> str:
    """Fixed-point string for one price.

    ``format(Decimal('0.00000001'), 'f')`` is ``0.00000001``.
    Pydantic's default JSON encoding of that value is ``1E-8``.
    The column scale is 8, so the string always has 8 digits after
    the decimal point.
    """
    quantized = value.quantize(_PRICE_QUANTUM, rounding=ROUND_HALF_EVEN)
    return format(quantized, "f")


# return_type=str tells the JSON schema this field is a string.
Price = Annotated[
    Decimal,
    PlainSerializer(price_to_json, return_type=str, when_used="json"),
]


class PriceBarBase(BaseModel):
    """Fields of one bar, without the generated id.

    ``allow_inf_nan`` is false so ``NaN`` and infinity are rejected
    here. They are not prices, and they must not be stored as a
    number or rewritten to zero.
    """

    model_config = ConfigDict(allow_inf_nan=False)

    date: DateType = Field(..., description="Session date of this bar")
    open: Optional[Price] = Field(
        None, description="Opening price. " + _PRICE_JSON
    )
    high: Optional[Price] = Field(
        None, description="Highest price. " + _PRICE_JSON
    )
    low: Optional[Price] = Field(
        None, description="Lowest price. " + _PRICE_JSON
    )
    close: Optional[Price] = Field(
        None, description="Closing price. " + _PRICE_JSON
    )
    # StrictInt, not int. Pydantic would otherwise turn the string
    # "100" into the number 100. A volume is a count, so that
    # coercion is rejected. JSON null stays null.
    volume: Optional[StrictInt] = Field(
        None,
        le=VOLUME_MAX,
        description=(
            "Volume for the session, or null when unknown. "
            'A string such as "100" is rejected, not turned into 100.'
        ),
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

    @field_validator("open", "high", "low", "close")
    @classmethod
    def _quantize_price(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        """Fit one price into Numeric(20, 8).

        Extra digits are rounded half-even, the same rule the column
        uses when the value is read back. A result with 13 digits
        before the decimal point does not fit the precision, so it is
        rejected here. PostgreSQL would otherwise raise, and SQLite
        would store it.
        """
        if value is None:
            return None
        # Non-finite values are already rejected by allow_inf_nan.
        quantized = value.quantize(_PRICE_QUANTUM, rounding=ROUND_HALF_EVEN)
        if abs(quantized) >= _PRICE_LIMIT:
            raise ValueError("price exceeds Numeric(20, 8)")
        return quantized

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
    def _candle_bounds(self) -> "PriceBarBase":
        """Reject a bar that cannot be a candle.

        A missing price is skipped. The comparisons use only the
        values that are present: high is at least the open and the
        close, low is at most the open and the close, and high is at
        least the low. Equal prices are a valid session (a flat bar).
        Volume is checked on its own field, above.
        """
        if self.high is not None and self.open is not None:
            if self.high < self.open:
                raise ValueError("high must be greater than or equal to open")
        if self.high is not None and self.close is not None:
            if self.high < self.close:
                raise ValueError("high must be greater than or equal to close")
        if self.low is not None and self.open is not None:
            if self.low > self.open:
                raise ValueError("low must be less than or equal to open")
        if self.low is not None and self.close is not None:
            if self.low > self.close:
                raise ValueError("low must be less than or equal to close")
        if self.high is not None and self.low is not None:
            if self.high < self.low:
                raise ValueError("high must be greater than or equal to low")
        return self


class PriceBarCreate(PriceBarBase):
    """One bar to insert. The instrument id is the URL, not the body.

    The candle rules (high, low, open, close, and volume) are on
    ``PriceBarBase``, so this write model rejects a broken bar before
    it reaches the database.
    """


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
