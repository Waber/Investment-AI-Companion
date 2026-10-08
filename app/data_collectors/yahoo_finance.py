"""
Yahoo Finance data collector module.

This module provides functionality to fetch stock market data from
Yahoo Finance using the yfinance library.
"""

import logging
from typing import Any, Dict, Optional

import yfinance as yf

logger = logging.getLogger(__name__)


def _is_real_number(value: Any) -> bool:
    """True for int and float, and false for bool.

    ``bool`` is a subclass of ``int``. ``True / 200`` would look like a
    ratio and would not be one, so booleans are rejected here.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _debt_to_assets(info: Dict[str, Any]) -> Optional[float]:
    """Return total debt divided by total assets from ``info`` alone.

    Yahoo's ``totalDebtPerShare`` is a currency amount per share, not
    this ratio, so this function never reads that field.
    ``fetch_key_metrics`` has already loaded ``info``. This does not
    call the provider again. If either total is missing, is not a real
    number, or total assets is zero, the ratio is unknown and the
    result is None.
    """
    total_debt = info.get("totalDebt")
    total_assets = info.get("totalAssets")
    if not _is_real_number(total_debt) or not _is_real_number(total_assets):
        return None
    if total_assets == 0:
        return None
    return total_debt / total_assets


class YahooFinanceCollector:
    """
    Collector for fetching stock market data from Yahoo Finance.

    This class wraps the yfinance library to provide a clean interface
    for fetching various types of financial data.
    """

    def __init__(self):
        """Initialize the Yahoo Finance collector."""
        pass

    def fetch_company_info(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch basic company information for a given ticker.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'TSLA')

        Returns:
            Dictionary containing company information or None if not found

        Example:
            >>> collector = YahooFinanceCollector()
            >>> info = collector.fetch_company_info('AAPL')
            >>> print(info['longName'])
            Apple Inc.
        """
        try:
            logger.info(f"Fetching company info for ticker: {ticker}")
            stock = yf.Ticker(ticker)
            info = stock.info

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

            logger.info(f"Successfully fetched company info for {ticker}")
            return company_info

        except Exception as e:
            logger.error(f"Error fetching company info for {ticker}: {str(e)}")
            return None

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
            DataFrame with historical data or None if error

        Example:
            >>> collector = YahooFinanceCollector()
            >>> data = collector.fetch_historical_data('AAPL', period='1y')
        """
        try:
            logger.info(
                f"Fetching historical data for {ticker}, "
                f"period={period}, interval={interval}"
            )
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period, interval=interval)

            if hist.empty:
                logger.warning(f"No historical data found for {ticker}")
                return None

            logger.info(
                f"Successfully fetched {len(hist)} records for {ticker}"
            )
            return hist

        except Exception as e:
            logger.error(
                f"Error fetching historical data for {ticker}: {str(e)}"
            )
            return None

    def fetch_financial_statements(
        self, ticker: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch financial statements (income, balance sheet, cash flow).

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with financial statements or None if error

        Example:
            >>> collector = YahooFinanceCollector()
            >>> statements = collector.fetch_financial_statements('AAPL')
            >>> income_stmt = statements['income_statement']
        """
        try:
            logger.info(f"Fetching financial statements for {ticker}")
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
                f"Successfully fetched financial statements for {ticker}"
            )
            return financials

        except Exception as e:
            logger.error(
                f"Error fetching financial statements for {ticker}: {str(e)}"
            )
            return None

    def fetch_key_metrics(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch key financial metrics and ratios.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with key metrics or None if error

        Example:
            >>> collector = YahooFinanceCollector()
            >>> metrics = collector.fetch_key_metrics('AAPL')
            >>> print(metrics['pe_ratio'])
        """
        try:
            logger.info(f"Fetching key metrics for {ticker}")
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
                "debt_to_assets": _debt_to_assets(info),
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

            logger.info(f"Successfully fetched key metrics for {ticker}")
            return metrics

        except Exception as e:
            logger.error(f"Error fetching key metrics for {ticker}: {str(e)}")
            return None

    def fetch_news(self, ticker: str, limit: int = 10) -> Optional[list]:
        """
        Fetch recent news articles about a company.

        Args:
            ticker: Stock ticker symbol
            limit: Maximum number of news articles to fetch

        Returns:
            List of news articles or None if error
        """
        try:
            logger.info(f"Fetching news for {ticker}")
            stock = yf.Ticker(ticker)
            news_list = stock.news

            # Limit the number of results
            limited_news = news_list[:limit] if news_list else []

            logger.info(
                f"Successfully fetched {len(limited_news)} "
                f"news articles for {ticker}"
            )
            return limited_news

        except Exception as e:
            logger.error(f"Error fetching news for {ticker}: {str(e)}")
            return None

    def fetch_recommendations(self, ticker: str) -> Optional[Any]:
        """
        Fetch analyst recommendations and consensus.

        Args:
            ticker: Stock ticker symbol

        Returns:
            DataFrame with recommendations or None if error
        """
        try:
            logger.info(f"Fetching recommendations for {ticker}")
            stock = yf.Ticker(ticker)
            recommendations = stock.recommendations

            if recommendations is not None and not recommendations.empty:
                logger.info(
                    f"Successfully fetched recommendations for {ticker}"
                )
                return recommendations
            else:
                logger.warning(f"No recommendations found for {ticker}")
                return None

        except Exception as e:
            logger.error(
                f"Error fetching recommendations for {ticker}: {str(e)}"
            )
            return None
