"""
Yahoo Finance data collector module.

This module provides functionality to fetch stock market data from
Yahoo Finance using the yfinance library.
"""

import logging
import math
import numbers
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import pandas as pd
import yfinance as yf

from app.data_collectors.base import (
    PriceBar,
    Provenance,
    ProviderError,
    Sourced,
)

logger = logging.getLogger(__name__)

SOURCE = "yahoo_finance"

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
        try:
            logger.info("Fetching company info for ticker: %r", ticker)
            stock = yf.Ticker(ticker)
            info = stock.info

            # yfinance 1.7 sets hide_exceptions=True, so an unknown
            # ticker returns a near-empty ``info`` dict instead of
            # raising. No name means no data for this ticker.
            if not (info.get("longName") or info.get("shortName")):
                logger.warning("No company info found for %r", ticker)
                return None

            # Extract relevant information
            company_info = {
                "name": info.get("longName") or info.get("shortName"),
                "ticker": ticker.upper(),
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

            logger.info("Successfully fetched company info for %r", ticker)

        except Exception as e:
            logger.error("Error fetching company info for %r: %r", ticker, e)
            raise ProviderError("Yahoo Finance company info failed") from e
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
        try:
            logger.info(
                "Fetching historical data for %r, period=%r, interval=%r",
                ticker,
                period,
                interval,
            )
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period, interval=interval)

            if hist.empty:
                logger.warning("No historical data found for %r", ticker)
                return None

            logger.info(
                "Successfully fetched %s records for %r", len(hist), ticker
            )
            return hist

        except Exception as e:
            logger.error(
                "Error fetching historical data for %r: %r", ticker, e
            )
            raise ProviderError("Yahoo Finance historical data failed") from e

    def fetch_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> Optional[Sourced[List[PriceBar]]]:
        """
        Fetch price bars, oldest first. ``as_of`` is the last bar's day.

        Built on ``fetch_historical_data``. NaN becomes None. Returns
        None when Yahoo has no history; raises ``ProviderError`` when
        yfinance fails or the frame cannot be read.
        """
        hist = self.fetch_historical_data(ticker, period, interval)
        if hist is None:
            return None
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
            logger.error("Error reading price history for %r: %r", ticker, e)
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
        try:
            logger.info("Fetching financial statements for %r", ticker)
            stock = yf.Ticker(ticker)

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
                "Successfully fetched financial statements for %r", ticker
            )
            return financials

        except Exception as e:
            logger.error(
                "Error fetching financial statements for %r: %r",
                ticker,
                e,
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
        try:
            logger.info("Fetching key metrics for %r", ticker)
            stock = yf.Ticker(ticker)
            info = stock.info

            # Extract key metrics
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

            logger.info("Successfully fetched key metrics for %r", ticker)

        except Exception as e:
            logger.error("Error fetching key metrics for %r: %r", ticker, e)
            raise ProviderError("Yahoo Finance key metrics failed") from e
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
        try:
            logger.info("Fetching news for %r", ticker)
            stock = yf.Ticker(ticker)
            news_list = stock.news

            # Limit the number of results
            limited_news = news_list[:limit] if news_list else []

            logger.info(
                "Successfully fetched %s news articles for %r",
                len(limited_news),
                ticker,
            )
            return limited_news

        except Exception as e:
            logger.error("Error fetching news for %r: %r", ticker, e)
            raise ProviderError("Yahoo Finance news failed") from e

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
        try:
            logger.info("Fetching recommendations for %r", ticker)
            stock = yf.Ticker(ticker)
            recommendations = stock.recommendations

            if recommendations is not None and not recommendations.empty:
                logger.info(
                    "Successfully fetched recommendations for %r", ticker
                )
                return recommendations
            else:
                logger.warning("No recommendations found for %r", ticker)
                return None

        except Exception as e:
            logger.error(
                "Error fetching recommendations for %r: %r", ticker, e
            )
            raise ProviderError("Yahoo Finance recommendations failed") from e
