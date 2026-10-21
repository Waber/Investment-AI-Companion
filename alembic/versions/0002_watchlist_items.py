"""add the watchlist_items table

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21

Creates ``watchlist_items``. It does not copy ``companies`` and it
does not rename that table. ``company_id`` points at ``companies.id``
with ON DELETE CASCADE. One company has at most one row.

Numbering is provisional. Open pull requests #83 (price bars) and
#87 (ticker unique) also add a revision ``0002`` that revises
``0001``. This file chains off the current master head, ``0001``.
After whichever of those merges first, rebase this branch and:

1. Set ``down_revision`` to that new head.
2. Change ``revision`` to the next free number (``0003`` if only one
   of them merged, ``0004`` if both did).
3. Rename this file so the numeric prefix matches ``revision``.
   Leave the ``watchlist_items`` slug as it is.

A database that ``create_all`` already built has this table. Stamp
that database (``alembic stamp head``). Running ``upgrade`` there
would try to create the table again. A database that stopped at
revision ``0001`` can upgrade.
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
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
