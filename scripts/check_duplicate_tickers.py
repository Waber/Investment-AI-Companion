"""Report tickers that are already stored more than once.

Revision 0002 adds a unique index on ``companies.ticker``. Creating
that index fails, with a different message on SQLite and PostgreSQL,
when two rows share a ticker. This check runs first, inside the
migration and as a command, and names the tickers. It does not
delete or merge rows.

The database URL is an argument. The script does not read
``settings.DATABASE_URL``, so it does not open the application
database unless that URL is passed in on purpose.

    python -m scripts.check_duplicate_tickers sqlite:///path.db
"""

import sys

from sqlalchemy import create_engine, inspect, text


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
    """Return ``(ticker, count)`` pairs stored more than once.

    The comparison is the raw ticker text. The API stores uppercase
    symbols, but a row written with SQL is reported as it is stored.
    """
    inspector = inspect(connection)
    if "companies" not in inspector.get_table_names():
        raise CompaniesTableMissing()
    rows = connection.execute(
        text(
            "SELECT ticker, COUNT(*) AS n FROM companies "
            "GROUP BY ticker HAVING COUNT(*) > 1 ORDER BY ticker"
        )
    )
    return [(row[0], int(row[1])) for row in rows]


def format_duplicate_tickers(found):
    """One sentence an operator can act on. ``found`` is not empty."""
    listed = ", ".join(f"{ticker} ({count} rows)" for ticker, count in found)
    return (
        "companies.ticker is not unique yet. These tickers are already "
        "stored more than once: "
        + listed
        + ". The upgrade did not change those rows. Merge or remove the "
        "extras, then run the upgrade again."
    )


def main(argv=None):
    """Exit 0 when tickers are unique, 1 when one repeats, 2 on usage."""
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
    finally:
        engine.dispose()
    if found:
        print(format_duplicate_tickers(found), file=sys.stderr)
        return 1
    print("No duplicate tickers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
