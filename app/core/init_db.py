from datetime import datetime, timezone

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.database import Base, engine
from app.models.database_models import CompanyDB, FinancialMetricsDB

# create_all adds a missing table. It does not add columns to one
# that is already there. These two arrived in revision 0001.
_COMPANY_COLUMNS = ("instrument_type", "isin")


class CompanySchemaError(RuntimeError):
    """``companies`` exists and is missing columns this process needs."""


def require_company_instrument_columns(db_engine) -> None:
    """Stop startup when an older ``companies`` table is still in use.

    A missing table is left for ``create_all``. A table that is
    present without ``instrument_type`` or ``isin`` would otherwise
    start and fail on the first query. The message tells the
    operator which Alembic command matches the database they have.
    """
    inspector = inspect(db_engine)
    if "companies" not in inspector.get_table_names():
        return
    present = {column["name"] for column in inspector.get_columns("companies")}
    missing = [name for name in _COMPANY_COLUMNS if name not in present]
    if not missing:
        return
    raise CompanySchemaError(
        "companies is missing "
        + " and ".join(missing)
        + ". An Alembic-managed database runs `alembic upgrade head`. "
        "A database created by an older startup create_all needs that "
        "upgrade. Adding the columns by hand skips the "
        "ck_companies_instrument_type CHECK, the uq_companies_isin "
        "unique index, and `alembic stamp head`. "
        "A fresh create_all database already has the columns: "
        "run `alembic stamp head`, not `alembic upgrade head`."
    )


def init_db():
    """
    Initialize the database by creating all tables.
    This function should be called when the application starts for the first time.
    """
    # Create all tables defined in our models.
    # This creates companies, financial_metrics, price_bars, and
    # watchlist_items when they are missing. It does not add columns
    # to an old table.
    Base.metadata.create_all(bind=engine)
    require_company_instrument_columns(engine)
    print("Database tables created successfully!")  # logs instead of print?


def seed_sample_data(db: Session):
    """
    Add sample data to the database for testing purposes.
    This is optional and only used during development.
    """
    # Check if we already have data
    if db.query(CompanyDB).first():
        print("Database already contains data, skipping seed.")
        return

    print("Seeding database with sample data...")

    # Create sample companies
    sample_companies = [
        CompanyDB(
            name="Apple Inc.",
            ticker="AAPL",
            sector="Technology",
            industry="Consumer Electronics",
            description="Apple Inc. designs, manufactures, and markets smartphones, personal computers, tablets, wearables, and accessories worldwide.",
            website="https://www.apple.com",
            country="USA",
            exchange="NASDAQ",
            currency="USD",
        ),
        CompanyDB(
            name="Microsoft Corporation",
            ticker="MSFT",
            sector="Technology",
            industry="Software",
            description="Microsoft Corporation develops, licenses, and supports software, services, devices, and solutions worldwide.",
            website="https://www.microsoft.com",
            country="USA",
            exchange="NASDAQ",
            currency="USD",
        ),
        CompanyDB(
            name="Tesla, Inc.",
            ticker="TSLA",
            sector="Consumer Discretionary",
            industry="Automobiles",
            description="Tesla, Inc. designs, develops, manufactures, leases, and sells electric vehicles, and energy generation and storage systems.",
            website="https://www.tesla.com",
            country="USA",
            exchange="NASDAQ",
            currency="USD",
        ),
    ]

    # Add companies to database
    for company in sample_companies:
        db.add(company)

    # Commit to get the IDs
    db.commit()

    # Create sample financial metrics for Apple
    apple = db.query(CompanyDB).filter(CompanyDB.ticker == "AAPL").first()
    if apple:
        sample_metrics = [
            FinancialMetricsDB(
                company_id=apple.id,
                period_end=datetime(2023, 12, 31, tzinfo=timezone.utc),
                period_type="annual",
                revenue=383285000000.0,  # $383.285 billion
                net_income=96995000000.0,  # $96.995 billion
                total_assets=352755000000.0,
                total_equity=62146000000.0,
                roe=15.6,  # 15.6%
                roa=27.5,  # 27.5%
                gross_margin=44.1,
                net_margin=25.3,
                pe_ratio=31.2,
            ),
            FinancialMetricsDB(
                company_id=apple.id,
                period_end=datetime(2022, 12, 31, tzinfo=timezone.utc),
                period_type="annual",
                revenue=394328000000.0,  # $394.328 billion
                net_income=96995000000.0,  # $96.995 billion
                total_assets=346747000000.0,
                total_equity=50672000000.0,
                roe=19.1,  # 19.1%
                roa=28.0,  # 28.0%
                gross_margin=43.3,
                net_margin=24.6,
                pe_ratio=25.8,
            ),
        ]

        for metrics in sample_metrics:
            db.add(metrics)

    # Commit all changes
    db.commit()
    print("Sample data seeded successfully!")


if __name__ == "__main__":
    # This allows us to run this script directly to initialize the database
    init_db()
    print("Database initialization complete!")
