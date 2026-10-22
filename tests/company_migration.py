"""Apply the company revisions to a connection that already has companies.

The application engine is not used. Callers pass the connection that
should change, including a PostgreSQL connection whose search_path
points at a scratch schema.
"""

from pathlib import Path

from sqlalchemy import inspect, text

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[1]

# The shape of companies before instrument_type and isin existed.
# Integer ids are inserted by the test. PostgreSQL does not add a
# sequence for a plain INTEGER primary key, and SQLite does not need one.
LEGACY_COMPANIES = """
CREATE TABLE companies (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    ticker VARCHAR(20) NOT NULL UNIQUE,
    currency VARCHAR(3) DEFAULT 'USD'
)
"""
LEGACY_METRICS = """
CREATE TABLE financial_metrics (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies (id)
)
"""


def _config(connection):
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


def upgrade_head(connection):
    command.upgrade(_config(connection), "head")


def upgrade_to(connection, revision):
    """Upgrade this connection to one revision, for example ``0002``."""
    command.upgrade(_config(connection), revision)


def downgrade_base(connection):
    command.downgrade(_config(connection), "base")


def downgrade_to(connection, revision):
    """Downgrade this connection to one revision, for example ``0002``."""
    command.downgrade(_config(connection), revision)


def stamp(connection, revision):
    command.stamp(_config(connection), revision)


def metadata_diff(connection):
    """Operations autogenerate would apply to match ``Base.metadata``.

    An empty list means the live schema and the models agree.
    """
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from app.core.database import Base

    context = MigrationContext.configure(connection)
    return compare_metadata(context, Base.metadata)


def duplicate_ticker_message(error):
    """Text of revision 0003's own ``DuplicateTickersError``.

    The revision defines that class so it does not import the command.
    A second class with the same name lives in
    ``scripts.check_duplicate_tickers``. ``pytest.raises`` has to use
    ``RuntimeError``, then this check, or it will miss the revision's
    class.
    """
    assert error.__class__.__name__ == "DuplicateTickersError"
    return str(error)


def upper_ticker_index(connection):
    """The ``uq_companies_ticker`` index when it uses ``upper``.

    SQLite does not reflect an expression index, so the SQL is read
    from ``sqlite_master``. PostgreSQL reflects ``upper(ticker::text)``.
    ``None`` means the index is missing or it is still on the raw column.
    """
    if connection.dialect.name == "sqlite":
        sql = connection.execute(
            text(
                "SELECT sql FROM sqlite_master "
                "WHERE type = 'index' AND name = 'uq_companies_ticker'"
            )
        ).scalar()
        if sql is None:
            return None
        compact = "".join(sql.split()).lower()
        if "upper(ticker)" not in compact:
            return None
        return ("uq_companies_ticker", True, "upper(ticker)")
    for index in inspect(connection).get_indexes("companies"):
        if index["name"] != "uq_companies_ticker":
            continue
        expressions = tuple(index.get("expressions") or ())
        if not any("upper" in item.lower() for item in expressions):
            return None
        return (index["name"], bool(index["unique"]), expressions)
    return None


def ticker_uniqueness(connection):
    """Unique indexes and ticker-only unique constraints on companies.

    Indexes are the first tuple. Constraints are the second. A
    PostgreSQL unique constraint also appears as an index with
    ``duplicates_constraint`` set; that index is still listed here.
    """
    inspector = inspect(connection)
    indexes = tuple(
        sorted(
            (
                index["name"],
                bool(index["unique"]),
                tuple(index["column_names"]),
            )
            for index in inspector.get_indexes("companies")
            if index["column_names"] == ["ticker"]
        )
    )
    constraints = tuple(
        sorted(
            (item["name"], tuple(item["column_names"] or []))
            for item in inspector.get_unique_constraints("companies")
            if list(item.get("column_names") or []) == ["ticker"]
        )
    )
    return indexes, constraints


# create_all and revision 0001 both report one unique index named
# uq_companies_isin on (isin), and no unique constraint on isin.
EXPECTED_ISIN_UNIQUENESS = (
    (("uq_companies_isin", True, ("isin",)),),
    (),
)


def isin_uniqueness(connection):
    """How the live companies table keeps isin unique.

    Indexes are the first tuple. Unique constraints are the second.
    Callers compare a create_all database with a database that
    revision 0001 upgraded.
    """
    inspector = inspect(connection)
    indexes = tuple(
        sorted(
            (
                index["name"],
                bool(index["unique"]),
                tuple(index["column_names"]),
            )
            for index in inspector.get_indexes("companies")
            if index["column_names"] == ["isin"]
        )
    )
    constraints = tuple(
        sorted(
            (item["name"], tuple(item["column_names"] or []))
            for item in inspector.get_unique_constraints("companies")
            if item.get("column_names") == ["isin"]
        )
    )
    return indexes, constraints
