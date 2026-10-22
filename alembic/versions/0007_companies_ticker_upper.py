"""unique index on upper(companies.ticker)

Revision ID: 0007
Revises: 0005
Create Date: 2026-10-22

Revision 0003 made ``ticker`` unique as stored. The application
uppercases a ticker before it writes, so the API cannot store
``aapl`` next to ``AAPL``. A raw ``INSERT`` still can, because the
index compares the column and not ``upper(ticker)``.

This revision stops when ``upper(ticker)`` is already stored more
than once. The message names the stored text. The rows are not
rewritten. It then replaces ``uq_companies_ticker`` with a unique
index on ``upper(ticker)``. The name stays ``uq_companies_ticker``.

``uq_company_name_ticker`` is the pair constraint from the old
model. Ticker uniqueness already makes that pair unique, and the
name may be shared (``BRK.A`` and ``BRK.B``), so the pair is
redundant. This revision drops it when it is present. A database
built only by the earlier revisions never had it. Downgrade puts
it back so the table matches that old model.

On SQLite the pair constraint is part of ``CREATE TABLE``. Dropping
it copies ``companies`` and only ``companies``. Foreign keys are
turned off for that copy. With them on, ``DROP TABLE companies``
either fails (``financial_metrics``) or cascade-deletes
``price_bars``. ``autocommit_block`` commits Alembic's transaction
and leaves the driver outside a transaction, which is the only
time ``PRAGMA foreign_keys`` is honored. The copy is then one
explicit ``BEGIN`` / ``COMMIT``. A failure rolls that back.
Foreign keys are restored afterward, and Alembic opens a new
transaction for the version row. PostgreSQL drops the constraint
in place.

``ix_companies_ticker`` is a non-unique index on the column.
Lookups compare ``ticker`` to a value, and the unique index is
on ``upper(ticker)``, which those comparisons do not use.
Downgrade drops the plain index. The unique column index from
the previous revision keeps the name ``uq_companies_ticker``.

``down_revision`` is ``0005`` so this branch has one Alembic head.
Revision ``0006`` is the price-bar numeric migration and is not on
this branch. Lengths and SQL fragments in this file are literals.
This file does not import application or script code.

SQLite's ``upper`` folds ASCII letters. Tickers stored by the
application are ASCII. PostgreSQL's ``upper`` is used on that
dialect, and the reflected expression is ``upper(ticker::text)``.
"""

import re
import warnings
from contextlib import contextmanager

import sqlalchemy as sa
from sqlalchemy.exc import SAWarning

from alembic import op

revision = "0007"
down_revision = "0005"
branch_labels = None
depends_on = None

_TICKER_INDEX = "uq_companies_ticker"
_PLAIN_TICKER_INDEX = "ix_companies_ticker"
_NAME_TICKER = "uq_company_name_ticker"
_CONSTRAINT_SQL = "CONSTRAINT uq_company_name_ticker UNIQUE (name, ticker)"
_COMPANIES_NEW = "companies__new"


class UpperTickerCollision(RuntimeError):
    """``upper(ticker)`` is already stored more than once.

    Raised before any index change, so the rows stay as they are.
    """


