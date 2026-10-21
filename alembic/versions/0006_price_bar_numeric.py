"""store OHLC prices exactly

Revision ID: 0006
Revises: 0003
Create Date: 2026-10-21

``open_price``, ``high_price``, ``low_price``, and ``close_price``
change from FLOAT. PostgreSQL stores ``NUMERIC(20, 8)``: twelve
digits before the decimal point and eight after. SQLite stores the
canonical 8-place string as TEXT. A SQLite numeric column would
keep a binary float, and the price that came back would not be the
price that was written. Volume stays BIGINT.

The candle checks stay, and they are recreated so they match the new
column type. Revision 0002 created them on FLOAT columns, and
PostgreSQL keeps that as ``::double precision`` even after the column
becomes numeric. Upgrade drops those five checks and creates them
again on the numeric columns. On SQLite they compare
``CAST(column AS REAL)``. A text comparison would reject a valid
candle such as low 9 and open 10. The API model is the exact check.
This rebuilds ``price_bars`` only. It does not rebuild ``companies``.

This revision is ``0006`` and it revises ``0003`` (the unique
ticker index). Pull requests #90 and #91 add ``0004`` and ``0005``
and merge before this file. The final re-chain sets
``down_revision`` to ``0005``. Until those merge, the parent stays
``0003`` so this branch has one Alembic head. The literals below
are frozen on purpose: a migration does not import the application.

PostgreSQL rounds each stored float half away from zero to 8 places
while it changes the type. SQLite rewrites each stored float to the
canonical 8-place string after the rebuild. A null price stays null.
Downgrade returns the four columns to FLOAT and restores the check
text from revision 0002.
"""

from decimal import ROUND_HALF_EVEN, Decimal

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0003"
branch_labels = None
depends_on = None

_PRICE_COLUMNS = ("open_price", "high_price", "low_price", "close_price")
_NUMERIC = sa.Numeric(20, 8)
_QUANTUM = Decimal("0.00000001")
# (name, left, operator, right). The same five checks as revision 0002.
_OHLC_CHECKS = (
    ("ck_price_bars_high_gte_open", "high_price", ">=", "open_price"),
    ("ck_price_bars_high_gte_close", "high_price", ">=", "close_price"),
    ("ck_price_bars_low_lte_open", "low_price", "<=", "open_price"),
    ("ck_price_bars_low_lte_close", "low_price", "<=", "close_price"),
    ("ck_price_bars_high_gte_low", "high_price", ">=", "low_price"),
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        _alter_postgres(_NUMERIC, sa.Float(), "ROUND({name}::numeric, 8)")
        return
    _rebuild_sqlite(sa.Float(), sa.Text(), _cast_sql)
    _write_sqlite_canonical_text()


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        _alter_postgres(sa.Float(), _NUMERIC, "{name}::double precision")
        return
    _rebuild_sqlite(sa.Text(), sa.Float(), _plain_sql)


def _alter_postgres(new_type, old_type, using: str) -> None:
    """Change the four price columns, then recreate the OHLC checks.

    The checks are dropped first. PostgreSQL would otherwise keep the
    float comparison it recorded when revision 0002 created them.
    Creating them again after the type change binds the comparison
    to the new column type: numeric on the way up, float on the way
    down.
    """
    for name, _left, _operator, _right in _OHLC_CHECKS:
        op.drop_constraint(name, "price_bars", type_="check")
    for name in _PRICE_COLUMNS:
        op.alter_column(
            "price_bars",
            name,
            existing_type=old_type,
            type_=new_type,
            existing_nullable=True,
            postgresql_using=using.format(name=name),
        )
    for name, left, operator, right in _OHLC_CHECKS:
        op.create_check_constraint(
            name, "price_bars", _plain_sql(left, operator, right)
        )


def _rebuild_sqlite(old_type, new_type, check_sql) -> None:
    """Rebuild ``price_bars`` once. ``companies`` is not touched.

    Column types and the five OHLC checks change in the same batch.
    SQLite copies the rows while it rebuilds, and the copy is checked
    against the new rules. Doing the checks in a second batch would
    copy them as text comparisons first and reject a valid low of 9
    against an open of 10.
    """
    with op.batch_alter_table("price_bars") as batch:
        for name in _PRICE_COLUMNS:
            batch.alter_column(
                name,
                existing_type=old_type,
                type_=new_type,
                existing_nullable=True,
            )
        for name, left, operator, right in _OHLC_CHECKS:
            batch.drop_constraint(name, type_="check")
            batch.create_check_constraint(
                name, check_sql(left, operator, right)
            )


def _plain_sql(left: str, operator: str, right: str) -> str:
    return f"{left} {operator} {right}"


def _cast_sql(left: str, operator: str, right: str) -> str:
    return f"CAST({left} AS REAL) {operator} CAST({right} AS REAL)"


def _write_sqlite_canonical_text() -> None:
    """Turn each copied float into the 8-place string the API returns.

    The batch copy casts the old real to text with SQLite's own
    formatting (``10.5``, not ``10.50000000``). This pass writes the
    canonical string. Null stays null.
    """
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, open_price, high_price, low_price, close_price "
            "FROM price_bars"
        )
    ).fetchall()
    for row in rows:
        values = {"id": row.id}
        assignments = []
        for name in _PRICE_COLUMNS:
            raw = getattr(row, name)
            if raw is None:
                continue
            values[name] = _canonical_text(raw)
            assignments.append(f"{name} = :{name}")
        if not assignments:
            continue
        bind.execute(
            sa.text(
                "UPDATE price_bars SET "
                + ", ".join(assignments)
                + " WHERE id = :id"
            ),
            values,
        )


def _canonical_text(value) -> str:
    quantized = Decimal(str(value)).quantize(
        _QUANTUM, rounding=ROUND_HALF_EVEN
    )
    return format(quantized, "f")
