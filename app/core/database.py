"""Database engine and the request-scoped session.

SQLite does not enforce foreign keys unless every connection runs
``PRAGMA foreign_keys=ON``. The pragma is per connection: a new
physical connection starts with foreign keys off. Registering it on
the application engine means the demo, scripts, and tests share one
implementation. PostgreSQL enforces foreign keys itself, so the hook
is not attached for that dialect.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """Enable foreign keys on one SQLite DB-API connection."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def create_db_engine(url, **kwargs):
    """Create an engine and apply the SQLite foreign-key hook."""
    db_engine = create_engine(url, **kwargs)
    if db_engine.dialect.name == "sqlite":
        event.listen(db_engine, "connect", enable_sqlite_foreign_keys)
    return db_engine


# The engine owns the connection pool. settings.DATABASE_URL is usually
# postgresql://user:password@host:port/database_name, from the
# environment or a .env file. Tests call create_db_engine with their
# own URL and do not reuse this engine.
engine = create_db_engine(settings.DATABASE_URL)

# SessionLocal is a factory. Each call starts one conversation with the
# database. autocommit and autoflush stay off so the repository decides
# when to commit.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base is the parent of every table class. SQLAlchemy 2 exposes
# declarative_base from sqlalchemy.orm. A subclass becomes a table.
Base = declarative_base()


def get_db():
    """Give one request its own session, then close that session.

    FastAPI runs this dependency per request. ``yield`` hands the
    session to the endpoint. ``finally`` runs even when the endpoint
    raises, so the connection returns to the pool.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
