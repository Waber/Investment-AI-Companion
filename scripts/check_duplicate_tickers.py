"""Report tickers that are already stored more than once.

Revision 0002 adds a unique index on ``companies.ticker``. Creating
that index fails, with a different message on SQLite and PostgreSQL,
when two rows share a ticker. This check runs first, inside the
migration and as a command, and names the tickers. It does not
delete or merge rows.

The comparison is uppercase after removing spaces, tabs, carriage
returns, and line feeds from both ends. That is the trim and
uppercase the application applies before it stores a ticker.
``aapl``, ``AAPL ``, and ``AAPL`` with a trailing tab are one
collision. The stored text is reported as it is. The rows are not
rewritten.

Pass the database URL in the ``DATABASE_URL`` environment variable.
An argument overrides that variable, but the argument can show up
in ``ps`` and in shell history.

    DATABASE_URL=sqlite:///path.db python -m scripts.check_duplicate_tickers
"""

import os
import sys

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import ArgumentError, SQLAlchemyError


class CompaniesTableMissing(RuntimeError):
    """The database has no ``companies`` table to check."""

    def __init__(self):
        super().__init__("companies table is not in this database")


class DuplicateTickersError(RuntimeError):
    """``companies.ticker`` already has repeated values.

    The migration raises this before it creates the unique index, so
    the rows stay as they are.
    """


def _normalized_ticker_sql(dialect_name):
    """SQL expression for the ticker key this check compares.

    ``TRIM(ticker)`` removes spaces only. SQLite's two-argument
    ``TRIM`` and PostgreSQL ``BTRIM`` remove every character in the
    set, so a tab, CR, or LF is the same kind of edge as a space.
    ``chr`` and ``char`` are the two dialects' names for the same
    function. The application rejects those controls before
    ``strip``, and ``strip`` would remove a tab, CR, or LF that
    remained, so a row written by the API does not need this. A row
    written with SQL can still have them.
    """
    if dialect_name == "postgresql":
        removed = "chr(9) || chr(10) || chr(13) || chr(32)"
        return f"UPPER(BTRIM(ticker, {removed}))"
    removed = "char(9) || char(10) || char(13) || char(32)"
    return f"UPPER(TRIM(ticker, {removed}))"


def duplicate_tickers(connection):
    """Return tickers that collide after trim and uppercase.

    Each item is ``(normalized, [(stored_ticker, count), ...])``.
    ``stored_ticker`` is the text in the table, including case and
    surrounding whitespace. Spaces, tabs, carriage returns, and line
    feeds are removed from both ends before the comparison. ``aapl``
    and ``AAPL `` are one collision because the application stores a
    ticker with ``strip`` and ``upper``. The rows are not rewritten.
    """
    inspector = inspect(connection)
    if "companies" not in inspector.get_table_names():
        raise CompaniesTableMissing()
    # Group by the normalized form and by the stored text. The inner
    # count is rows, so one ``aapl`` and one ``AAPL `` are a collision
    # even though each stored spelling appears once.
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
    for normalized in sorted(grouped, key=_sort_key):
        variants = sorted(grouped[normalized], key=lambda item: item[0])
        found.append((normalized, variants))
    return found


def _sort_key(value):
    """Keep a missing ticker at the start of a stable ordering."""
    if value is None:
        return ""
    return value


def _stored_phrase(stored, count):
    noun = "row" if count == 1 else "rows"
    return f"{stored!r} ({count} {noun})"


def format_duplicate_tickers(found):
    """One sentence an operator can act on. ``found`` is not empty.

    The stored ticker is quoted, so a trailing space stays visible.
    The sentence names the rows. It does not describe a rewrite.
    """
    parts = []
    for normalized, variants in found:
        stored = ", ".join(
            _stored_phrase(ticker, count) for ticker, count in variants
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


_USAGE = (
    "Usage: python -m scripts.check_duplicate_tickers [DATABASE_URL]\n"
    "Set DATABASE_URL instead of passing the URL as an argument. "
    "An argument can appear in ps and in shell history."
)
_URL_MESSAGE = "Could not read companies: the database URL is not valid."
_READ_MESSAGE = (
    "Could not read companies: the database is unreachable "
    "or the table is missing."
)


def _chosen_url(arguments):
    """The argument when one was passed, otherwise ``DATABASE_URL``.

    A blank argument is treated as absent so the environment variable
    can still be used. ``None`` means the operator gave neither.
    """
    if len(arguments) > 2:
        return None
    if len(arguments) == 2 and str(arguments[1]).strip():
        return str(arguments[1])
    env = os.environ.get("DATABASE_URL", "")
    if str(env).strip():
        return str(env)
    return None


def main(argv=None):
    """Exit 0 when tickers are unique, 1 on duplicates or a read error.

    Exit 2 is usage, or a database that has no ``companies`` table.
    A bad URL or a connection failure is exit 1 and one fixed line on
    stderr. The line does not include the URL or the driver text, and
    the return happens after the handler so nothing is chained.
    """
    arguments = list(sys.argv if argv is None else argv)
    url = _chosen_url(arguments)
    if url is None:
        print(_USAGE, file=sys.stderr)
        return 2
    found = None
    failure = None
    try:
        engine = create_engine(url)
        try:
            with engine.connect() as connection:
                found = duplicate_tickers(connection)
        finally:
            engine.dispose()
    except ArgumentError:
        failure = (_URL_MESSAGE, 1)
    except SQLAlchemyError:
        failure = (_READ_MESSAGE, 1)
    except CompaniesTableMissing as error:
        failure = (str(error), 2)
    if failure is not None:
        print(failure[0], file=sys.stderr)
        return failure[1]
    if found:
        print(format_duplicate_tickers(found), file=sys.stderr)
        return 1
    print("No duplicate tickers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
