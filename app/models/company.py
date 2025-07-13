from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl


class CompanyBase(BaseModel):
    """Base company model."""
    name: str = Field(..., description="Company name")
    ticker: str = Field(..., description="Stock ticker symbol")
    sector: Optional[str] = Field(None, description="Economic sector")
    industry: Optional[str] = Field(None, description="Industry")
    description: Optional[str] = Field(None, description="Brief company description")
    website: HttpUrl | None = Field(None, description="Company website")
    country: Optional[str] = Field(None, description="Country of origin")
    exchange: Optional[str] = Field(None, description="Stock exchange where the company is listed")
    currency: Optional[str] = Field("USD", description="Currency for financial data")


class CompanyCreate(CompanyBase):
    """Model for creating a new company."""
    pass


class CompanyUpdate(CompanyBase):
    """Model for updating company data."""
    name: Optional[str] = None
    ticker: Optional[str] = None


class Company(CompanyBase):
    """Full company model with additional fields."""
    id: int = Field(..., description="Unique company identifier")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = Field(default=True, description="Whether the company is active in the system")
    last_data_update: Optional[datetime] = Field(None, description="Date of last data update")
    
    class Config:
        from_attributes = True  # for SQLAlchemy compatibility 