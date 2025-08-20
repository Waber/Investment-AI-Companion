from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class CompanyDB(Base):
    """
    SQLAlchemy model for the companies table.
    This represents the actual database table structure.
    
    Key differences from Pydantic models:
    - Uses SQLAlchemy Column types (Integer, String, etc.)
    - Has __tablename__ to specify the table name
    - Can include database-specific features like indexes, constraints
    """
    __tablename__ = "companies"
    
    # Primary key - auto-incrementing integer
    id = Column(Integer, primary_key=True, index=True)
    
    # Company information fields
    name = Column(String(255), nullable=False, index=True)  # index=True creates a database index for faster searches
    ticker = Column(String(20), nullable=False, unique=True, index=True)  # unique=True ensures no duplicate tickers
    sector = Column(String(100), nullable=True)
    industry = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)  # Text allows longer content than String
    website = Column(String(500), nullable=True)
    country = Column(String(100), nullable=True)
    exchange = Column(String(50), nullable=True)
    currency = Column(String(3), default="USD")  # 3-letter currency codes like USD, EUR
    
    # Metadata fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # func.now() sets default to current timestamp
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # onupdate automatically updates this field
    is_active = Column(Boolean, default=True)
    last_data_update = Column(DateTime(timezone=True), nullable=True)
    
    # Relationship to financial metrics - one company can have many financial metrics
    # This creates a virtual field that allows us to access related data
    financial_metrics = relationship("FinancialMetricsDB", back_populates="company", cascade="all, delete-orphan")
    
    # Database constraints
    __table_args__ = (
        # Composite unique constraint - ensures name + ticker combination is unique
        UniqueConstraint('name', 'ticker', name='uq_company_name_ticker'),
    )

class FinancialMetricsDB(Base):
    """
    SQLAlchemy model for the financial_metrics table.
    Stores financial performance data for companies over time.
    """
    __tablename__ = "financial_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key relationship to companies table
    # This creates a database constraint ensuring data integrity
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    
    # Time period information
    period_end = Column(DateTime(timezone=True), nullable=False)
    period_type = Column(String(20), nullable=False)  # 'annual', 'quarterly', 'monthly' Enum?
    
    # Financial metrics - using Float for decimal numbers
    # These fields store the actual financial data
    revenue = Column(Float, nullable=True)
    net_income = Column(Float, nullable=True)
    total_assets = Column(Float, nullable=True)
    total_liabilities = Column(Float, nullable=True)
    total_equity = Column(Float, nullable=True)
    
    # Profitability ratios
    roe = Column(Float, nullable=True)  # Return on Equity
    roa = Column(Float, nullable=True)  # Return on Assets
    gross_margin = Column(Float, nullable=True)
    net_margin = Column(Float, nullable=True)
    
    # Liquidity ratios
    current_ratio = Column(Float, nullable=True)
    quick_ratio = Column(Float, nullable=True)
    
    # Debt ratios
    debt_to_equity = Column(Float, nullable=True)
    debt_to_assets = Column(Float, nullable=True)
    
    # Efficiency ratios
    asset_turnover = Column(Float, nullable=True)
    inventory_turnover = Column(Float, nullable=True)
    
    # Growth metrics
    revenue_growth = Column(Float, nullable=True)
    net_income_growth = Column(Float, nullable=True)
    
    # Valuation metrics
    pe_ratio = Column(Float, nullable=True)  # Price to Earnings
    pb_ratio = Column(Float, nullable=True)  # Price to Book
    ev_ebitda = Column(Float, nullable=True)  # Enterprise Value to EBITDA
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationship back to company
    company = relationship("CompanyDB", back_populates="financial_metrics")
    
    # Database constraints
    __table_args__ = (
        # Composite unique constraint - ensures one set of metrics per company per period
        UniqueConstraint('company_id', 'period_end', 'period_type', name='uq_metrics_company_period'),
    )
