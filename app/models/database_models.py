from sqlalchemy import (
    BigInteger,
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
    text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.utc_datetime import UTCDateTime
from app.models.price_amount import PriceAmount, price_compare
from app.models.research import (
    NOTE_BODY_MAX,
    THESIS_BODY_MAX,
    THESIS_BREAKERS_MAX,
    THESIS_STATUS_CHECK,
    THESIS_TITLE_MAX,
    ThesisStatus,
)
from app.models.watchlist import WATCHLIST_LABEL_MAX_LENGTH


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
    # Not unique=True. That flag would create ix_companies_ticker.
    # The unique index is uq_companies_ticker. Revision 0003 created
    # it on the column. Revision 0007 replaces it with a unique index
    # on upper(ticker), so raw SQL cannot store 'aapl' next to
    # 'AAPL'. The application already uppercases a ticker before it
    # writes. It stays an index rather than a UNIQUE CONSTRAINT so
    # SQLite does not have to rebuild companies to add it. The ISIN
    # index is the same kind of index.
    ticker = Column(String(20), nullable=False)
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
    # passive_deletes leaves the DELETE of these rows to the database.
    # The foreign key uses ON DELETE CASCADE. Loading every bar into
    # the session just to delete the company would be wasted work.
    price_bars = relationship(
        "PriceBarDB",
        back_populates="company",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    # One watchlist row per company. Deleting the company deletes that
    # row. passive_deletes leaves the DELETE to the database: the
    # foreign key is ON DELETE CASCADE, so the session does not load
    # the watchlist row just to remove it.
    watchlist_item = relationship(
        "WatchlistItemDB",
        back_populates="company",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    # The database removes notes and theses when the company row is
    # deleted (ON DELETE CASCADE). passive_deletes="all" tells
    # SQLAlchemy not to blank company_id on those rows first.
    # Financial metrics above do not use a database cascade; the
    # relationship deletes them in the session instead.
    notes = relationship(
        "NoteDB",
        back_populates="company",
        passive_deletes="all",
    )
    theses = relationship(
        "ThesisDB",
        back_populates="company",
        passive_deletes="all",
    )

    # Database constraints
    __table_args__ = (
        # One row per ticker, ignoring case. The company name may be
        # shared (BRK.A and BRK.B). Revision 0007 creates this index
        # and drops uq_company_name_ticker: ticker uniqueness already
        # makes that pair unique, so the pair constraint was redundant.
        Index("uq_companies_ticker", func.upper(ticker), unique=True),
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

    The check constraints match ``PriceBarCreate``. A SQL ``CHECK``
    passes when its expression is true or null, so a missing price
    does not fail the comparison that uses it. When both sides are
    present, high is at least the open and the close, low is at most
    the open and the close, high is at least the low, and volume is
    not negative. The API model is the exact check. On SQLite the
    prices are text, so the database check casts each side to REAL
    (a text comparison would reject low 9 and open 10). PostgreSQL
    compares the numeric columns directly.
    """

    __tablename__ = "price_bars"

    # No index=True on the primary key. That flag would add a second
    # index, ix_price_bars_id, beside the primary key itself.
    id = Column(Integer, primary_key=True)
    # No separate index on instrument_id. The unique key starts with
    # that column, so a lookup by instrument already has an index.
    # ON DELETE CASCADE removes the bars when the company row goes,
    # including a DELETE that did not load this relationship.
    instrument_id = Column(
        Integer,
        ForeignKey(
            "companies.id",
            name="fk_price_bars_instrument_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    bar_date = Column(Date, nullable=False)
    # PriceAmount is Numeric(20, 8) on PostgreSQL and TEXT on SQLite.
    # The text is the canonical 8-place string, so SQLite does not
    # round the price through a binary float.
    open_price = Column(PriceAmount(), nullable=True)
    high_price = Column(PriceAmount(), nullable=True)
    low_price = Column(PriceAmount(), nullable=True)
    close_price = Column(PriceAmount(), nullable=True)
    # BigInteger, not Integer. PostgreSQL INTEGER is int4 and rejects
    # a volume above 2_147_483_647. A busy session can be larger.
    # The Pydantic model caps the value at the signed 64-bit maximum.
    volume = Column(BigInteger, nullable=True)
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
        CheckConstraint(
            price_compare("high_price", ">=", "open_price"),
            name="ck_price_bars_high_gte_open",
        ),
        CheckConstraint(
            price_compare("high_price", ">=", "close_price"),
            name="ck_price_bars_high_gte_close",
        ),
        CheckConstraint(
            price_compare("low_price", "<=", "open_price"),
            name="ck_price_bars_low_lte_open",
        ),
        CheckConstraint(
            price_compare("low_price", "<=", "close_price"),
            name="ck_price_bars_low_lte_close",
        ),
        CheckConstraint(
            price_compare("high_price", ">=", "low_price"),
            name="ck_price_bars_high_gte_low",
        ),
        CheckConstraint(
            "volume >= 0",
            name="ck_price_bars_volume_gte_zero",
        ),
    )


class WatchlistItemDB(Base):
    """One company on the single v1 watchlist.

    ``company_id`` is unique, so adding the same company again is the
    same row. ``added_at`` is an aware UTC instant. ``label`` is an
    optional short note. The foreign key uses ON DELETE CASCADE, and
    ``CompanyDB.watchlist_item`` sets ``passive_deletes`` so a company
    delete does not load this row first.
    """

    __tablename__ = "watchlist_items"

    # No index=True. The primary key is already an index, and a second
    # one would be ix_watchlist_items_id. Lookups use company_id, which
    # the unique constraint indexes.
    id = Column(Integer, primary_key=True)
    company_id = Column(
        Integer,
        ForeignKey(
            "companies.id",
            name="fk_watchlist_items_company_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    added_at = Column(UTCDateTime(), nullable=False)
    label = Column(String(WATCHLIST_LABEL_MAX_LENGTH), nullable=True)

    company = relationship("CompanyDB", back_populates="watchlist_item")

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            name="uq_watchlist_items_company_id",
        ),
    )


class NoteDB(Base):
    """One free-text note attached to a company.

    ``company_id`` is indexed because the list for a company is the
    common read. Deleting the company deletes the note in the
    database. The repository still checks that the company exists
    on create, because a SQLite connection can have foreign keys
    turned off.
    """

    __tablename__ = "notes"

    id = Column(Integer, primary_key=True)
    company_id = Column(
        Integer,
        ForeignKey(
            "companies.id",
            name="fk_notes_company_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    body = Column(String(NOTE_BODY_MAX), nullable=False)
    # The database fills both clocks on insert. An update sets
    # ``updated_at`` in the repository, in UTC. There is no
    # ``onupdate`` here: that would be a second clock.
    created_at = Column(
        UTCDateTime(),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        UTCDateTime(),
        nullable=False,
        server_default=func.now(),
    )

    company = relationship("CompanyDB", back_populates="notes")


class ThesisDB(Base):
    """One investment thesis attached to a company.

    ``status`` is a short string plus a CHECK, not a PostgreSQL ENUM.
    SQLite has no ENUM type, and one column type has to work on both
    databases. ``thesis_breakers`` is an empty string when the thesis
    has none yet; it is not NULL.
    """

    __tablename__ = "theses"

    id = Column(Integer, primary_key=True)
    company_id = Column(
        Integer,
        ForeignKey(
            "companies.id",
            name="fk_theses_company_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    title = Column(String(THESIS_TITLE_MAX), nullable=False)
    body = Column(String(THESIS_BODY_MAX), nullable=False)
    thesis_breakers = Column(
        String(THESIS_BREAKERS_MAX),
        nullable=False,
        default="",
        server_default=text("''"),
    )
    # 'active' and 'closed' are both 6 characters. The CHECK below
    # is what limits the value; the length only sizes the column.
    status = Column(
        String(max(len(item.value) for item in ThesisStatus)),
        nullable=False,
        default=ThesisStatus.ACTIVE.value,
        server_default=text("'active'"),
    )
    # Same clocks as ``NoteDB``. Insert uses the server default.
    # The repository sets ``updated_at`` when a field changes.
    created_at = Column(
        UTCDateTime(),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        UTCDateTime(),
        nullable=False,
        server_default=func.now(),
    )

    company = relationship("CompanyDB", back_populates="theses")

    __table_args__ = (
        CheckConstraint(THESIS_STATUS_CHECK, name="ck_theses_status"),
    )
