from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class HistoricalDataBase(BaseModel):
    """Base historical data model."""
    date: datetime = Field(..., description="Trading date")
    open_price: Decimal = Field(..., description="Opening price")
    high_price: Decimal = Field(..., description="Highest price")
    low_price: Decimal = Field(..., description="Lowest price")
    close_price: Decimal = Field(..., description="Closing price")
    volume: int = Field(..., description="Trading volume")
    adjusted_close: Optional[Decimal] = Field(None, description="Adjusted closing price")
    
    # Additional market data
    market_cap: Optional[Decimal] = Field(None, description="Market capitalization")
    enterprise_value: Optional[Decimal] = Field(None, description="Enterprise value")
    shares_outstanding: Optional[int] = Field(None, description="Shares outstanding")
    avg_volume: Optional[int] = Field(None, description="Average daily volume")
    
    # Technical indicators
    sma_20: Optional[Decimal] = Field(None, description="20-day simple moving average")
    sma_50: Optional[Decimal] = Field(None, description="50-day simple moving average")
    sma_200: Optional[Decimal] = Field(None, description="200-day simple moving average")
    rsi_14: Optional[Decimal] = Field(None, description="14-day RSI indicator")
    macd: Optional[Decimal] = Field(None, description="MACD indicator")
    macd_signal: Optional[Decimal] = Field(None, description="MACD signal line")
    macd_hist: Optional[Decimal] = Field(None, description="MACD histogram")


class HistoricalDataCreate(HistoricalDataBase):
    """Model for creating new historical data."""
    company_id: int = Field(..., description="Company ID")


class HistoricalDataUpdate(HistoricalDataBase):
    """Model for updating historical data."""
    pass


class HistoricalData(HistoricalDataBase):
    """Full historical data model with additional fields."""
    id: int = Field(..., description="Unique identifier")
    company_id: int = Field(..., description="Company ID")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        from_attributes = True  # for SQLAlchemy compatibility 