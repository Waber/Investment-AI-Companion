from datetime import datetime
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field


class FinancialMetricsBase(BaseModel):
    """Podstawowy model wskaźników finansowych."""
    # Wskaźniki rentowności
    roe: Optional[Decimal] = Field(None, description="Return on Equity (ROE) - rentowność kapitału własnego")
    roa: Optional[Decimal] = Field(None, description="Return on Assets (ROA) - rentowność aktywów")
    operating_margin: Optional[Decimal] = Field(None, description="Marża operacyjna")
    net_profit_margin: Optional[Decimal] = Field(None, description="Marża zysku netto")
    
    # Wskaźniki płynności
    current_ratio: Optional[Decimal] = Field(None, description="Wskaźnik bieżącej płynności")
    quick_ratio: Optional[Decimal] = Field(None, description="Wskaźnik szybkiej płynności")
    cash_ratio: Optional[Decimal] = Field(None, description="Wskaźnik płynności gotówkowej")
    
    # Wskaźniki zadłużenia
    debt_to_equity: Optional[Decimal] = Field(None, description="Wskaźnik zadłużenia do kapitału własnego")
    debt_to_assets: Optional[Decimal] = Field(None, description="Wskaźnik zadłużenia do aktywów")
    interest_coverage: Optional[Decimal] = Field(None, description="Wskaźnik pokrycia obsługi długu")
    
    # Wskaźniki efektywności
    asset_turnover: Optional[Decimal] = Field(None, description="Rotacja aktywów")
    inventory_turnover: Optional[Decimal] = Field(None, description="Rotacja zapasów")
    receivables_turnover: Optional[Decimal] = Field(None, description="Rotacja należności")
    
    # Wskaźniki wzrostu
    revenue_growth: Optional[Decimal] = Field(None, description="Wzrost przychodów (YoY)")
    earnings_growth: Optional[Decimal] = Field(None, description="Wzrost zysku (YoY)")
    eps_growth: Optional[Decimal] = Field(None, description="Wzrost EPS (YoY)")
    
    # Wskaźniki wyceny
    pe_ratio: Optional[Decimal] = Field(None, description="Wskaźnik C/Z (P/E)")
    pb_ratio: Optional[Decimal] = Field(None, description="Wskaźnik C/WK (P/B)")
    ps_ratio: Optional[Decimal] = Field(None, description="Wskaźnik C/P (P/S)")
    ev_ebitda: Optional[Decimal] = Field(None, description="Wskaźnik EV/EBITDA")
    
    # Dodatkowe wskaźniki
    dividend_yield: Optional[Decimal] = Field(None, description="Stopa dywidendy")
    payout_ratio: Optional[Decimal] = Field(None, description="Wskaźnik wypłaty dywidendy")
    beta: Optional[Decimal] = Field(None, description="Współczynnik beta")


class FinancialMetricsCreate(FinancialMetricsBase):
    """Model do tworzenia nowych wskaźników finansowych."""
    company_id: int = Field(..., description="ID firmy")
    period_end: datetime = Field(..., description="Data końca okresu sprawozdawczego")
    period_type: str = Field(..., description="Typ okresu (quarterly/annual)")


class FinancialMetricsUpdate(FinancialMetricsBase):
    """Model do aktualizacji wskaźników finansowych."""
    pass


class FinancialMetrics(FinancialMetricsBase):
    """Pełny model wskaźników finansowych z dodatkowymi polami."""
    id: int = Field(..., description="Unikalny identyfikator")
    company_id: int = Field(..., description="ID firmy")
    period_end: datetime = Field(..., description="Data końca okresu sprawozdawczego")
    period_type: str = Field(..., description="Typ okresu (quarterly/annual)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True  # dla kompatybilności z SQLAlchemy 