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


# The URL comes from settings (environment or .env). Tests that need a
# private database call create_db_engine with their own URL instead of
# reusing this engine.
engine = create_db_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# SQLAlchemy 2 exposes declarative_base from sqlalchemy.orm.
Base = declarative_base()


def get_db():
    """Yield one session for a request and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
