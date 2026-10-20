import re
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

# The companies.ticker column is String(20). The limit matches that
# column. "_" is included because the demo fixture symbols use it
# (DEMO_DE_INDUSTRY is 16 characters). The alphabet also allows the
# dots, dashes, carets, and equals signs in GPW, EU, US, index, and
# FX symbols (PKN.WA, BRK-B, ^GSPC, EURUSD=X). Control characters and
# spaces are not in the class.
# ``.`` and ``..`` are not symbols. They would be path segments if a
# ticker were ever joined onto a directory. ``PKN.WA`` still matches.
# Pydantic's regex engine has no lookahead, so the shape is two
# alternatives: a symbol that does not start with ``.``, or one that
# starts with ``.`` and is longer than ``.`` and ``..``.
TICKER_PATTERN = (
    r"^(?:[A-Z0-9_\-^=][A-Z0-9._\-^=]{0,19}"
    r"|\.(?:[A-Z0-9_\-^=]|[A-Z0-9._\-^=]{2})[A-Z0-9._\-^=]{0,17})$"
)
# Three ASCII letters, either case, before normalization.
_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")
# Yahoo's minor-unit codes, where the letter case is the meaning:
# GBp is London pence (GBP / 100) and ZAc is South African cents. They
# are kept exactly as sent. Every other code is uppercased.
MINOR_UNIT_CURRENCIES = frozenset({"GBp", "ZAc"})
# The description column is Text, so the database would store a
# paste of any size. 5000 characters is about a page: enough for a
# provider summary, and the cap lives on the write models only so a
# longer row that is already stored can still be read.
DESCRIPTION_MAX_LENGTH = 5000
_TICKER_RE = re.compile(TICKER_PATTERN)


def normalize_ticker(value: object) -> object:
    """Strip and uppercase a ticker. Reject blanks and control characters.

    Non-ASCII and control characters are rejected before ``strip`` and
    ``upper``. Those calls would hide a trailing newline, a line
    separator, a no-break space, or a dotless i. ``None`` is left
    alone so an update can omit the field.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    # Before strip/upper. Those calls turn a line separator, a
    # no-break space, and a dotless i into a normal ASCII symbol.
    if not value.isascii():
        raise ValueError("ticker must be ASCII")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("ticker must not contain control characters")
    normalized = value.strip().upper()
    if _TICKER_RE.fullmatch(normalized) is None:
        raise ValueError(
            "ticker must match " + TICKER_PATTERN + " after trim and uppercase"
        )
    return normalized


def normalize_currency(value: object) -> object:
    """Uppercase a three-letter currency code, except Yahoo minor units.

    ``usd`` and ``Usd`` become ``USD``, so one currency is stored as one
    code. ``GBp`` and ``ZAc`` stay as sent; ``gbp`` becomes ``GBP``,
    because only the exact spelling ``GBp`` means pence. ``None`` and
    non-strings are left for the field type to handle.

    ``isascii`` runs before any later case change. A long s, a ligature,
    or a no-break space must not fold into a real ISO code.
    """
    if value is None or not isinstance(value, str):
        return value
    # Before ``upper``. ``"ſ".upper()`` is ``"S"`` and a ligature can
    # grow into ASCII letters. The shape check alone uses ``[A-Za-z]``,
    # which does not match those characters; the ASCII check stays even
    # if a later edit strips the value first.
    if not value.isascii() or _CURRENCY_RE.fullmatch(value) is None:
        raise ValueError("currency must be exactly three letters")
    if value in MINOR_UNIT_CURRENCIES:
        return value
    return value.upper()


class _CompanyWriteChecks(BaseModel):
    """Ticker and currency checks for create and update only.

    ``Company``, the model that serialises stored rows, does not
    inherit this. One old blank ticker would otherwise make
    ``GET /companies/`` return 500 for every caller.
    ``check_fields=False`` is required because this mixin declares
    no fields of its own; the subclasses do.
    """

    @field_validator("ticker", mode="before", check_fields=False)
    @classmethod
    def _normalize_ticker(cls, value: object) -> object:
        return normalize_ticker(value)

    @field_validator("currency", mode="before", check_fields=False)
    @classmethod
    def _normalize_currency(cls, value: object) -> object:
        return normalize_currency(value)


class CompanyBase(BaseModel):
    """Fields of a stored company, without write-time limits.

    SQLite does not enforce ``String(n)``. The limits live on
    ``CompanyCreate`` and ``CompanyUpdate``, so a too-long value is a
    422 on those routes instead of a 500 on PostgreSQL, and a legacy
    row can still be read.
    """

    name: str = Field(..., description="Company name")
    ticker: str = Field(..., description="Stock ticker symbol")
    sector: Optional[str] = Field(None, description="Economic sector")
    industry: Optional[str] = Field(None, description="Industry")
    description: Optional[str] = Field(
        None, description="Brief company description"
    )
    # Plain text on the read model. One stored value that is not a
    # URL would otherwise fail HttpUrl validation and make
    # GET /companies/ return 500. Create and update still require
    # a real URL.
    website: Optional[str] = Field(None, description="Company website")
    country: Optional[str] = Field(None, description="Country of origin")
    exchange: Optional[str] = Field(
        None, description="Stock exchange where the company is listed"
    )
    currency: Optional[str] = Field(
        "USD", description="Currency for financial data"
    )


class CompanyCreate(_CompanyWriteChecks):
    """Input for creating a company. Lengths match the table columns."""

    name: str = Field(..., max_length=255, description="Company name")
    ticker: str = Field(
        ...,
        pattern=TICKER_PATTERN,
        description="Stock ticker symbol",
    )
    sector: Optional[str] = Field(
        None, max_length=100, description="Economic sector"
    )
    industry: Optional[str] = Field(
        None, max_length=100, description="Industry"
    )
    description: Optional[str] = Field(
        None,
        max_length=DESCRIPTION_MAX_LENGTH,
        description="Brief company description",
    )
    website: Optional[HttpUrl] = Field(
        None, max_length=500, description="Company website"
    )
    country: Optional[str] = Field(
        None, max_length=100, description="Country of origin"
    )
    exchange: Optional[str] = Field(
        None,
        max_length=50,
        description="Stock exchange where the company is listed",
    )
    currency: Optional[str] = Field(
        "USD",
        min_length=3,
        max_length=3,
        description="Currency for financial data",
    )


class CompanyUpdate(_CompanyWriteChecks):
    """Input for a partial update. Every field is optional.

    Repeating the limits matters: this model does not inherit
    ``CompanyCreate``, so the constraints have to be written again.
    """

    name: Optional[str] = Field(None, max_length=255)
    ticker: Optional[str] = Field(None, pattern=TICKER_PATTERN)
    sector: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=DESCRIPTION_MAX_LENGTH)
    website: Optional[HttpUrl] = Field(None, max_length=500)
    country: Optional[str] = Field(None, max_length=100)
    exchange: Optional[str] = Field(None, max_length=50)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)


class Company(CompanyBase):
    """Full company model with additional fields."""

    id: int = Field(..., description="Unique company identifier")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    is_active: bool = Field(
        default=True, description="Whether the company is active in the system"
    )
    last_data_update: Optional[datetime] = Field(
        None, description="Date of last data update"
    )

    # from_attributes lets model_validate read SQLAlchemy rows.
    model_config = ConfigDict(from_attributes=True)
