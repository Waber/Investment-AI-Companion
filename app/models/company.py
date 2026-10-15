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
TICKER_PATTERN = r"^[A-Z0-9._\-^=]{1,20}$"
# Yahoo quotes some markets in a minor unit. The letter case is the
# distinction, so these two spellings are stored exactly:
#   GBp  London pence (GBP is pounds, 100 times larger)
#   ZAc  South African cents (ZAR is the rand)
# ILA is Israeli agorot. It is already three capitals, so the uppercase
# rule stores it and does not turn it into ILS. Only the exact Yahoo
# spelling is special: "gbp" becomes "GBP", and "zac" becomes "ZAC"
# (not ZAR, and not the cents code).
MINOR_UNIT_CURRENCIES = frozenset({"GBp", "ZAc"})
# Checked after normalization. Ordinary codes are three capitals.
# The two minor-unit spellings are the only lowercase that remains.
_NORMALIZED_CURRENCY_RE = re.compile(r"^(?:[A-Z]{3}|GBp|ZAc)$")
# The description column is Text, so the database would store a
# paste of any size. 5000 characters is about a page: enough for a
# provider summary, and the cap lives on the write models only so a
# longer row that is already stored can still be read.
DESCRIPTION_MAX_LENGTH = 5000
_TICKER_RE = re.compile(TICKER_PATTERN)


def normalize_currency(value: object) -> object:
    """Store an ISO currency in uppercase. Keep Yahoo's minor-unit codes.

    ``usd`` and ``USD`` become one code, ``USD``. ``GBp`` and ``ZAc``
    are returned unchanged. ``None`` is left alone so an update can
    omit the field. A non-string is left for pydantic to reject.

    The three-letter check runs on the value after that normalization,
    not on the raw text. ``" usd "`` is therefore ``USD``.
    """
    if value is None or not isinstance(value, str):
        return value
    text = value.strip()
    if text in MINOR_UNIT_CURRENCIES:
        normalized = text
    else:
        normalized = text.upper()
    if _NORMALIZED_CURRENCY_RE.fullmatch(normalized) is None:
        raise ValueError("currency must be exactly three letters")
    return normalized


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
