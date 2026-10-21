"""store price bars

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21

Creates ``price_bars``. It does not copy companies and it does not
rename that table. ``instrument_id`` points at ``companies.id``.

A database that ``create_all`` already built has this table. Stamp
that database (``alembic stamp head``). Running ``upgrade`` there
would try to create the table again. A database that only has the
legacy companies table, or that stopped at revision 0001, can
upgrade.

The candle checks are part of the table. Downgrade drops the table,
so those checks go away with it. A null price makes a comparison
null, and a check constraint allows null, so a missing open, high,
low, close, or volume is still stored.

``volume`` is BIGINT. PostgreSQL INTEGER stops at 2_147_483_647, and
a session volume can be larger. The foreign key is ON DELETE CASCADE.
There is no extra index on ``id`` or on ``instrument_id``: the primary
key and the unique key ``(instrument_id, bar_date, source)`` already
cover those lookups.
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_bars",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("bar_date", sa.Date(), nullable=False),
        sa.Column("open_price", sa.Float(), nullable=True),
        sa.Column("high_price", sa.Float(), nullable=True),
        sa.Column("low_price", sa.Float(), nullable=True),
        sa.Column("close_price", sa.Float(), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["companies.id"],
            name="fk_price_bars_instrument_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "instrument_id",
            "bar_date",
            "source",
            name="uq_price_bars_instrument_date_source",
        ),
        sa.CheckConstraint(
            "high_price >= open_price",
            name="ck_price_bars_high_gte_open",
        ),
        sa.CheckConstraint(
            "high_price >= close_price",
            name="ck_price_bars_high_gte_close",
        ),
        sa.CheckConstraint(
            "low_price <= open_price",
            name="ck_price_bars_low_lte_open",
        ),
        sa.CheckConstraint(
            "low_price <= close_price",
            name="ck_price_bars_low_lte_close",
        ),
        sa.CheckConstraint(
            "high_price >= low_price",
            name="ck_price_bars_high_gte_low",
        ),
        sa.CheckConstraint(
            "volume >= 0",
            name="ck_price_bars_volume_gte_zero",
        ),
    )


def downgrade() -> None:
    op.drop_table("price_bars")
