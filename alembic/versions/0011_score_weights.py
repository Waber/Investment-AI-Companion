"""Weight set per instrument type

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-18

Creates ``score_weights``, one row per instrument type. The row is
the weight set a caller saved. This revision does not insert the
built-in equal weights: those live in code and are version 1 until
a row exists. ``version`` and ``weights`` have no server default, so
a raw insert has to choose them. Inventing a version would claim a
saved set that nobody saved.

``instrument_type`` is STOCK, ETF, or ETC. ``version`` is at least 1.
``weights`` is JSON text. SQLite and PostgreSQL both store that text,
so the column is not a database JSON type.

Downgrade drops the table. Companies, metrics, fund attributes, and
price bars stay. The weight rows did not exist at revision 0010.

A database that ``create_all`` already built has this table. Adding
it again would fail, so the create runs only when the table is
missing. ``down_revision`` is ``0010``, so Alembic keeps one head.
This file does not import application or script code.
"""

import sqlalchemy as sa

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def _table_exists(bind, table):
    """True when ``table`` is already in the current schema.

    SQLite reads ``sqlite_master``. PostgreSQL reads
    ``information_schema`` for the current schema, so a test schema
    does not see another schema's table.
    """
    if bind.dialect.name == "sqlite":
        row = bind.execute(
            sa.text(
                "SELECT 1 FROM sqlite_master "
                "WHERE type = 'table' AND name = :table"
            ),
            {"table": table},
        ).scalar()
        return row is not None
    row = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = current_schema() "
            "AND table_name = :table"
        ),
        {"table": table},
    ).scalar()
    return row is not None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, "score_weights"):
        return
    op.create_table(
        "score_weights",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("instrument_type", sa.String(length=8), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("weights", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "instrument_type IN ('STOCK', 'ETF', 'ETC')",
            name="ck_score_weights_instrument_type",
        ),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_score_weights_version",
        ),
        sa.UniqueConstraint(
            "instrument_type",
            name="uq_score_weights_instrument_type",
        ),
    )


def downgrade() -> None:
    op.drop_table("score_weights")
