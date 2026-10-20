import enum
import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

# The companies.ticker column is String(20). The limit matches that
# column. "_" is included because the demo fixture symbols use it
# (DEMO_DE_INDUSTRY is 16 characters). The alphabet also allows the
# dots, dashes, carets, and equals signs in GPW, EU, US, index, and
# FX symbols (PKN.WA, BRK-B, ^GSPC, EURUSD=X). Control characters and
# spaces are not in the class.
# ``.``, ``..``, and any ticker made only of dots are not symbols.
# They would be path segments if a ticker were ever joined onto a
# directory. ``PKN.WA``, ``.A``, and ``..A`` still match. Pydantic's
# regex engine has no lookahead, so "not only dots" is written as
# "there is one character that is not a dot". The ``{0,19}`` on both
# sides can add up to more than 20 characters; ``normalize_ticker``
# and ``max_length=20`` reject that.
TICKER_PATTERN = r"^[A-Z0-9._\-^=]{0,19}[A-Z0-9_\-^=][A-Z0-9._\-^=]{0,19}$"
TICKER_MAX_LENGTH = 20
# Three ASCII letters, either case, before normalization.
_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")
# Yahoo's minor-unit codes, where the letter case is the meaning:
# GBp is London pence (GBP / 100) and ZAc is South African cents. They
# are kept exactly as sent. Every other code is uppercased.
MINOR_UNIT_CURRENCIES = frozenset({"GBp", "ZAc"})
logger = logging.getLogger(__name__)
# The description column is Text, so the database would store a
# paste of any size. 5000 characters is about a page: enough for a
# provider summary, and the cap lives on the write models only so a
# longer row that is already stored can still be read.
DESCRIPTION_MAX_LENGTH = 5000
_TICKER_RE = re.compile(TICKER_PATTERN)


def normalize_name(value: object) -> object:
    """Strip a company name. Reject one with no visible character.

    ``None`` and non-strings are left for the field type. Spaces are
    removed first. A name that is then empty, or made only of format
    characters (Unicode category ``Cf``, such as U+200B, U+FEFF,
    U+200C, and U+200D), is rejected. A real letter with a format
    character beside it is kept. The read model does not use this,
    so a blank name already stored can still be listed.
    """
    if value is None or not isinstance(value, str):
        return value
    stripped = value.strip()
    if stripped and any(
        unicodedata.category(char) != "Cf" for char in stripped
    ):
        return stripped
    raise ValueError("name must contain a visible character")


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
    if (
        len(normalized) > TICKER_MAX_LENGTH
        or _TICKER_RE.fullmatch(normalized) is None
    ):
        raise ValueError(
            "ticker must match " + TICKER_PATTERN + " after trim and uppercase"
        )
    return normalized


