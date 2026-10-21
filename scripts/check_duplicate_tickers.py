"""Report tickers that are already stored more than once.

Revision 0002 adds a unique index on ``companies.ticker``. Creating
that index fails, with a different message on SQLite and PostgreSQL,
when two rows share a ticker. This check runs first, inside the
migration and as a command, and names the tickers. It does not
delete or merge rows.

The comparison is ``UPPER(TRIM(ticker))``, the same trim and
uppercase the application uses before it stores a ticker. ``aapl``
and ``AAPL `` are one collision. The stored text is reported as it
is. The rows are not rewritten.

The database URL is an argument. The script does not read
``settings.DATABASE_URL``, so it does not open the application
database unless that URL is passed in on purpose.

    python -m scripts.check_duplicate_tickers sqlite:///path.db
"""

import sys

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError


class CompaniesTableMissing(RuntimeError):
    """The database has no ``companies`` table to check."""

    def __init__(self):
        super().__init__("companies table is not in this database")


class DuplicateTickersError(RuntimeError):
    """``companies.ticker`` already has repeated values.

    The migration raises this before it creates the unique index, so
    the rows stay as they are.
    """


def duplicate_tickers(connection):
    """Return tickers that collide after ``UPPER(TRIM(ticker))``.

    Each item is ``(normalized, [(stored_ticker, count), ...])``.
    ``stored_ticker`` is the text in the table, including case and
    spaces. ``aapl`` and ``AAPL `` are one collision because the
    application stores a ticker with ``strip`` and ``upper``. The
    rows are not rewritten.
    """
    inspector = inspect(connection)
    if "companies" not in inspector.get_table_names():
        raise CompaniesTableMissing()
    # Group by the normalized form and by the stored text. The inner
    # count is rows, so one ``aapl`` and one ``AAPL `` are a collision
    # even though each stored spelling appears once.
    rows = connection.execute(
        text(
            "SELECT UPPER(TRIM(ticker)) AS normalized, ticker, "
            "COUNT(*) AS n FROM companies "
            "GROUP BY UPPER(TRIM(ticker)), ticker "
            "HAVING UPPER(TRIM(ticker)) IN ("
            "SELECT UPPER(TRIM(ticker)) FROM companies "
            "GROUP BY UPPER(TRIM(ticker)) HAVING COUNT(*) > 1"
            ") "
            "ORDER BY UPPER(TRIM(ticker)), ticker"
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


def main(argv=None):
    """Exit 0 when tickers are unique, 1 on duplicates or a read error.

    Exit 2 is usage, or a database that has no ``companies`` table.
    A connection failure is exit 1 and one line on stderr, with no
    traceback.
    """
    arguments = list(sys.argv if argv is None else argv)
    if len(arguments) != 2 or not str(arguments[1]).strip():
        print(
            "Usage: python -m scripts.check_duplicate_tickers DATABASE_URL",
            file=sys.stderr,
        )
        return 2
    engine = create_engine(arguments[1])
    try:
        with engine.connect() as connection:
            found = duplicate_tickers(connection)
    except CompaniesTableMissing as error:
        print(str(error), file=sys.stderr)
        return 2
    except OperationalError:
        print(
            "Could not read companies: the database is unreachable "
            "or the table is missing.",
            file=sys.stderr,
        )
        return 1
    finally:
        engine.dispose()
    if found:
        print(format_duplicate_tickers(found), file=sys.stderr)
        return 1
    print("No duplicate tickers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
