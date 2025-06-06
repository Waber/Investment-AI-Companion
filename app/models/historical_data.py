from datetime import datetime
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field


class HistoricalDataBase(BaseModel):
    """Podstawowy model danych historycznych."""
    date: datetime = Field(..., description="Data notowania")
    open_price: Decimal = Field(..., description="Cena otwarcia")
    high_price: Decimal = Field(..., description="Najwyższa cena")
    low_price: Decimal = Field(..., description="Najniższa cena")
    close_price: Decimal = Field(..., description="Cena zamknięcia")
    volume: int = Field(..., description="Wolumen obrotu")
    adjusted_close: Optional[Decimal] = Field(None, description="Skorygowana cena zamknięcia")
    
    # Dodatkowe dane rynkowe
    market_cap: Optional[Decimal] = Field(None, description="Kapitalizacja rynkowa")
    enterprise_value: Optional[Decimal] = Field(None, description="Wartość przedsiębiorstwa")
    shares_outstanding: Optional[int] = Field(None, description="Liczba akcji w obrocie")
    avg_volume: Optional[int] = Field(None, description="Średni dzienny wolumen")
    
    # Wskaźniki techniczne
    sma_20: Optional[Decimal] = Field(None, description="20-dniowa średnia krocząca")
    sma_50: Optional[Decimal] = Field(None, description="50-dniowa średnia krocząca")
    sma_200: Optional[Decimal] = Field(None, description="200-dniowa średnia krocząca")
    rsi_14: Optional[Decimal] = Field(None, description="14-dniowy wskaźnik RSI")
    macd: Optional[Decimal] = Field(None, description="Wskaźnik MACD")
    macd_signal: Optional[Decimal] = Field(None, description="Linia sygnałowa MACD")
    macd_hist: Optional[Decimal] = Field(None, description="Histogram MACD")


class HistoricalDataCreate(HistoricalDataBase):
    """Model do tworzenia nowych danych historycznych."""
    company_id: int = Field(..., description="ID firmy")


class HistoricalDataUpdate(HistoricalDataBase):
    """Model do aktualizacji danych historycznych."""
    pass


class HistoricalData(HistoricalDataBase):
    """Pełny model danych historycznych z dodatkowymi polami."""
    id: int = Field(..., description="Unikalny identyfikator")
    company_id: int = Field(..., description="ID firmy")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True  # dla kompatybilności z SQLAlchemy 