# ISO 6166 shape: two letters, nine letters or digits, one check
# digit. Those first two letters are not checked against the
# ISO 3166 country list on purpose. Prefixes such as XS (a clearing
# code) and EU are real ISINs and must stay accepted.
_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def isin_checksum_is_valid(isin: str) -> bool:
    """Return True when ``isin`` has a valid ISO 6166 check digit.

    The value must already be twelve uppercase ASCII characters.
    This function does not strip or change case.

    The check digit is the Luhn algorithm applied after letters are
    expanded to numbers (A=10, B=11, ... Z=35). Luhn only adds single
    digits, so 10 is stored as the two digits 1 and 0, not as ten.
    Counting from the right, every second digit is doubled. The
    rightmost digit is the check digit itself, so it is not doubled.
    A doubled number above 9 is reduced by 9, which is the same as
    adding its two digits. The total must be divisible by 10.

    ``US0378331005`` is a published example that passes this rule.
    """
    if _ISIN_RE.fullmatch(isin) is None:
        return False
    digits: list[int] = []
    for char in isin:
        if char.isdigit():
            digits.append(ord(char) - ord("0"))
            continue
        # A=10 ... Z=35. Two decimal digits, most significant first.
        number = ord(char) - ord("A") + 10
        digits.append(number // 10)
        digits.append(number % 10)
    total = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def normalize_isin(value: object) -> object:
    """Uppercase an ISIN and reject anything that is not a real one.

    ``None`` stays ``None`` so a create can omit the field and an
    update can clear it. Non-ASCII and control characters are rejected
    before ``strip`` and ``upper``, for the same reason as a ticker:
    those calls would hide a no-break space or a trailing newline.
    A blank string is not a missing ISIN; the caller must send null
    to clear the field.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    if not value.isascii():
        raise ValueError("isin must be ASCII")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("isin must not contain control characters")
    normalized = value.strip().upper()
    if _ISIN_RE.fullmatch(normalized) is None:
        raise ValueError(
            "isin must be 12 characters: two letters, "
            "nine letters or digits, and a check digit"
        )
    if not isin_checksum_is_valid(normalized):
        raise ValueError("isin checksum is invalid")
    return normalized


class InstrumentType(str, enum.Enum):
    """Type stored by this application, not by a market-data provider.

    ``EQUITY`` is intentionally absent. Some providers use that word
    for a share and also for an ETC, so it cannot choose the type.
    """

    STOCK = "STOCK"
    ETF = "ETF"
    ETC = "ETC"


_INSTRUMENT_TYPES = frozenset(item.value for item in InstrumentType)


def normalize_instrument_type(value: object) -> object:
    """Accept STOCK, ETF, or ETC in any letter case.

    ``None`` and non-strings are left for the field type to reject.
    Non-ASCII and control characters are rejected before ``strip``
    and ``upper``. A provider value such as ``EQUITY`` is not a type.
    """
    if isinstance(value, InstrumentType):
        return value
    if value is None or not isinstance(value, str):
        return value
    if not value.isascii():
        raise ValueError("instrument_type must be ASCII")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("instrument_type must not contain control characters")
    normalized = value.strip().upper()
    if normalized not in _INSTRUMENT_TYPES:
        raise ValueError("instrument_type must be STOCK, ETF, or ETC")
    return normalized


def coerce_stored_instrument_type(value: object) -> object:
    """Keep one bad stored type from failing a whole company list.

    Writes still reject anything other than STOCK, ETF, or ETC. A
    value already on a row is returned as null, and the log records
    the value's class name rather than the stored text.
    """
    if value is None or isinstance(value, InstrumentType):
        return value
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized in _INSTRUMENT_TYPES:
            return normalized
    logger.warning(
        "Stored instrument_type is outside the enum (%s)",
        type(value).__name__,
    )
    return None


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

    @field_validator("name", mode="before", check_fields=False)
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        return normalize_name(value)

    @field_validator("ticker", mode="before", check_fields=False)
    @classmethod
    def _normalize_ticker(cls, value: object) -> object:
        return normalize_ticker(value)

    @field_validator("currency", mode="before", check_fields=False)
    @classmethod
    def _normalize_currency(cls, value: object) -> object:
        return normalize_currency(value)

    @field_validator("instrument_type", mode="before", check_fields=False)
    @classmethod
    def _normalize_instrument_type(cls, value: object) -> object:
        return normalize_instrument_type(value)

    @field_validator("isin", mode="before", check_fields=False)
    @classmethod
    def _normalize_isin(cls, value: object) -> object:
        return normalize_isin(value)


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
    instrument_type: InstrumentType = Field(
        InstrumentType.STOCK,
        description=(
            "STOCK, ETF, or ETC. Stored by this application, "
            "not copied from a data provider."
        ),
    )
    isin: Optional[str] = Field(
        None,
        description="ISO 6166 ISIN, or null when the identifier is unknown",
    )


class CompanyCreate(_CompanyWriteChecks):
    """Input for creating a company. Lengths match the table columns."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Company name",
    )
    ticker: str = Field(
        ...,
        max_length=TICKER_MAX_LENGTH,
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
    instrument_type: InstrumentType = Field(
        InstrumentType.STOCK,
        description=(
            "STOCK, ETF, or ETC. Stored by this application, "
            "not copied from a data provider."
        ),
    )
    isin: Optional[str] = Field(
        None,
        description=(
            "ISO 6166 ISIN. Uppercased when stored. "
            "Null when the identifier is unknown."
        ),
    )


class CompanyUpdate(_CompanyWriteChecks):
    """Input for a partial update. Every field is optional.

    Repeating the limits matters: this model does not inherit
    ``CompanyCreate``, so the constraints have to be written again.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    ticker: Optional[str] = Field(
        None, max_length=TICKER_MAX_LENGTH, pattern=TICKER_PATTERN
    )
    sector: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=DESCRIPTION_MAX_LENGTH)
    website: Optional[HttpUrl] = Field(None, max_length=500)
    country: Optional[str] = Field(None, max_length=100)
    exchange: Optional[str] = Field(None, max_length=50)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    instrument_type: Optional[InstrumentType] = Field(
        None,
        description="STOCK, ETF, or ETC. Omit to leave the stored type.",
    )
    isin: Optional[str] = Field(
        None,
        description="ISO 6166 ISIN. Send null to clear the stored value.",
    )

    @field_validator("instrument_type", mode="before")
    @classmethod
    def _reject_null_instrument_type(cls, value: object) -> object:
        """A JSON null is not a type. Omitting the field keeps the row."""
        if value is None:
            raise ValueError(
                "instrument_type cannot be null; "
                "omit it to keep the stored type"
            )
        return value


class Company(CompanyBase):
    """Full company model with additional fields."""

    instrument_type: Optional[InstrumentType] = Field(
        None,
        description=(
            "STOCK, ETF, or ETC. A stored value outside those three "
            "is null so one bad row does not break the list."
        ),
    )

    @field_validator("instrument_type", mode="before")
    @classmethod
    def _coerce_stored_instrument_type(cls, value: object) -> object:
        return coerce_stored_instrument_type(value)

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
