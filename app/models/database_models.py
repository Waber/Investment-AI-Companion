from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.utc_datetime import UTCDateTime


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
    name = Column(
        String(255), nullable=False, index=True
    )  # index=True creates a database index for faster searches
    ticker = Column(
        String(20), nullable=False, unique=True, index=True
    )  # unique=True ensures no duplicate tickers
    sector = Column(String(100), nullable=True)
    industry = Column(String(100), nullable=True)
    description = Column(
        Text, nullable=True
    )  # Text allows longer content than String
    website = Column(String(500), nullable=True)
    country = Column(String(100), nullable=True)
    exchange = Column(String(50), nullable=True)
    currency = Column(
        String(3), default="USD"
    )  # 3-letter currency codes like USD, EUR
    # STOCK, ETF, or ETC. A short string plus a CHECK, not a PostgreSQL
    # ENUM: SQLite has no ENUM type, and one column type has to work
    # on both databases. Existing rows and omitted inserts are STOCK
    # because every company stored before this column was a share.
    instrument_type = Column(
        String(8),
        nullable=False,
        default="STOCK",
        server_default="STOCK",
    )
    # ISO 6166, already validated by the API. Null when unknown.
    # More than one null is allowed; a present ISIN is unique.
    isin = Column(String(12), nullable=True)

    # Metadata fields
    created_at = Column(
        UTCDateTime(), server_default=func.now()
    )  # func.now() sets default to current timestamp
    updated_at = Column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )  # onupdate automatically updates this field
    is_active = Column(Boolean, default=True)
    last_data_update = Column(UTCDateTime(), nullable=True)

    # One company has many financial-metrics rows.
    # This creates a virtual field that allows us to access related data
    financial_metrics = relationship(
        "FinancialMetricsDB",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    # Daily or weekly bars. Deleting the company deletes its bars,
    # the same way it deletes financial metrics. The column is
    # instrument_id because a price belongs to an instrument. The
    # row it points at is still companies.id: issue #26 added the
    # type and the ISIN on this table and did not rename it.
    price_bars = relationship(
        "PriceBarDB",
        back_populates="company",
        cascade="all, delete-orphan",
    )

    # Database constraints
    __table_args__ = (
        # name + ticker together must be unique.
        UniqueConstraint("name", "ticker", name="uq_company_name_ticker"),
        # Same unique index revision 0001 creates. Several null ISINs
        # are allowed; a present ISIN is stored once.
        Index("uq_companies_isin", "isin", unique=True),
        CheckConstraint(
            "instrument_type IN ('STOCK', 'ETF', 'ETC')",
            name="ck_companies_instrument_type",
        ),
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
    company_id = Column(
        Integer, ForeignKey("companies.id"), nullable=False, index=True
    )

    # Time period information
    period_end = Column(UTCDateTime(), nullable=False)
    period_type = Column(
        String(20), nullable=False
    )  # 'annual', 'quarterly', 'monthly' Enum?

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
    created_at = Column(UTCDateTime(), server_default=func.now())
    updated_at = Column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )

    # Relationship back to company
    company = relationship("CompanyDB", back_populates="financial_metrics")

    # Database constraints
    __table_args__ = (
        # One metrics row per company, period end, and period type.
        UniqueConstraint(
            "company_id",
            "period_end",
            "period_type",
            name="uq_metrics_company_period",
        ),
    )


class PriceBarDB(Base):
    """One stored price bar for an instrument.

    ``bar_date`` is a calendar date, not a timestamp: a daily or
    weekly bar names the session, and two offsets must not turn one
    session into two rows. OHLC and volume may be null. A missing
    provider value stays null and is never written as zero.

    The same session can be stored twice only when ``source`` differs
    (a seeded synthetic bar and a later collector refresh). The
    unique key is ``(instrument_id, bar_date, source)``.
    """

    __tablename__ = "price_bars"

    id = Column(Integer, primary_key=True, index=True)
    instrument_id = Column(
        Integer, ForeignKey("companies.id"), nullable=False, index=True
    )
    bar_date = Column(Date, nullable=False)
    open_price = Column(Float, nullable=True)
    high_price = Column(Float, nullable=True)
    low_price = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)
    currency = Column(String(3), nullable=False)
    source = Column(String(64), nullable=False)
    retrieved_at = Column(UTCDateTime(), nullable=False)

    company = relationship("CompanyDB", back_populates="price_bars")

    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "bar_date",
            "source",
            name="uq_price_bars_instrument_date_source",
        ),
    )
