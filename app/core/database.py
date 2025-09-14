from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Create SQLAlchemy engine - this manages the connection pool to the database
# The URL format is: postgresql://username:password@host:port/database_name
# We get these values from environment variables via settings
engine = create_engine(
    settings.DATABASE_URL,
    # echo=True  # Uncomment to see SQL queries in console (useful for debugging)
)

# SessionLocal is a factory for creating database sessions
# Each session represents a conversation with the database
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all database models (tables)
# This allows us to define models as Python classes that SQLAlchemy will convert to database tables
Base = declarative_base()

# Dependency function for FastAPI to inject database sessions into endpoints
def get_db():
    """
    Creates a new database session for each request.
    This ensures each API call gets its own database connection.
    The session is automatically closed after the request completes.
    """
    db = SessionLocal()
    try:
        yield db  # Yield the session to the endpoint
    finally:
        db.close()  # Always close the session, even if an error occurs
