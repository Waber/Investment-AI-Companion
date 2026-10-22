"""unique index on companies.ticker

Revision ID: 0003
Revises: 0002
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

It then leaves one unique index, ``uq_companies_ticker``, created
with ``op.create_index``. That is not a ``batch_alter_table``
rebuild of ``companies``. With foreign keys on, SQLite would drop
``companies`` during a rebuild and cascade-delete child rows such
as ``price_bars``. A unique index does not rebuild the table.
PostgreSQL uses that same index so the model, SQLite, and
PostgreSQL agree. ``uq_companies_isin`` is the same kind of index.

Money columns stay ``Float``. ``price_bars`` already stores prices
as ``Float``. This revision does not change them to ``Numeric``.

The preflight SQL is copied into this file. A migration must stay
frozen: importing ``scripts`` would change this revision when the
command changes. ``scripts.check_duplicate_tickers`` repeats the
same SQL for the operator command. ``DuplicateTickersError`` here
is not that module's class.
"""

import warnings
from contextlib import contextmanager

from sqlalchemy import inspect, text
from sqlalchemy.exc import SAWarning

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


class DuplicateTickersError(RuntimeError):
    """``companies.ticker`` already has repeated values.

    Raised before the unique index is created, so the rows stay as
    they are. This class lives in the revision so the file does not
    import the command.
    """


def _normalized_ticker_sql(dialect_name):
    """SQL for the ticker key this revision compares.

    ``TRIM(ticker)`` removes spaces only. SQLite's two-argument
    ``TRIM`` and PostgreSQL ``BTRIM`` remove every character in the
    set, so a tab, CR, or LF is the same kind of edge as a space.
    ``chr`` and ``char`` are the two dialects' names for the same
    function. These strings are literals. They are not imported.
    """
    if dialect_name == "postgresql":
        removed = "chr(9) || chr(10) || chr(13) || chr(32)"
        return f"UPPER(BTRIM(ticker, {removed}))"
    removed = "char(9) || char(10) || char(13) || char(32)"
    return f"UPPER(TRIM(ticker, {removed}))"


def _duplicate_tickers(connection):
    """Tickers that collide after trim and uppercase.

    Each item is ``(normalized, [(stored_ticker, count), ...])``.
    The stored text is not rewritten.
    """
    if "companies" not in inspect(connection).get_table_names():
        raise RuntimeError("companies table is not in this database")
    key = _normalized_ticker_sql(connection.dialect.name)
    rows = connection.execute(
        text(
            f"SELECT {key} AS normalized, ticker, "
            "COUNT(*) AS n FROM companies "
            f"GROUP BY {key}, ticker "
            f"HAVING {key} IN ("
            f"SELECT {key} FROM companies "
            f"GROUP BY {key} HAVING COUNT(*) > 1"
            f") "
            f"ORDER BY {key}, ticker"
        )
    )
    grouped = {}
    for normalized, stored, count in rows:
        grouped.setdefault(normalized, []).append((stored, int(count)))
    found = []
    for normalized in sorted(grouped, key=lambda value: value or ""):
        variants = sorted(grouped[normalized], key=lambda item: item[0])
        found.append((normalized, variants))
    return found


def _format_duplicate_tickers(found):
    """One sentence. ``found`` is not empty. Rows are not rewritten."""
    parts = []
    for normalized, variants in found:
        stored = ", ".join(
            f"{ticker!r} ({count} {'row' if count == 1 else 'rows'})"
            for ticker, count in variants
        )
        parts.append(f"{normalized} is stored as {stored}")
    listed = "; ".join(parts)
    return (
        "companies.ticker is not unique after trim and uppercase. "
        "These stored rows collide, and they were not rewritten: "
        + listed
        + ". The upgrade did not change those rows. Merge or remove the "
        "extras, then run the upgrade again."
    )


def _ticker_only(column_names):
    return list(column_names or []) == ["ticker"]


@contextmanager
def _quiet_expression_index():
    """Hide SQLite's skip warning for ``uq_companies_ticker``.

    Revision 0007 may already have replaced that index with
    ``upper(ticker)`` before a later downgrade runs this file.
    SQLAlchemy 2.0.23 cannot reflect an expression index and warns.
    The filter matches that one message. It is not a blanket ignore.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=(
                "Skipped unsupported reflection of "
                "expression-based index uq_companies_ticker"
            ),
            category=SAWarning,
        )
        yield


def _reflected_indexes(bind):
    with _quiet_expression_index():
        return inspect(bind).get_indexes("companies")


def _reflected_unique_constraints(bind):
    with _quiet_expression_index():
        return inspect(bind).get_unique_constraints("companies")


def upgrade() -> None:
    bind = op.get_bind()
    # Before any index change. The check trims spaces, tabs, CR, and
    # LF, then uppercases, matching the application's strip and
    # uppercase. Naming the stored rows here leaves the table
    # untouched by this revision.
    found = _duplicate_tickers(bind)
    if found:
        raise DuplicateTickersError(_format_duplicate_tickers(found))
    _use_named_ticker_index(bind)


def _use_named_ticker_index(bind) -> None:
    names = {index["name"] for index in _reflected_indexes(bind)}
    if "uq_companies_ticker" not in names:
        op.create_index(
            "uq_companies_ticker", "companies", ["ticker"], unique=True
        )
    # The old create_all index. A PostgreSQL UNIQUE constraint is also
    # listed as an index, with duplicates_constraint set. Dropping it
    # here and again as a constraint would fail, so those are skipped.
    for index in _reflected_indexes(bind):
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
        # it would rebuild the table and cascade-delete price_bars.
        # The new unique index is enough.
        return
    for item in _reflected_unique_constraints(bind):
        if _ticker_only(item.get("column_names")) and item.get("name"):
            op.drop_constraint(item["name"], "companies", type_="unique")


def downgrade() -> None:
    bind = op.get_bind()
    names = {index["name"] for index in _reflected_indexes(bind)}
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
    for index in _reflected_indexes(bind):
        if index.get("unique") and _ticker_only(index.get("column_names")):
            return True
    for item in _reflected_unique_constraints(bind):
        if _ticker_only(item.get("column_names")):
            return True
    return False
