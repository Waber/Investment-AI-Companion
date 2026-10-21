"""add the watchlist_items table

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-21

Creates ``watchlist_items``. It does not copy ``companies`` and it
does not rename that table. ``company_id`` points at ``companies.id``
with ON DELETE CASCADE. One company has at most one row.

This revises ``0002``, the price bars revision. The file used to be
``0002`` as well, which made a second Alembic head after that
revision merged. The slug stays ``watchlist_items``.

A database that ``create_all`` already built has this table. Stamp
that database (``alembic stamp head``). Running ``upgrade`` there
would try to create the table again. A database that stopped at
revision ``0002`` can upgrade.
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_watchlist_items_company_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            name="uq_watchlist_items_company_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("watchlist_items")
