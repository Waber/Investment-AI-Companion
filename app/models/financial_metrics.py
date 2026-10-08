from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class FinancialMetricsBase(BaseModel):
    """Base financial metrics model."""

    model_config = ConfigDict(allow_inf_nan=False)

    # Statement values
    revenue: Optional[float] = Field(None, description="Revenue")
    net_income: Optional[float] = Field(None, description="Net income")
    total_assets: Optional[float] = Field(None, description="Total assets")
    total_liabilities: Optional[float] = Field(
        None, description="Total liabilities"
    )
    total_equity: Optional[float] = Field(None, description="Total equity")

    # Profitability ratios
    roe: Optional[float] = Field(None, description="Return on Equity (ROE)")
    roa: Optional[float] = Field(None, description="Return on Assets (ROA)")
    gross_margin: Optional[float] = Field(None, description="Gross margin")
    net_margin: Optional[float] = Field(None, description="Net margin")

    # Liquidity ratios
    current_ratio: Optional[float] = Field(None, description="Current ratio")
    quick_ratio: Optional[float] = Field(None, description="Quick ratio")

    # Debt ratios
    debt_to_equity: Optional[float] = Field(
        None, description="Debt to equity ratio"
    )
    debt_to_assets: Optional[float] = Field(
        None, description="Debt to assets ratio"
    )

    # Efficiency ratios
    asset_turnover: Optional[float] = Field(None, description="Asset turnover")
    inventory_turnover: Optional[float] = Field(
        None, description="Inventory turnover"
    )

    # Growth ratios
    revenue_growth: Optional[float] = Field(
        None, description="Revenue growth (YoY)"
    )
    net_income_growth: Optional[float] = Field(
        None,
        description="Net income growth (YoY)",
    )

    # Valuation ratios
    pe_ratio: Optional[float] = Field(
        None,
        description="Price to Earnings (P/E) ratio",
    )
    pb_ratio: Optional[float] = Field(
        None, description="Price to Book (P/B) ratio"
    )
    ev_ebitda: Optional[float] = Field(None, description="EV/EBITDA ratio")


class FinancialMetricsCreate(FinancialMetricsBase):
    """Model for creating new financial metrics."""

    company_id: int = Field(..., description="Company ID")
    period_end: datetime = Field(
        ..., description="End of reporting period date"
    )
    period_type: str = Field(..., description="Period type (quarterly/annual)")


class FinancialMetricsUpdate(FinancialMetricsBase):
    """Partial update of financial metrics.

    ``period_end`` is optional. When a client sends it, the repository
    converts it to aware UTC before the uniqueness check. Omitted fields
    stay as they are.
    """

    period_end: Optional[datetime] = None


class FinancialMetrics(FinancialMetricsBase):
    """Full financial metrics model with additional fields."""

    id: int = Field(..., description="Unique identifier")
    company_id: int = Field(..., description="Company ID")
    period_end: datetime = Field(
        ..., description="End of reporting period date"
    )
    period_type: str = Field(..., description="Period type (quarterly/annual)")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # from_attributes reads SQLAlchemy rows. allow_inf_nan stays False
    # so this response model still rejects Infinity and NaN.
    model_config = ConfigDict(
        allow_inf_nan=False,
        from_attributes=True,
    )
