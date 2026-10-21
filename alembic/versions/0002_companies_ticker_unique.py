"""unique index on companies.ticker

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21

A database created by the current models used to enforce ticker
uniqueness with the index ``ix_companies_ticker``. An older
``CREATE TABLE`` used ``ticker UNIQUE``, which PostgreSQL names
``companies_ticker_key``. A database that only had the
``(name, ticker)`` constraint can hold one ticker twice when the
names differ. This revision stops in that case. It also stops
when two stored tickers match after trim and uppercase, such as
``aapl`` and ``AAPL ``. The trim also removes tabs, carriage
returns, and line feeds. The message quotes the stored text. The
rows are not rewritten.

It then leaves one unique index, ``uq_companies_ticker``. SQLite
cannot ``ADD CONSTRAINT`` while ``financial_metrics`` points at
``companies``: rebuilding the table drops ``companies`` and the
foreign key fails. A unique index does not rebuild the table.
PostgreSQL uses that same index so the model, SQLite, and
PostgreSQL agree. ``uq_companies_isin`` is the same kind of index.

Money columns stay ``Float``. Price tables are not in this schema,
so this revision does not choose ``Numeric`` for them.
"""

from sqlalchemy import inspect

from alembic import op
from scripts.check_duplicate_tickers import (
    DuplicateTickersError,
    duplicate_tickers,
    format_duplicate_tickers,
)

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _ticker_only(column_names):
    return list(column_names or []) == ["ticker"]


def upgrade() -> None:
    bind = op.get_bind()
    # Before any index change. The check uses UPPER(TRIM(ticker)),
    # matching the application's strip and uppercase. Naming the
    # stored rows here leaves the table untouched by this revision.
    found = duplicate_tickers(bind)
    if found:
        raise DuplicateTickersError(format_duplicate_tickers(found))
    _use_named_ticker_index(bind)


def _use_named_ticker_index(bind) -> None:
    names = {index["name"] for index in inspect(bind).get_indexes("companies")}
    if "uq_companies_ticker" not in names:
        op.create_index(
            "uq_companies_ticker", "companies", ["ticker"], unique=True
        )
    # The old create_all index. A PostgreSQL UNIQUE constraint is also
    # listed as an index, with duplicates_constraint set. Dropping it
    # here and again as a constraint would fail, so those are skipped.
    for index in inspect(bind).get_indexes("companies"):
        if (
            index["name"] != "uq_companies_ticker"
            and index.get("unique")
            and _ticker_only(index.get("column_names"))
            and not index.get("duplicates_constraint")
        ):
            op.drop_index(index["name"], table_name="companies")
    if bind.dialect.name == "sqlite":
        # The column-level UNIQUE in an old CREATE TABLE is an
        # autoindex. SQLite's inspector does not list it, and dropping
        # it would rebuild the table. The new unique index is enough.
        return
    for item in inspect(bind).get_unique_constraints("companies"):
        if _ticker_only(item.get("column_names")) and item.get("name"):
            op.drop_constraint(item["name"], "companies", type_="unique")


def downgrade() -> None:
    bind = op.get_bind()
    names = {index["name"] for index in inspect(bind).get_indexes("companies")}
    if "uq_companies_ticker" in names:
        op.drop_index("uq_companies_ticker", table_name="companies")
    # The previous revision's create_all index. Skip it when something
    # else still keeps ticker unique, so downgrade does not add a
    # second index.
    if _ticker_still_unique(bind):
        return
    op.create_index(
        "ix_companies_ticker", "companies", ["ticker"], unique=True
    )


def _ticker_still_unique(bind) -> bool:
    inspector = inspect(bind)
    for index in inspector.get_indexes("companies"):
        if index.get("unique") and _ticker_only(index.get("column_names")):
            return True
    for item in inspector.get_unique_constraints("companies"):
        if _ticker_only(item.get("column_names")):
            return True
    return False
