"""add instrument type and ISIN on companies

Revision ID: 0001
Revises:
Create Date: 2026-10-20

Existing rows become STOCK. The ISIN column is null until a caller
sets one. This revision alters a companies table that already exists.
It does not create the table. Application startup still uses
create_all. The full baseline migration is issue #8.

SQLite cannot ADD CONSTRAINT, and rebuilding the table would drop
companies while financial_metrics still points at it. The CHECK is
therefore part of the ADD COLUMN on SQLite, and a named constraint
on PostgreSQL. Neither path copies the table.
"""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_TYPE_CHECK = "instrument_type IN ('STOCK', 'ETF', 'ETC')"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(
            "ALTER TABLE companies ADD COLUMN instrument_type "
            "VARCHAR(8) NOT NULL DEFAULT 'STOCK' "
            "CHECK (" + _TYPE_CHECK + ")"
        )
    else:
        op.add_column(
            "companies",
            sa.Column(
                "instrument_type",
                sa.String(length=8),
                nullable=False,
                server_default=sa.text("'STOCK'"),
            ),
        )
        op.create_check_constraint(
            "ck_companies_instrument_type",
            "companies",
            _TYPE_CHECK,
        )
    op.add_column(
        "companies",
        sa.Column("isin", sa.String(length=12), nullable=True),
    )
    op.create_index(
        "uq_companies_isin",
        "companies",
        ["isin"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_companies_isin", table_name="companies")
    op.drop_column("companies", "isin")
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint(
            "ck_companies_instrument_type",
            "companies",
            type_="check",
        )
    op.drop_column("companies", "instrument_type")
