"""
Yahoo Finance data collector module.

This module provides functionality to fetch stock market data from
Yahoo Finance using the yfinance library.
"""

import logging
import math
import numbers
import threading
import time
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import pandas as pd
import yfinance as yf

from app.data_collectors.base import (
    PriceBar,
    Provenance,
    ProviderError,
    Sourced,
    TransientProviderError,
)
from app.data_collectors.call_budget import (
    has_budget,
    pop_budget,
    push_budget,
    remaining,
)
from app.models.company import normalize_ticker

logger = logging.getLogger(__name__)

SOURCE = "yahoo_finance"

# yfinance 1.7 hardcodes 10 s on some calls and 30 s on others. Every
# request this process makes is capped at 10 s, and at whatever the
# collector deadline has left when that is shorter.
YFINANCE_HTTP_TIMEOUT_SECONDS = 10.0
# Same number as COLLECTOR_TOTAL_DEADLINE_SECONDS. A direct call, with
# no guard around it, still shares one budget across its HTTP requests.
_DIRECT_CALL_DEADLINE_SECONDS = 15.0

_http_cap_lock = threading.Lock()


class _RedactYFinance(logging.Filter):
    """Replace a yfinance log line so a URL or body cannot be written.

    The library logs the exception text. This filter runs on the
    ``yfinance`` logger, and on a handler, so a record from a child
    logger is cleaned before it reaches the root logger. Child records
    do not pass the parent's own filters. ``NullHandler`` cannot do
    this: its ``handle`` method skips filters.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = "yfinance log redacted"
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


class _RedactHandler(logging.Handler):
    """A handler whose only job is to run ``_RedactYFinance``.

    ``logging.NullHandler.handle`` does not call filters, so a filter
    attached to it never sees a record from a child logger. A normal
    handler does. ``emit`` stays empty: the redacted record then
    propagates to the root logger.
    """

    def emit(self, record: logging.LogRecord) -> None:
        return None


def _install_yfinance_log_filter() -> None:
    """Install the redaction filter once on the ``yfinance`` logger."""
    yf_logger = logging.getLogger("yfinance")
    filters = yf_logger.filters
    if not any(isinstance(item, _RedactYFinance) for item in filters):
        yf_logger.addFilter(_RedactYFinance())
    already = any(
        isinstance(handler, _RedactHandler) for handler in yf_logger.handlers
    )
    if not already:
        handler = _RedactHandler()
        handler.addFilter(_RedactYFinance())
        yf_logger.addHandler(handler)


_install_yfinance_log_filter()


def _accepted_symbol(ticker: str) -> str:
    """The ticker Yahoo may see, or a provider error when it is refused.

    ``normalize_ticker`` strips, uppercases, and rejects a ticker that
    is only dots, plus non-ASCII and control characters. The refusal is
    logged without
    the ticker, so a newline in it cannot forge a log line.
    """
    try:
        normalized = normalize_ticker(ticker)
    except ValueError:
        logger.error("Rejected ticker before Yahoo Finance was called")
        raise ProviderError("Yahoo Finance ticker was rejected") from None
    if not isinstance(normalized, str):
        raise ProviderError("Yahoo Finance ticker was rejected")
    return normalized


def _capped_timeout(requested: Any) -> float:
    """The timeout to give one HTTP request, in seconds.

    Never longer than ``YFINANCE_HTTP_TIMEOUT_SECONDS``, and never
    longer than the time left on the call's deadline. A spent deadline
    becomes a tiny timeout. Raising here would be swallowed by
    yfinance when it hides exceptions. The caller then checks the
    result: empty data after a spent deadline is a transient error,
    not a cached "no data".
    """
    try:
        numeric = float(requested)
    except (TypeError, ValueError):
        numeric = YFINANCE_HTTP_TIMEOUT_SECONDS
    budget = remaining(YFINANCE_HTTP_TIMEOUT_SECONDS)
    if numeric > 0 and numeric < budget:
        budget = numeric
    if budget <= 0:
        return 0.001
    return budget


def _http_timeout() -> float:
    """Timeout argument for ``PriceHistory`` ``history``.

    yfinance 1.7 accepts ``timeout`` on ``history``. ``Ticker`` itself
    does not, and the cookie helpers call ``session.get`` directly.
    """
    return _capped_timeout(YFINANCE_HTTP_TIMEOUT_SECONDS)


def _result_is_empty(result: Any) -> bool:
    """True for None, an empty collection, or an empty data frame."""
    if result is None:
        return True
    if isinstance(result, (str, dict, list, tuple)) and len(result) == 0:
        return True
    return getattr(result, "empty", None) is True


def _raise_if_deadline_hid_the_result(result: Any) -> Any:
    """Return ``result`` unless a spent deadline came back empty.

    A 0.001 s timeout is swallowed by yfinance and looks like "no
    data". The guard would cache that for the no-data TTL, and
    fetch-company would answer HTTP 404 for a timeout. Nothing to
    show after the deadline is a transient provider error instead:
    HTTP 502, and the guard does not cache it. A real payload is
    returned even when the deadline is already spent.
    """
    # ``remaining`` returns its default when no budget was pushed, so
    # 1.0 here means "a budget exists and it is already spent".
    if remaining(1.0) != 0 or not _result_is_empty(result):
        return result
    raise TransientProviderError("Collector deadline reached")


def _with_capped_timeout(original: Any) -> Any:
    """Return ``original`` with its ``timeout`` keyword replaced.

    yfinance 1.7 passes ``timeout=30`` into ``YfData.get`` and also
    straight into ``session.get`` from ``_get_cookie_and_crumb``. Both
    have to go through this wrapper. A missing timeout is capped too:
    the requests default of ``None`` would wait with no limit.
    """

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        supplied = kwargs.get("timeout", YFINANCE_HTTP_TIMEOUT_SECONDS)
        kwargs["timeout"] = _capped_timeout(supplied)
        return original(*args, **kwargs)

    return wrapped


def _install_http_cap(stock: Any) -> None:
    """Force yfinance HTTP calls to use our timeout.

    ``history`` takes a timeout (``PriceHistory`` passes it). ``Ticker``
    does not, and the cookie helpers call ``session.get`` with
    ``timeout=30``. ``YfData.get`` and ``post`` are wrapped, and so are
    ``session.get`` and ``session.post``. The marker sits on the session
    object. ``_open_ticker`` calls this again, so a session yfinance
    replaces is capped too. The wrapper reads the current deadline on
    every request.
    """
    data = getattr(stock, "_data", None)
    if data is None or not callable(getattr(data, "get", None)):
        return
    with _http_cap_lock:
        if not getattr(data, "_iac_http_cap", False):
            data.get = _with_capped_timeout(data.get)
            if callable(getattr(data, "post", None)):
                data.post = _with_capped_timeout(data.post)
            data._iac_http_cap = True
        session = getattr(data, "_session", None)
        if session is None or getattr(session, "_iac_http_cap", False):
            return
        if callable(getattr(session, "get", None)):
            session.get = _with_capped_timeout(session.get)
        if callable(getattr(session, "post", None)):
            session.post = _with_capped_timeout(session.post)
        session._iac_http_cap = True


def _open_ticker(symbol: str) -> Any:
    """A ``yf.Ticker`` for an already accepted symbol."""
    stock = yf.Ticker(symbol)
    _install_http_cap(stock)
    return stock


@contextmanager
def _deadline_scope():
    """One deadline for the ``with`` block, unless the guard set one.

    Several HTTP requests inside the block share the time that is left.
    A budget the guard already pushed is left alone, so retries share
    that outer deadline too.
    """
    if has_budget():
        yield
        return
    token = push_budget(
        time.monotonic() + _DIRECT_CALL_DEADLINE_SECONDS,
        time.monotonic,
    )
    try:
        yield
    finally:
        pop_budget(token)


# yfinance quoteType values for which ``totalAssets`` is assets under
# management, not a balance-sheet total.
FUND_QUOTE_TYPES = ("ETF", "MUTUALFUND")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _float_or_none(value: Any) -> Optional[float]:
    """NaN and missing become None, never 0."""
    if value is None or pd.isna(value):
        return None
    return float(value)


def _int_or_none(value: Any) -> Optional[int]:
    if value is None or pd.isna(value):
        return None
    return int(value)


def _is_real_number(value: Any) -> bool:
    """True for a real number, and false for bool.

    ``bool`` is a ``numbers.Real`` because it subclasses ``int``.
    ``True / 200`` would look like a ratio and would not be one, so
    booleans are rejected. NumPy integers and floats are real numbers
    too, and they are not always subclasses of the builtin ``int`` and
    ``float``, so the check uses ``numbers.Real``.
    """
    return isinstance(value, numbers.Real) and not isinstance(value, bool)


def _debt_to_assets(info: Dict[str, Any]) -> Optional[float]:
    """Return total debt divided by total assets from ``info`` alone.

    Yahoo's ``totalDebtPerShare`` is a currency amount per share, not
    this ratio, so this function never reads that field.
    ``fetch_key_metrics`` has already loaded ``info``. This does not
    call the provider again. With yfinance, ``info`` has no
    ``totalAssets`` for equities, so the value is usually None. For
    ETFs, ``totalAssets`` is assets under management, not a
    balance-sheet total, so ``fetch_key_metrics`` skips this function
    for funds. The ``balance_sheet`` ratio is R1 (#54).

    Missing values, non-numbers, NaN, infinity, negative debt, and a
    non-positive asset total are None. A huge integer can make
    ``math.isfinite`` or the division raise ``OverflowError``. That
    error is caught here so the rest of the metrics dict is kept.
    """
    total_debt = info.get("totalDebt")
    total_assets = info.get("totalAssets")
    if not _is_real_number(total_debt) or not _is_real_number(total_assets):
        return None
    # isfinite converts to float. 10**400 overflows that conversion,
    # and the same overflow happens again on the division. Either one
    # used to escape and make fetch_key_metrics drop every metric.
    try:
        if not (math.isfinite(total_debt) and math.isfinite(total_assets)):
            return None
        if total_assets <= 0 or total_debt < 0:
            return None
        return float(total_debt) / float(total_assets)
    except OverflowError:
        return None


def _has_no_data(info: Dict[str, Any]) -> bool:
    """True when ``info`` looks like an unknown ticker.

    yfinance 1.7 sets hide_exceptions=True, so an unknown ticker returns
    a near-empty ``info`` dict instead of raising. No name means no data
    for this ticker.
    """
    return not (info.get("longName") or info.get("shortName"))


class YahooFinanceCollector:
    """
    Collector for fetching stock market data from Yahoo Finance.

    This class wraps the yfinance library to provide a clean interface
    for fetching various types of financial data.

    It implements the ``InstrumentLookup``, ``PriceHistory`` and
    ``Fundamentals`` capabilities from ``base``. It does not implement
    ``FundAttributes`` yet (I3 #28, R1 #54). The other ``fetch_*``
    methods are Yahoo-specific helpers outside those contracts.

    Error contract: "no data" is ``None``. When yfinance fails, each
    method logs and raises ``ProviderError``. ``raise ... from exc``
    chains the original exception as ``__cause__`` (like the cause of a
    Java exception), so the traceback still shows what really failed.

    Known limitation: yfinance 1.7 hides some exceptions
    (hide_exceptions=True). A Yahoo HTTP failure can therefore look like
    "no data" (``None``, so fetch-company answers 404) or an empty
    history instead of raising ``ProviderError``. To fix in R1 (#54).
    """

    def __init__(self, clock: Optional[Callable[[], datetime]] = None):
        """Initialize the collector.

        ``clock`` returns the current time. Tests pass a fixed one; the
        default is the current UTC time.
        """
        self._clock = clock or _utc_now

    def _provenance(self, as_of: Optional[date] = None) -> Provenance:
        # Yahoo ``info`` does not say which date it describes, so as_of
        # stays None unless the caller knows it (the last price bar).
        return Provenance(
            source=SOURCE, retrieved_at=self._clock(), as_of=as_of
        )

    def fetch_company_info(
        self, ticker: str
    ) -> Optional[Sourced[Dict[str, Any]]]:
        """
        Fetch basic company information for a given ticker.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'TSLA')

        Returns:
            The company dict (keys: ``COMPANY_INFO_FIELDS``) with its
            provenance.

        Raises:
            ProviderError: when yfinance fails.

        Example:
            >>> collector = YahooFinanceCollector()
            >>> result = collector.fetch_company_info('AAPL')
            >>> print(result.value['name'])
            Apple Inc.
        """
        symbol = _accepted_symbol(ticker)
        with _deadline_scope():
            return self._load_company_info(symbol)

    def _load_company_info(self, symbol: str):
        try:
            logger.info("Fetching company info for ticker: %r", symbol)
            stock = _open_ticker(symbol)
            info = stock.info

            if _has_no_data(info):
                logger.warning("No company info found for %r", symbol)
                company_info = None
            else:
                company_info = {
                    "name": info.get("longName") or info.get("shortName"),
                    "ticker": symbol,
                    "sector": info.get("sector"),
                    "industry": info.get("industry"),
                    "description": info.get("longBusinessSummary"),
                    "website": info.get("website"),
                    "country": info.get("country"),
                    "exchange": info.get("exchange"),
                    "currency": info.get("currency", "USD"),
                    "market_cap": info.get("marketCap"),
                    "employees": info.get("fullTimeEmployees"),
                    "founded": info.get("founded"),
                    "logo_url": info.get("logo_url"),
                }
                logger.info("Successfully fetched company info for %r", symbol)

        except Exception as e:
            logger.error(
                "Error fetching company info for %r: %s",
                symbol,
                type(e).__name__,
            )
            raise ProviderError("Yahoo Finance company info failed") from e
        if company_info is None:
            _raise_if_deadline_hid_the_result(None)
            return None
        # Outside the try: a bad clock is a programming error (ValueError),
        # not a provider failure.
        return Sourced(company_info, self._provenance())

    def fetch_historical_data(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> Optional[Any]:
        """
        Fetch historical stock price data.

        Args:
            ticker: Stock ticker symbol
            period: Valid periods: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y,
                10y, ytd, max
            interval: Valid intervals: 1m, 2m, 5m, 15m, 30m, 60m, 90m,
                1h, 1d, 5d, 1wk, 1mo, 3mo

        Returns:
            DataFrame with historical data, or None when there is none

        Raises:
            ProviderError: when yfinance fails.

        Example:
            >>> collector = YahooFinanceCollector()
            >>> data = collector.fetch_historical_data('AAPL', period='1y')
        """
        symbol = _accepted_symbol(ticker)
        with _deadline_scope():
            return self._load_historical_data(symbol, period, interval)

    def _load_historical_data(self, symbol: str, period: str, interval: str):
        try:
            logger.info(
                "Fetching historical data for %r, period=%r, interval=%r",
                symbol,
                period,
                interval,
            )
            stock = _open_ticker(symbol)
            hist = stock.history(
                period=period, interval=interval, timeout=_http_timeout()
            )

            if hist.empty:
                logger.warning("No historical data found for %r", symbol)
                hist = None
            else:
                logger.info(
                    "Successfully fetched %s records for %r", len(hist), symbol
                )

        except Exception as e:
            logger.error(
                "Error fetching historical data for %r: %s",
                symbol,
                type(e).__name__,
            )
            raise ProviderError("Yahoo Finance historical data failed") from e
        if hist is None:
            _raise_if_deadline_hid_the_result(None)
            return None
        return hist

    def fetch_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> Optional[Sourced[List[PriceBar]]]:
        """
        Fetch price bars, oldest first. ``as_of`` is the last bar's day.

        Built on ``fetch_historical_data``. NaN becomes None. Returns
        None when Yahoo has no history; raises ``ProviderError`` when
        yfinance fails or the frame cannot be read.
        """
        symbol = _accepted_symbol(ticker)
        with _deadline_scope():
            hist = self.fetch_historical_data(symbol, period, interval)
            if hist is None:
                return None
            return self._bars_from_frame(symbol, hist)

    def _bars_from_frame(self, symbol: str, hist: Any):
        try:
            bars = [
                PriceBar(
                    day=pd.Timestamp(index).date(),
                    open=_float_or_none(row["Open"]),
                    high=_float_or_none(row["High"]),
                    low=_float_or_none(row["Low"]),
                    close=_float_or_none(row["Close"]),
                    volume=_int_or_none(row["Volume"]),
                )
                for index, row in hist.iterrows()
            ]
        except Exception as e:
            logger.error(
                "Error reading price history for %r: %s",
                symbol,
                type(e).__name__,
            )
            raise ProviderError("Yahoo Finance price history failed") from e
        bars.sort(key=lambda bar: bar.day)
        return Sourced(bars, self._provenance(as_of=bars[-1].day))

    def fetch_financial_statements(
        self, ticker: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch financial statements (income, balance sheet, cash flow).

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with financial statements

        Raises:
            ProviderError: when yfinance fails.

        Example:
            >>> collector = YahooFinanceCollector()
            >>> statements = collector.fetch_financial_statements('AAPL')
            >>> income_stmt = statements['income_statement']
        """
        symbol = _accepted_symbol(ticker)
        with _deadline_scope():
            return self._load_financial_statements(symbol)

    def _load_financial_statements(self, symbol: str):
        try:
            logger.info("Fetching financial statements for %r", symbol)
            stock = _open_ticker(symbol)

            # Fetch different financial statements
            financials = {
                "income_statement": stock.financials,
                "balance_sheet": stock.balance_sheet,
                "cash_flow": stock.cashflow,
                "quarterly_income": stock.quarterly_financials,
                "quarterly_balance": stock.quarterly_balance_sheet,
                "quarterly_cashflow": stock.quarterly_cashflow,
            }

            logger.info(
                "Successfully fetched financial statements for %r", symbol
            )
            return financials

        except Exception as e:
            logger.error(
                "Error fetching financial statements for %r: %s",
                symbol,
                type(e).__name__,
            )
            raise ProviderError(
                "Yahoo Finance financial statements failed"
            ) from e

    def fetch_key_metrics(
        self, ticker: str
    ) -> Optional[Sourced[Dict[str, Any]]]:
        """
        Fetch key financial metrics and ratios.

        ``debt_to_assets`` is None for ETFs and mutual funds, where
        ``totalAssets`` is assets under management. Yahoo types ETCs as
        ``EQUITY``, so they stay on the ``info`` path until the
        app-owned instrument type (#26). The ``balance_sheet`` ratio is
        R1 (#54).

        Args:
            ticker: Stock ticker symbol

        Returns:
            The metrics dict (keys: ``KEY_METRIC_FIELDS``) with its
            provenance.

        Raises:
            ProviderError: when yfinance fails.

        Example:
            >>> collector = YahooFinanceCollector()
            >>> metrics = collector.fetch_key_metrics('AAPL')
            >>> print(metrics.value['pe_ratio'])
        """
        symbol = _accepted_symbol(ticker)
        with _deadline_scope():
            return self._load_key_metrics(symbol)

    def _load_key_metrics(self, symbol: str):
        try:
            logger.info("Fetching key metrics for %r", symbol)
            stock = _open_ticker(symbol)
            info = stock.info

            if _has_no_data(info):
                logger.warning("No key metrics found for %r", symbol)
                metrics = None
            else:
                metrics = {
                    # Valuation metrics
                    "pe_ratio": info.get("trailingPE"),
                    "forward_pe": info.get("forwardPE"),
                    "pb_ratio": info.get("priceToBook"),
                    "ps_ratio": info.get("priceToSalesTrailing12Months"),
                    "ev_ebitda": info.get("enterpriseToEbitda"),
                    "ev_revenue": info.get("enterpriseToRevenue"),
                    # Profitability metrics
                    "roe": info.get("returnOnEquity"),
                    "roa": info.get("returnOnAssets"),
                    "profit_margin": info.get("profitMargins"),
                    "operating_margin": info.get("operatingMargins"),
                    "gross_margin": info.get("grossMargins"),
                    # Growth metrics
                    "revenue_growth": info.get("revenueGrowth"),
                    "earnings_growth": info.get("earningsGrowth"),
                    "earnings_quarterly_growth": info.get(
                        "earningsQuarterlyGrowth"
                    ),
                    # Liquidity metrics
                    "current_ratio": info.get("currentRatio"),
                    "quick_ratio": info.get("quickRatio"),
                    # Debt metrics. debt_to_assets is a ratio from totals
                    # already on info, never totalDebtPerShare.
                    "debt_to_equity": info.get("debtToEquity"),
                    "debt_to_assets": (
                        None
                        if info.get("quoteType") in FUND_QUOTE_TYPES
                        else _debt_to_assets(info)
                    ),
                    # Dividend metrics
                    "dividend_yield": info.get("dividendYield"),
                    "payout_ratio": info.get("payoutRatio"),
                    "dividend_rate": info.get("dividendRate"),
                    # Other metrics
                    "beta": info.get("beta"),
                    "52_week_high": info.get("fiftyTwoWeekHigh"),
                    "52_week_low": info.get("fiftyTwoWeekLow"),
                    "avg_volume": info.get("averageVolume"),
                    "market_cap": info.get("marketCap"),
                }

                logger.info("Successfully fetched key metrics for %r", symbol)

        except Exception as e:
            logger.error(
                "Error fetching key metrics for %r: %s",
                symbol,
                type(e).__name__,
            )
            raise ProviderError("Yahoo Finance key metrics failed") from e
        if metrics is None:
            _raise_if_deadline_hid_the_result(None)
            return None
        # Outside the try: a bad clock is a programming error (ValueError),
        # not a provider failure.
        return Sourced(metrics, self._provenance())

    def fetch_news(self, ticker: str, limit: int = 10) -> Optional[list]:
        """
        Fetch recent news articles about a company.

        Args:
            ticker: Stock ticker symbol
            limit: Maximum number of news articles to fetch

        Returns:
            List of news articles

        Raises:
            ProviderError: when yfinance fails.
        """
        symbol = _accepted_symbol(ticker)
        with _deadline_scope():
            return self._load_news(symbol, limit)

    def _load_news(self, symbol: str, limit: int):
        try:
            logger.info("Fetching news for %r", symbol)
            stock = _open_ticker(symbol)
            news_list = stock.news

            # Limit the number of results
            limited_news = news_list[:limit] if news_list else []

            logger.info(
                "Successfully fetched %s news articles for %r",
                len(limited_news),
                symbol,
            )

        except Exception as e:
            logger.error(
                "Error fetching news for %r: %s", symbol, type(e).__name__
            )
            raise ProviderError("Yahoo Finance news failed") from e
        return _raise_if_deadline_hid_the_result(limited_news)

    def fetch_recommendations(self, ticker: str) -> Optional[Any]:
        """
        Fetch analyst recommendations and consensus.

        Args:
            ticker: Stock ticker symbol

        Returns:
            DataFrame with recommendations, or None when there are none

        Raises:
            ProviderError: when yfinance fails.
        """
        symbol = _accepted_symbol(ticker)
        with _deadline_scope():
            return self._load_recommendations(symbol)

    def _load_recommendations(self, symbol: str):
        try:
            logger.info("Fetching recommendations for %r", symbol)
            stock = _open_ticker(symbol)
            recommendations = stock.recommendations

            if recommendations is not None and not recommendations.empty:
                logger.info(
                    "Successfully fetched recommendations for %r", symbol
                )
            else:
                logger.warning("No recommendations found for %r", symbol)
                recommendations = None

        except Exception as e:
            logger.error(
                "Error fetching recommendations for %r: %s",
                symbol,
                type(e).__name__,
            )
            raise ProviderError("Yahoo Finance recommendations failed") from e
        if recommendations is None:
            _raise_if_deadline_hid_the_result(None)
            return None
        return recommendations
