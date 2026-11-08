"""provenance columns for companies and financial metrics

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-08

Adds ``companies.is_synthetic`` (boolean, NOT NULL, server default
false), ``companies.source`` (string 64, NOT NULL, server default
``manual``), and ``financial_metrics.source`` (the same string).
There is no CHECK on ``source``. The application accepts ``manual``,
``demo``, and ``fixture``. A later value such as ``yahoo`` is a code
change, not another migration.

Rows whose ``description`` starts with ``[IAC-DEMO-`` are backfilled
as synthetic ``demo``. Every other company stays false and ``manual``.
A metric is ``demo`` when its company is synthetic, and ``manual``
otherwise. The legacy Alembic stub has no ``description`` column.
That database still upgrades: there is no prefix to read, so the
defaults stand. A ``create_all`` database already has the columns.
Adding them again would fail, so each add runs only when the column
is missing. The backfill still runs.

Downgrade drops the three columns. On SQLite that is
``ALTER TABLE ... DROP COLUMN`` (3.35 or newer; this project runs
3.45). It does not copy ``companies``. A batch copy would
``DROP TABLE companies`` while ``financial_metrics``, ``price_bars``,
``notes``, ``theses``, and ``watchlist_items`` point at it. With
foreign keys on, that drop fails or deletes those rows. PostgreSQL
drops the columns in place.

``down_revision`` is ``0008``, so Alembic keeps one head. This file
does not import application or script code.
"""

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def _column_names(bind, table):
    """Column names for ``table`` without reflecting expression indexes.

    SQLite cannot reflect ``uq_companies_ticker``. ``pragma_table_info``
    lists columns and does not look at that index. PostgreSQL reads
    ``information_schema`` for the current schema, so a test schema
    does not see another schema's columns.
    """
    if bind.dialect.name == "sqlite":
        rows = bind.execute(
            sa.text(f"SELECT name FROM pragma_table_info('{table}')")
        )
        return {row[0] for row in rows}
    rows = bind.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = :table"
        ),
        {"table": table},
    )
    return {row[0] for row in rows}


def _add_column_if_missing(bind, table, column):
    if column.name in _column_names(bind, table):
        return
    op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    _add_column_if_missing(
        bind,
        "companies",
        sa.Column(
            "is_synthetic",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    _add_column_if_missing(
        bind,
        "companies",
        sa.Column(
            "source",
            sa.String(length=64),
            nullable=False,
            server_default="manual",
        ),
    )
    _add_column_if_missing(
        bind,
        "financial_metrics",
        sa.Column(
            "source",
            sa.String(length=64),
            nullable=False,
            server_default="manual",
        ),
    )
    if "description" in _column_names(bind, "companies"):
        # ``LIKE`` is case-sensitive on PostgreSQL and not on SQLite.
        # ``substr`` plus ``=`` is case-sensitive on both. The prefix
        # is ten characters: ``[IAC-DEMO-``.
        op.execute(
            "UPDATE companies SET is_synthetic = TRUE, source = 'demo' "
            "WHERE substr(description, 1, 10) = '[IAC-DEMO-'"
        )
    op.execute(
        "UPDATE financial_metrics SET source = 'demo' "
        "WHERE company_id IN ("
        "SELECT id FROM companies WHERE is_synthetic)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # In-place DROP COLUMN. See the module docstring for why this
        # is not a batch copy of companies.
        op.execute("ALTER TABLE financial_metrics DROP COLUMN source")
        op.execute("ALTER TABLE companies DROP COLUMN source")
        op.execute("ALTER TABLE companies DROP COLUMN is_synthetic")
        return
    op.drop_column("financial_metrics", "source")
    op.drop_column("companies", "source")
    op.drop_column("companies", "is_synthetic")
