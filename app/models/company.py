from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl


class CompanyBase(BaseModel):
    """Podstawowy model firmy."""
    name: str = Field(..., description="Nazwa firmy")
    ticker: str = Field(..., description="Symbol giełdowy")
    sector: Optional[str] = Field(None, description="Sektor gospodarki")
    industry: Optional[str] = Field(None, description="Branża")
    description: Optional[str] = Field(None, description="Krótki opis firmy")
    website: Optional[HttpUrl] = Field(None, description="Strona internetowa firmy")
    country: Optional[str] = Field(None, description="Kraj pochodzenia")
    exchange: Optional[str] = Field(None, description="Giełda, na której notowana jest spółka")
    currency: Optional[str] = Field("USD", description="Waluta, w której podawane są dane finansowe")


class CompanyCreate(CompanyBase):
    """Model do tworzenia nowej firmy."""
    pass


class CompanyUpdate(CompanyBase):
    """Model do aktualizacji danych firmy."""
    name: Optional[str] = None
    ticker: Optional[str] = None


class Company(CompanyBase):
    """Pełny model firmy z dodatkowymi polami."""
    id: int = Field(..., description="Unikalny identyfikator firmy")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True, description="Czy firma jest aktywna w systemie")
    last_data_update: Optional[datetime] = Field(None, description="Data ostatniej aktualizacji danych")
    
    class Config:
        from_attributes = True  # dla kompatybilności z SQLAlchemy 