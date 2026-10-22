"""Apply the company revisions to a connection that already has companies.

The application engine is not used. Callers pass the connection that
should change, including a PostgreSQL connection whose search_path
points at a scratch schema.
"""

import warnings
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.exc import SAWarning

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


# SQLite cannot reflect an index on upper(ticker). These two messages
# are the only ones hidden, and only while a block below reflects
# companies. A different warning still surfaces. The catalog assert
# reads sqlite_master or pg_indexes, because an empty autogenerate
# diff stays empty when this index is missing.
_REFLECTION_SKIPPED = (
    "Skipped unsupported reflection of "
    "expression-based index uq_companies_ticker"
)
_AUTOGENERATE_SKIPPED = (
    "autogenerate skipping metadata-specified "
    "expression-based index 'uq_companies_ticker'"
)


@contextmanager
def without_unreflectable_ticker_index():
    """Ignore the SQLite reflection warning for ``uq_companies_ticker``.

    ``warnings.filterwarnings`` matches the start of the message.
    The SQLAlchemy warning is an ``SAWarning``. Alembic's autogenerate
    warning is a ``UserWarning`` and names the same index. Nothing
    else is filtered. This is not a pytest-wide filter.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=_REFLECTION_SKIPPED,
            category=SAWarning,
        )
        warnings.filterwarnings(
            "ignore",
            message=_AUTOGENERATE_SKIPPED,
            category=UserWarning,
        )
        yield


def metadata_diff(connection):
    """Operations autogenerate would apply to match ``Base.metadata``.

    An empty list means the live schema and the models agree.
    On SQLite that list does not include ``uq_companies_ticker``.
    ``assert_upper_ticker_index_recorded`` is the check for the index.
    """
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from app.core.database import Base

    with without_unreflectable_ticker_index():
        context = MigrationContext.configure(connection)
        return compare_metadata(context, Base.metadata)


def assert_upper_ticker_index_recorded(connection):
    """``uq_companies_ticker`` is unique and uses ``upper(ticker)``.

    SQLite reads ``sqlite_master``. PostgreSQL reads ``pg_indexes``.
    Both are the database catalog, not SQLAlchemy's inspector.
    Reflection skips this index on SQLite, so autogenerate cannot
    report it missing.
    """
    if connection.dialect.name == "sqlite":
        sql = connection.execute(
            text(
                "SELECT sql FROM sqlite_master "
                "WHERE type = 'index' AND name = 'uq_companies_ticker'"
            )
        ).scalar()
        assert sql, "uq_companies_ticker is missing from sqlite_master"
        compact = "".join(sql.split()).lower()
        assert "unique" in compact
        assert "upper(ticker)" in compact
        return
    indexdef = connection.execute(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE schemaname = current_schema() "
            "AND tablename = 'companies' "
            "AND indexname = 'uq_companies_ticker'"
        )
    ).scalar()
    assert indexdef, "uq_companies_ticker is missing from pg_indexes"
    folded = "".join(indexdef.split()).lower()
    assert "unique" in folded
    assert "upper(" in folded
    assert "ticker" in folded


def assert_plain_ticker_index_recorded(connection):
    """``ix_companies_ticker`` is a non-unique index on ``ticker``.

    The catalog is ``sqlite_master`` or ``pg_indexes``. The index
    is not unique. Uniqueness stays on ``uq_companies_ticker``.
    """
    if connection.dialect.name == "sqlite":
        sql = connection.execute(
            text(
                "SELECT sql FROM sqlite_master "
                "WHERE type = 'index' AND name = 'ix_companies_ticker'"
            )
        ).scalar()
        assert sql, "ix_companies_ticker is missing from sqlite_master"
        compact = "".join(sql.split()).lower()
        assert "createuniqueindex" not in compact
        assert "(ticker)" in compact
        return
    indexdef = connection.execute(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE schemaname = current_schema() "
            "AND tablename = 'companies' "
            "AND indexname = 'ix_companies_ticker'"
        )
    ).scalar()
    assert indexdef, "ix_companies_ticker is missing from pg_indexes"
    folded = "".join(indexdef.split()).lower()
    assert "createuniqueindex" not in folded
    assert "(ticker)" in folded


def assert_empty_metadata_diff(connection):
    """Autogenerate is empty and both ticker indexes are recorded."""
    assert metadata_diff(connection) == []
    assert_upper_ticker_index_recorded(connection)
    assert_plain_ticker_index_recorded(connection)


def unique_constraint_names(connection):
    """Names of unique constraints on ``companies``.

    The SQLite inspector warns while it skips the expression index.
    That warning is ignored here. The names themselves are unchanged.
    """
    with without_unreflectable_ticker_index():
        return {
            item["name"]
            for item in inspect(connection).get_unique_constraints("companies")
        }


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
    with without_unreflectable_ticker_index():
        reflected = inspect(connection).get_indexes("companies")
    for index in reflected:
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
    with without_unreflectable_ticker_index():
        inspector = inspect(connection)
        reflected_indexes = inspector.get_indexes("companies")
        reflected_constraints = inspector.get_unique_constraints("companies")
    indexes = tuple(
        sorted(
            (
                index["name"],
                bool(index["unique"]),
                tuple(index["column_names"]),
            )
            for index in reflected_indexes
            if index["column_names"] == ["ticker"]
        )
    )
    constraints = tuple(
        sorted(
            (item["name"], tuple(item["column_names"] or []))
            for item in reflected_constraints
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
    with without_unreflectable_ticker_index():
        inspector = inspect(connection)
        reflected_indexes = inspector.get_indexes("companies")
        reflected_constraints = inspector.get_unique_constraints("companies")
    indexes = tuple(
        sorted(
            (
                index["name"],
                bool(index["unique"]),
                tuple(index["column_names"]),
            )
            for index in reflected_indexes
            if index["column_names"] == ["isin"]
        )
    )
    constraints = tuple(
        sorted(
            (item["name"], tuple(item["column_names"] or []))
            for item in reflected_constraints
            if item.get("column_names") == ["isin"]
        )
    )
    return indexes, constraints
