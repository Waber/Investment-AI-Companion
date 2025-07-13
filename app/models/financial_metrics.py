from datetime import datetime, timezone
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field


class FinancialMetricsBase(BaseModel):
    """Base financial metrics model."""
    # Profitability ratios
    roe: Optional[Decimal] = Field(None, description="Return on Equity (ROE)")
    roa: Optional[Decimal] = Field(None, description="Return on Assets (ROA)")
    operating_margin: Optional[Decimal] = Field(None, description="Operating margin")
    net_profit_margin: Optional[Decimal] = Field(None, description="Net profit margin")
    
    # Liquidity ratios
    current_ratio: Optional[Decimal] = Field(None, description="Current ratio")
    quick_ratio: Optional[Decimal] = Field(None, description="Quick ratio")
    cash_ratio: Optional[Decimal] = Field(None, description="Cash ratio")
    
    # Debt ratios
    debt_to_equity: Optional[Decimal] = Field(None, description="Debt to equity ratio")
    debt_to_assets: Optional[Decimal] = Field(None, description="Debt to assets ratio")
    interest_coverage: Optional[Decimal] = Field(None, description="Interest coverage ratio")
    
    # Efficiency ratios
    asset_turnover: Optional[Decimal] = Field(None, description="Asset turnover")
    inventory_turnover: Optional[Decimal] = Field(None, description="Inventory turnover")
    receivables_turnover: Optional[Decimal] = Field(None, description="Receivables turnover")
    
    # Growth ratios
    revenue_growth: Optional[Decimal] = Field(None, description="Revenue growth (YoY)")
    earnings_growth: Optional[Decimal] = Field(None, description="Earnings growth (YoY)")
    eps_growth: Optional[Decimal] = Field(None, description="EPS growth (YoY)")
    
    # Valuation ratios
    pe_ratio: Optional[Decimal] = Field(None, description="Price to Earnings (P/E) ratio")
    pb_ratio: Optional[Decimal] = Field(None, description="Price to Book (P/B) ratio")
    ps_ratio: Optional[Decimal] = Field(None, description="Price to Sales (P/S) ratio")
    ev_ebitda: Optional[Decimal] = Field(None, description="EV/EBITDA ratio")
    
    # Additional metrics
    dividend_yield: Optional[Decimal] = Field(None, description="Dividend yield")
    payout_ratio: Optional[Decimal] = Field(None, description="Payout ratio")
    beta: Optional[Decimal] = Field(None, description="Beta coefficient")


class FinancialMetricsCreate(FinancialMetricsBase):
    """Model for creating new financial metrics."""
    company_id: int = Field(..., description="Company ID")
    period_end: datetime = Field(..., description="End of reporting period date")
    period_type: str = Field(..., description="Period type (quarterly/annual)")


class FinancialMetricsUpdate(FinancialMetricsBase):
    """Model for updating financial metrics."""
    pass


class FinancialMetrics(FinancialMetricsBase):
    """Full financial metrics model with additional fields."""
    id: int = Field(..., description="Unique identifier")
    company_id: int = Field(..., description="Company ID")
    period_end: datetime = Field(..., description="End of reporting period date")
    period_type: str = Field(..., description="Period type (quarterly/annual)")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        from_attributes = True  # for SQLAlchemy compatibility 