def _upper_collisions(connection):
    """Rows that collide on ``upper(ticker)``.

    Each item is ``(normalized, [(stored_ticker, count), ...])``.
    The comparison is ``upper(ticker)`` with no trim. That is the
    expression the unique index uses. A trailing space does not
    collide with the same letters. The stored text is not rewritten.
    """
    if "companies" not in sa.inspect(connection).get_table_names():
        raise RuntimeError("companies table is not in this database")
    key = "upper(ticker)"
    rows = connection.execute(
        sa.text(
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
        variants = sorted(grouped[normalized], key=lambda item: item[0] or "")
        found.append((normalized, variants))
    return found


def _format_upper_collisions(found):
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
        "companies.ticker is not unique under upper(ticker). "
        "These stored rows collide, and they were not rewritten: "
        + listed
        + ". The upgrade did not change those rows. Merge or remove the "
        "extras, then run the upgrade again."
    )


@contextmanager
def _quiet_expression_index():
    """Hide SQLite's skip warning for ``uq_companies_ticker``.

    The index expression is ``upper(ticker)``. SQLAlchemy 2.0.23
    cannot reflect that and emits one ``SAWarning`` whose text names
    this index. The filter matches that message only, and only while
    the constraint names are read. The tests check the index in
    ``sqlite_master`` or ``pg_indexes`` instead.
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


def _constraint_names(bind):
    with _quiet_expression_index():
        inspector = sa.inspect(bind)
        found = inspector.get_unique_constraints("companies")
    return {item["name"] for item in found}


def _sqlite_rows(bind, statement, parameters=None):
    return bind.execute(sa.text(statement), parameters or {})


def _sqlite_table_sql(bind):
    sql = _sqlite_rows(
        bind,
        "SELECT sql FROM sqlite_master "
        "WHERE type = 'table' AND name = 'companies'",
    ).scalar()
    if not sql:
        raise RuntimeError("companies table is not in this database")
    return sql


def _sqlite_index_sqls(bind):
    rows = _sqlite_rows(
        bind,
        "SELECT sql FROM sqlite_master "
        "WHERE type = 'index' AND tbl_name = 'companies' "
        "AND sql IS NOT NULL "
        "ORDER BY name",
    )
    return [row[0] for row in rows]


def _index_sql(bind, name):
    if bind.dialect.name != "sqlite":
        return None
    return _sqlite_rows(
        bind,
        "SELECT sql FROM sqlite_master "
        "WHERE type = 'index' AND name = :name",
        {"name": name},
    ).scalar()


def _ticker_index_is_upper(bind):
    """True when ``uq_companies_ticker`` is already on ``upper``."""
    if bind.dialect.name == "sqlite":
        sql = _index_sql(bind, _TICKER_INDEX)
        if not sql:
            return False
        compact = "".join(sql.split()).lower()
        return "upper(ticker)" in compact
    inspector = sa.inspect(bind)
    for index in inspector.get_indexes("companies"):
        if index["name"] != _TICKER_INDEX:
            continue
        expressions = " ".join(index.get("expressions") or []).lower()
        return "upper" in expressions
    return False


def _index_exists(bind, name):
    if bind.dialect.name == "sqlite":
        return _index_sql(bind, name) is not None
    inspector = sa.inspect(bind)
    return any(
        index["name"] == name for index in inspector.get_indexes("companies")
    )


def _without_name_ticker_constraint(ddl):
    """Table SQL with the pair constraint removed. Other clauses stay.

    SQLite may store the name in double quotes after a table is
    renamed. The pattern accepts that form.
    """
    if _NAME_TICKER not in ddl:
        return ddl
    pattern = re.compile(
        r"\s*CONSTRAINT\s+\"?uq_company_name_ticker\"?\s+"
        r"UNIQUE\s*\(\s*\"?name\"?\s*,\s*\"?ticker\"?\s*\)\s*,?",
        re.IGNORECASE,
    )
    updated = pattern.sub("", ddl)
    updated = re.sub(r",(\s*)\)", r"\1)", updated)
    updated = re.sub(r",(\s*),", r",\1", updated)
    if _NAME_TICKER in updated:
        raise RuntimeError(
            "Could not remove uq_company_name_ticker from companies."
        )
    return updated


def _with_name_ticker_constraint(ddl):
    """Table SQL with the pair constraint added before the closing paren."""
    if _NAME_TICKER in ddl:
        return ddl
    stripped = ddl.rstrip()
    if not stripped.endswith(")"):
        raise RuntimeError("companies table SQL does not end with ')'.")
    return stripped[:-1] + ", " + _CONSTRAINT_SQL + ")"


def _as_new_table(ddl):
    """Point the copied ``CREATE TABLE`` at ``companies__new``.

    ``ALTER TABLE ... RENAME`` makes SQLite store the name as
    ``"companies"``. A second copy has to recognize both spellings.
    """
    updated, count = re.subn(
        r'^CREATE TABLE\s+"?companies"?\s*\(',
        "CREATE TABLE " + _COMPANIES_NEW + " (",
        ddl.strip(),
        count=1,
        flags=re.IGNORECASE,
    )
    if count != 1:
        raise RuntimeError("Could not rename the companies table SQL.")
    return updated


def _pragma(raw, statement):
    """Run one SQLite pragma on the DB-API connection.

    The SQLAlchemy connection is not used. ``execute`` on that
    connection would start a transaction, and ``PRAGMA foreign_keys``
    is ignored once a transaction is open.
    """
    cursor = raw.cursor()
    try:
        cursor.execute(statement)
        row = cursor.fetchone()
        return None if row is None else row[0]
    finally:
        cursor.close()


def _dbapi_execute(raw, statement):
    cursor = raw.cursor()
    try:
        cursor.execute(statement)
    finally:
        cursor.close()


def _with_foreign_keys_off(work):
    """Run ``work`` while SQLite is not enforcing foreign keys.

    ``PRAGMA foreign_keys`` is ignored inside a transaction.
    :meth:`alembic.runtime.migration.MigrationContext.autocommit_block`
    commits the migration transaction and sets the driver to
    ``AUTOCOMMIT`` (SQLite isolation level ``None``), so the pragma
    takes effect. The copy then uses its own ``BEGIN`` and
    ``COMMIT``. A failure runs ``ROLLBACK`` and the exception
    propagates, so Alembic does not advance the version. The block
    opens a new transaction on the way out. That transaction is
    where the version row is written when the migration succeeds.

    ``work`` receives the connection from inside the block. The
    connection captured before the block is a different object.

    When the caller already had a transaction open, Alembic does
    not start its own, and ``autocommit_block`` refuses to run
    (it only commits the transaction it started). That caller
    transaction is committed first so the pragma can change.
    This function does not read or assign ``context._transaction``.
    Alembic still commits the version row when it owns the
    transaction: ``autocommit_block`` opens a new one on the way
    out, and that is the transaction the version update uses.
    """
    context = op.get_context()
    bind = op.get_bind()
    if bind.in_transaction() and context._in_external_transaction:
        bind.commit()
    with context.autocommit_block():
        bind = op.get_bind()
        raw = bind.connection.dbapi_connection
        previous = _pragma(raw, "PRAGMA foreign_keys")
        open_copy = False
        try:
            _pragma(raw, "PRAGMA foreign_keys=OFF")
            turned_off = _pragma(raw, "PRAGMA foreign_keys")
            if turned_off not in (0, "0"):
                raise RuntimeError(
                    "SQLite foreign keys stayed on, so companies "
                    "was not rebuilt."
                )
            _dbapi_execute(raw, "BEGIN")
            open_copy = True
            try:
                work(bind)
            except Exception:
                _dbapi_execute(raw, "ROLLBACK")
                open_copy = False
                raise
            else:
                _dbapi_execute(raw, "COMMIT")
                open_copy = False
        finally:
            if open_copy:
                _dbapi_execute(raw, "ROLLBACK")
            state = "ON" if previous in (1, "1") else "OFF"
            _pragma(raw, "PRAGMA foreign_keys=" + state)


def _company_child_tables(bind):
    """Tables with a foreign key to ``companies``.

    The copy does not rebuild these tables. ``PRAGMA
    foreign_key_check`` is run on each of them. ``companies__new``
    is the temporary copy and is not a child.
    """
    inspector = sa.inspect(bind)
    children = []
    for name in inspector.get_table_names():
        if name == "companies" or name.startswith("companies__"):
            continue
        for foreign_key in inspector.get_foreign_keys(name):
            if foreign_key.get("referred_table") == "companies":
                children.append(name)
                break
    return children


def _foreign_key_violations(bind, tables):
    """Rows ``PRAGMA foreign_key_check`` reports for ``tables``.

    Each item is ``(table, rowid, parent, fkid)``. The pragma
    reports violations whether or not foreign keys are enforced.
    """
    found = set()
    for table in tables:
        rows = bind.execute(
            sa.text('PRAGMA foreign_key_check("' + table + '")')
        )
        for row in rows:
            found.add(tuple(row))
    return found


def _format_new_fk_violations(rows):
    listed = ", ".join(
        f"{table} rowid {rowid} -> {parent}"
        for table, rowid, parent, _fkid in sorted(
            rows, key=lambda item: (str(item[0]), item[1] or 0)
        )
    )
    return (
        "Rebuilding companies introduced foreign-key violations "
        "that were not in the table before the copy: "
        + listed
        + ". The copy was rolled back."
    )


def _rebuild_sqlite_companies(bind, transform):
    """Copy ``companies`` through ``transform`` and recreate its indexes.

    Only this table is copied. Child tables are not dropped. Foreign
    keys are off for the copy so their rows stay. After the rename,
    ``PRAGMA foreign_key_check`` must not report a violation that
    was not already there. An orphan that existed before the copy
    does not stop the upgrade. A parent the copy dropped does.
    """
    ddl = _sqlite_table_sql(bind)
    indexes = _sqlite_index_sqls(bind)
    children = _company_child_tables(bind)
    new_ddl = _as_new_table(transform(ddl))

    def copy(active):
        before = _foreign_key_violations(active, children)
        active.execute(sa.text("DROP TABLE IF EXISTS " + _COMPANIES_NEW))
        active.execute(sa.text(new_ddl))
        active.execute(
            sa.text(
                "INSERT INTO " + _COMPANIES_NEW + " SELECT * FROM companies"
            )
        )
        active.execute(sa.text("DROP TABLE companies"))
        active.execute(
            sa.text("ALTER TABLE " + _COMPANIES_NEW + " RENAME TO companies")
        )
        introduced = _foreign_key_violations(active, children) - before
        if introduced:
            raise RuntimeError(_format_new_fk_violations(introduced))
        for statement in indexes:
            active.execute(sa.text(statement))

    _with_foreign_keys_off(copy)


def _drop_name_ticker_constraint(bind):
    if _NAME_TICKER not in _constraint_names(bind):
        return
    if bind.dialect.name == "sqlite":
        _rebuild_sqlite_companies(bind, _without_name_ticker_constraint)
        return
    op.drop_constraint(_NAME_TICKER, "companies", type_="unique")


def _restore_name_ticker_constraint(bind):
    if _NAME_TICKER in _constraint_names(bind):
        return
    if bind.dialect.name == "sqlite":
        _rebuild_sqlite_companies(bind, _with_name_ticker_constraint)
        return
    op.create_unique_constraint(_NAME_TICKER, "companies", ["name", "ticker"])


def _ensure_plain_ticker_index(bind):
    """Non-unique index for ``WHERE ticker = ...``.

    The unique index is on ``upper(ticker)``. A comparison with the
    column itself does not use that index. This one does. It is not
    unique: uniqueness stays on ``uq_companies_ticker``.
    """
    if _index_exists(bind, _PLAIN_TICKER_INDEX):
        return
    op.create_index(_PLAIN_TICKER_INDEX, "companies", ["ticker"], unique=False)


def _drop_plain_ticker_index(bind):
    if _index_exists(bind, _PLAIN_TICKER_INDEX):
        op.drop_index(_PLAIN_TICKER_INDEX, table_name="companies")


def _replace_with_upper_index(bind):
    if _ticker_index_is_upper(bind):
        return
    if _index_exists(bind, _TICKER_INDEX):
        op.drop_index(_TICKER_INDEX, table_name="companies")
    op.create_index(
        _TICKER_INDEX,
        "companies",
        [sa.func.upper(sa.column("ticker"))],
        unique=True,
    )


def _restore_column_ticker_index(bind):
    if _ticker_index_is_upper(bind):
        op.drop_index(_TICKER_INDEX, table_name="companies")
    elif _index_exists(bind, _TICKER_INDEX):
        return
    op.create_index(_TICKER_INDEX, "companies", ["ticker"], unique=True)


def upgrade() -> None:
    bind = op.get_bind()
    # Before any index or constraint change. A collision leaves the
    # table and the Alembic version untouched.
    found = _upper_collisions(bind)
    if found:
        raise UpperTickerCollision(_format_upper_collisions(found))
    _drop_name_ticker_constraint(bind)
    _replace_with_upper_index(bind)
    _ensure_plain_ticker_index(bind)


def downgrade() -> None:
    bind = op.get_bind()
    # Drop the plain index before the companies copy. The copy
    # recreates every index that is present, and the previous
    # revision did not have this one. Revision 0003 may later
    # create a unique index with the same name.
    _drop_plain_ticker_index(bind)
    _restore_column_ticker_index(bind)
    _restore_name_ticker_constraint(bind)
