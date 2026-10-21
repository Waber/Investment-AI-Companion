"""store OHLC prices exactly

Revision ID: 0006
Revises: 0005
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

This revision is ``0006`` and it revises ``0005`` (notes and
theses). ``0004`` is the watchlist. ``0003`` is the unique ticker
index. The literals below are frozen on purpose: a migration does
not import the application.

PostgreSQL ``ROUND`` is half away from zero. The application
quantizes half-even. On a legacy row those two rules differ by at
most one unit in the last place, ``1e-8``. A stored float keeps
about 15 significant digits, so the conversion cannot recover
digits the float never held.

SQLite rewrites each stored float to the canonical 8-place string
after the rebuild. A null price stays null. The preflight uses that
same conversion, not the raw float: PostgreSQL checks
``abs(ROUND(column::numeric, 8))``, and SQLite quantizes the text
SQLite would store for the real. A float under ``1e12`` can still
become ``1e12`` after that step. A result at or above ``1e12``, or
a value that is not finite, does not fit ``NUMERIC(20, 8)``.
Upgrade names those ``price_bars`` ids and stops before it changes
a row. Downgrade returns the four columns to FLOAT and restores
the check text from revision 0002.
"""

from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

# Twelve digits before the point is the numeric limit. 1e12 does not fit.
# The preflight and the PostgreSQL USING clause share this expression
# so a later edit cannot check one rounding and store another.
_PG_ROUNDED = "ROUND({name}::numeric, 8)"
_PRICE_ABS_LIMIT = "1000000000000"
_PRICE_LIMIT = Decimal(_PRICE_ABS_LIMIT)
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


class OversizedPricesError(RuntimeError):
    """A legacy price does not fit ``NUMERIC(20, 8)``.

    The message lists ``price_bars`` ids. The upgrade has not
    rewritten those rows.
    """


def upgrade() -> None:
    bind = op.get_bind()
    _reject_oversized(bind)
    if bind.dialect.name == "postgresql":
        _alter_postgres(_NUMERIC, sa.Float(), _PG_ROUNDED)
        return
    _rebuild_sqlite(sa.Float(), sa.Text(), _cast_sql)
    _write_sqlite_canonical_text()


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        _alter_postgres(sa.Float(), _NUMERIC, "{name}::double precision")
        return
    _rebuild_sqlite(sa.Text(), sa.Float(), _plain_sql)


def _reject_oversized(bind) -> None:
    """Abort before any rewrite when the converted price does not fit.

    The check uses the conversion this upgrade is about to apply.
    A raw ``abs(float) >= 1e12`` misses ``999999999999.9999``: the
    float is under the limit, and rounding makes it ``1e12``.
    PostgreSQL would then raise ``numeric field overflow`` inside
    the ``ALTER``. SQLite would store ``1000000000000.00000000``,
    which later reads skip. NaN and infinity are named before the
    numeric cast, because that cast rejects them. A null price is
    not selected.
    """
    if bind.dialect.name == "postgresql":
        ids = _postgres_oversized_ids(bind)
    else:
        ids = _sqlite_oversized_ids(bind)
    if not ids:
        return
    listed = ", ".join(str(item) for item in ids)
    raise OversizedPricesError(
        f"price_bars ids {listed} have a price outside Numeric(20, 8) "
        "or a price that is not finite. "
        "This upgrade did not change those rows."
    )


def _postgres_oversized_ids(bind):
    """Ids whose rounded numeric price does not fit, or is not finite.

    The ``CASE`` names NaN and infinity first. PostgreSQL does not
    evaluate the ``ELSE``, so ``ROUND`` never sees those values.
    ``_PG_ROUNDED`` is the same expression the ``ALTER`` uses.
    """
    nonfinite = "'NaN'::float8, 'Infinity'::float8, '-Infinity'::float8"
    parts = []
    for name in _PRICE_COLUMNS:
        rounded = _PG_ROUNDED.format(name=name)
        parts.append(
            "CASE "
            f"WHEN {name}::float8 IN ({nonfinite}) THEN TRUE "
            f"ELSE abs({rounded}) >= {_PRICE_ABS_LIMIT} "
            "END"
        )
    rows = bind.execute(
        sa.text(
            "SELECT id FROM price_bars WHERE "
            + " OR ".join(parts)
            + " ORDER BY id"
        )
    ).fetchall()
    return [row.id for row in rows]


def _sqlite_oversized_ids(bind):
    """Ids whose canonical text does not fit, or cannot be quantized.

    The batch copy turns each REAL into text with SQLite's own cast
    (``1000000000000.0``, not the shorter Python ``str(float)``).
    ``_quantized_legacy`` is the same function the rewrite uses on
    that text. A value SQLite renders as ``1.0e+20`` or ``Inf``
    cannot be quantized, and that is a rejection too.
    """
    columns = ", ".join(
        f"CAST({name} AS TEXT) AS {name}" for name in _PRICE_COLUMNS
    )
    rows = bind.execute(
        sa.text(f"SELECT id, {columns} FROM price_bars ORDER BY id")
    ).fetchall()
    bad = []
    for row in rows:
        for name in _PRICE_COLUMNS:
            raw = getattr(row, name)
            if raw is None:
                continue
            try:
                quantized = _quantized_legacy(raw)
                # ``Decimal('NaN')`` quantizes without raising.
                # ``abs(NaN) >= limit`` then raises outside this
                # try, which would abort the upgrade with a
                # traceback instead of the id list.
                if not quantized.is_finite() or abs(quantized) >= _PRICE_LIMIT:
                    bad.append(row.id)
                    break
            except (InvalidOperation, ValueError):
                bad.append(row.id)
                break
    return bad


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


def _quantized_legacy(value) -> Decimal:
    """The decimal this upgrade stores for one copied SQLite price.

    ``value`` is the text SQLite produced from the old real. The
    preflight calls this before the rebuild, on ``CAST(column AS
    TEXT)``, so both sides reject the same numbers.
    """
    return Decimal(str(value)).quantize(_QUANTUM, rounding=ROUND_HALF_EVEN)


def _canonical_text(value) -> str:
    return format(_quantized_legacy(value), "f")
