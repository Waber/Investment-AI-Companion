"""ETF and ETC attribute table

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-10

Creates ``fund_attributes``, one row per company. Every fact column
is nullable. A missing TER or AUM stays null. This revision does not
write zero, and it does not copy anything out of ``companies``:
those facts were not stored before. ``source`` has no CHECK. The
application accepts ``manual``, ``demo``, and ``fixture``.

``is_synthetic`` defaults to false and ``source`` defaults to
``manual``, so a raw insert that omits them matches a hand-entered
row. ``as_of`` has no default. Inventing today's date would claim a
freshness the row does not have.

Downgrade drops the table. Companies, metrics, and price bars stay.
The attribute rows did not exist at revision 0009, so they are not
copied anywhere else.

A database that ``create_all`` already built has this table. Adding
it again would fail, so the create runs only when the table is
missing. ``down_revision`` is ``0009``, so Alembic keeps one head.
This file does not import application or script code.
"""

import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
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
    if _table_exists(bind, "fund_attributes"):
        return
    op.create_table(
        "fund_attributes",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("issuer", sa.String(length=255), nullable=True),
        sa.Column("underlying", sa.String(length=255), nullable=True),
        sa.Column("ter", sa.Float(), nullable=True),
        sa.Column("domicile", sa.String(length=100), nullable=True),
        sa.Column("replication_method", sa.String(length=64), nullable=True),
        sa.Column("distribution_policy", sa.String(length=64), nullable=True),
        sa.Column("aum", sa.Float(), nullable=True),
        sa.Column("aum_currency", sa.String(length=3), nullable=True),
        sa.Column("aum_as_of", sa.Date(), nullable=True),
        sa.Column("as_of", sa.Date(), nullable=True),
        sa.Column(
            "is_synthetic",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "source",
            sa.String(length=64),
            nullable=False,
            server_default="manual",
        ),
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
            "ter >= 0",
            name="ck_fund_attributes_ter_gte_zero",
        ),
        sa.CheckConstraint(
            "aum >= 0",
            name="ck_fund_attributes_aum_gte_zero",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_fund_attributes_company_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "company_id",
            name="uq_fund_attributes_company_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("fund_attributes")
