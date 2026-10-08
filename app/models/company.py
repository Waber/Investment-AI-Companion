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
_TICKER_RE = re.compile(TICKER_PATTERN)


def normalize_ticker(value: object) -> object:
    """Strip and uppercase a ticker. Reject blanks and control characters.

    Control characters are rejected before ``strip`` so a trailing
    newline is not removed and then stored as a normal symbol. ``None``
    is left alone so an update can omit the field.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("ticker must not contain control characters")
    normalized = value.strip().upper()
    if _TICKER_RE.fullmatch(normalized) is None:
        raise ValueError(
            "ticker must match " + TICKER_PATTERN + " after trim and uppercase"
        )
    return normalized


class CompanyBase(BaseModel):
    """Base company model.

    String limits match the companies table. SQLite does not enforce
    ``String(n)``, so the check lives here and a too-long value is a
    422 on the user routes instead of a 500 on PostgreSQL.
    """

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
        None, description="Brief company description"
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

    @field_validator("ticker", mode="before")
    @classmethod
    def _normalize_ticker(cls, value: object) -> object:
        return normalize_ticker(value)

    @field_validator("currency", mode="before")
    @classmethod
    def _normalize_currency(cls, value: object) -> object:
        # Before the length check, so " usd " is "USD" and then accepted.
        if isinstance(value, str):
            return value.strip().upper()
        return value


class CompanyCreate(CompanyBase):
    """Model for creating a new company."""

    pass


class CompanyUpdate(CompanyBase):
    """Model for updating company data.

    ``name`` and ``ticker`` are optional here. Repeating the limits
    matters: overriding a field drops the parent's ``Field`` constraints.
    The ticker validator on ``CompanyBase`` still runs.
    """

    name: Optional[str] = Field(None, max_length=255)
    ticker: Optional[str] = Field(None, pattern=TICKER_PATTERN)


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
