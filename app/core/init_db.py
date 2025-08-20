from sqlalchemy.orm import Session
from app.core.database import engine, Base
from app.models.database_models import CompanyDB, FinancialMetricsDB
from datetime import datetime, timezone

def init_db():
    """
    Initialize the database by creating all tables.
    This function should be called when the application starts for the first time.
    """
    # Create all tables defined in our models
    # This will create the 'companies' and 'financial_metrics' tables
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")#logs instead of print?

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
            currency="USD"
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
            currency="USD"
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
            currency="USD"
        )
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
                pe_ratio=31.2
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
                pe_ratio=25.8
            )
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
