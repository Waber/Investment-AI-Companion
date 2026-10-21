"""store OHLC prices as numeric

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-21

``open_price``, ``high_price``, ``low_price``, and ``close_price``
change from FLOAT to NUMERIC(20, 8). Twelve digits before the
decimal point and eight after. Volume stays BIGINT.

This is the next number after master's 0002. Open pull requests
#87, #90, and #91 also add revisions. When one of those merges,
re-chain this file onto the new head and renumber it if 0003 was
taken.

PostgreSQL rounds each stored float half away from zero to 8
places while it changes the type. SQLite cannot change a column
type in place, so the table is rebuilt. A null price stays null.
Downgrade returns the four columns to FLOAT. The candle checks
stay; they compare the same columns either way.
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_PRICE_COLUMNS = ("open_price", "high_price", "low_price", "close_price")
_NUMERIC = sa.Numeric(20, 8)


def upgrade() -> None:
    _alter(_NUMERIC, sa.Float(), "ROUND({name}::numeric, 8)")


def downgrade() -> None:
    _alter(sa.Float(), _NUMERIC, "{name}::double precision")


def _alter(new_type, old_type, postgres_using: str) -> None:
    """Change the four price columns.

    ``postgres_using`` is a format string with ``{name}``. SQLite
    rebuilds the table, so it has no USING clause. The rebuild keeps
    the primary key, the foreign key, the unique key, and the checks.
    """
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for name in _PRICE_COLUMNS:
            op.alter_column(
                "price_bars",
                name,
                existing_type=old_type,
                type_=new_type,
                existing_nullable=True,
                postgresql_using=postgres_using.format(name=name),
            )
        return
    with op.batch_alter_table("price_bars") as batch:
        for name in _PRICE_COLUMNS:
            batch.alter_column(
                name,
                existing_type=old_type,
                type_=new_type,
                existing_nullable=True,
            )
