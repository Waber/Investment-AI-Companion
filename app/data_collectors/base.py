"""
Provider-neutral contracts for market-data collectors.

A provider (Yahoo, a fake for tests, a future paid API) may implement
only some capabilities. Each capability is its own small protocol, so a
caller asks for the one it needs and a provider is not forced to stub
methods it cannot serve.

Error contract for every capability method:

- return ``None`` when the provider has no data for the ticker;
- raise ``ProviderError`` when the provider fails (network, rate limit,
  parse error). An exception is never turned into ``None``.

Every successful result is wrapped in ``Sourced`` so the caller can show
the source, the data date, and whether the data is synthetic.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Optional,
    Protocol,
    TypeVar,
    runtime_checkable,
)

from app.core.utc_datetime import as_utc

T = TypeVar("T")

# Keys a provider puts in the dict of each capability. Defined once so
# the Yahoo adapter and the offline fake cannot drift apart.
COMPANY_INFO_FIELDS = (
    "name",
    "ticker",
    "sector",
    "industry",
    "description",
    "website",
    "country",
    "exchange",
    "currency",
    "market_cap",
    "employees",
    "founded",
    "logo_url",
)

KEY_METRIC_FIELDS = (
    "pe_ratio",
    "forward_pe",
    "pb_ratio",
    "ps_ratio",
    "ev_ebitda",
    "ev_revenue",
    "roe",
    "roa",
    "profit_margin",
    "operating_margin",
    "gross_margin",
    "revenue_growth",
    "earnings_growth",
    "earnings_quarterly_growth",
    "current_ratio",
    "quick_ratio",
    "debt_to_equity",
    "debt_to_assets",
    "dividend_yield",
    "payout_ratio",
    "dividend_rate",
    "beta",
    "52_week_high",
    "52_week_low",
    "avg_volume",
    "market_cap",
)

FUND_ATTRIBUTE_FIELDS = (
    "fund_type",
    "ter",
    "aum",
    "aum_currency",
    "issuer",
    "underlying",
    "domicile",
    "distribution_policy",
)


class ProviderError(Exception):
    """The provider failed: network, rate limit, or a parse error.

    "No data for this ticker" is not an error; a capability returns
    ``None`` for that. This is deliberately not a ``ValueError``: the
    fetch-company handler maps ``ValueError`` to HTTP 400 (the caller's
    fault), while a provider failure is a 502 (the upstream's fault).
    """


@dataclass(frozen=True)
class Provenance:
    """Where a result came from and what date it describes.

    ``frozen=True`` makes the instance immutable, like a Java ``record``
    (setting a field raises ``FrozenInstanceError``). ``as_of`` is the
    date the data describes, or ``None`` when the provider does not say.
    ``retrieved_at`` must be timezone-aware and is stored in UTC.
    """

    source: str
    retrieved_at: datetime
    as_of: Optional[date] = None
    synthetic: bool = False

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("Provenance source must not be blank")
        if self.retrieved_at.utcoffset() is None:
            raise ValueError("Provenance retrieved_at must be timezone-aware")
        # A frozen dataclass blocks normal assignment, so the normalized
        # value is written with object.__setattr__ (the usual idiom).
        object.__setattr__(self, "retrieved_at", as_utc(self.retrieved_at))


@dataclass(frozen=True)
class Sourced(Generic[T]):
    """A value together with its provenance.

    ``Generic[T]`` works like Java generics: ``Sourced[List[PriceBar]]``
    says what ``value`` holds. Python does not check it at runtime; only
    a type checker such as mypy does.
    """

    value: T
    provenance: Provenance


@dataclass(frozen=True)
class PriceBar:
    """One trading day. A value the provider lacks is ``None``, not 0."""

    day: date
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    volume: Optional[int]


# typing.Protocol is structural typing: a class satisfies it by having
# the methods, without naming it in an ``implements`` clause as Java
# requires. @runtime_checkable lets ``isinstance`` work, but it only
# checks that the method names exist, not their signatures.


@runtime_checkable
class InstrumentLookup(Protocol):
    """Basic company data. Keys: ``COMPANY_INFO_FIELDS``."""

    def fetch_company_info(
        self, ticker: str
    ) -> Optional[Sourced[Dict[str, Any]]]: ...


@runtime_checkable
class PriceHistory(Protocol):
    """Daily or periodic price bars, oldest first."""

    def fetch_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> Optional[Sourced[List[PriceBar]]]: ...


@runtime_checkable
class Fundamentals(Protocol):
    """Valuation and financial ratios. Keys: ``KEY_METRIC_FIELDS``."""

    def fetch_key_metrics(
        self, ticker: str
    ) -> Optional[Sourced[Dict[str, Any]]]: ...


@runtime_checkable
class FundAttributes(Protocol):
    """ETF and fund facts. Keys: ``FUND_ATTRIBUTE_FIELDS``."""

    def fetch_fund_attributes(
        self, ticker: str
    ) -> Optional[Sourced[Dict[str, Any]]]: ...
