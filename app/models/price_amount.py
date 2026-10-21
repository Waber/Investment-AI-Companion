"""Exact OHLC storage on PostgreSQL and on SQLite.

PostgreSQL keeps ``Numeric(20, 8)``. SQLite cannot. Its numeric
affinity stores a binary float, and SQLAlchemy binds ``Numeric``
through ``float``. A price with more significant digits than that
float can hold is then a different number on the way back. One of
those numbers is large enough that the API model rejects it, which
used to fail the request after the row had already been committed
and made every later read of that instrument fail too.

On SQLite this type writes the canonical 8-place string into a TEXT
column and parses that string back with ``Decimal``. The string is
the same one the API returns, so a stored price cannot come back as
a different price.
"""

import logging
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

from sqlalchemy import Boolean, Numeric, Text
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.types import TypeDecorator

logger = logging.getLogger(__name__)

# 12 digits before the decimal point and 8 after. 10**12 does not fit.
PRICE_PRECISION = 20
PRICE_SCALE = 8
PRICE_QUANTUM = Decimal("0.00000001")
PRICE_LIMIT = Decimal(10) ** (PRICE_PRECISION - PRICE_SCALE)


class UnreadablePrice:
    """A stored price that is not a decimal.

    Loading a row must not raise. One bad cell would abort the whole
    SELECT, and the price list would be HTTP 500 for every bar of
    that instrument. The repository drops the row and logs its id.
    """

    def __repr__(self) -> str:
        return "UnreadablePrice()"


def quantize_price(value: Decimal) -> Decimal:
    """Fit one price to 8 decimal places, half-even.

    ``Decimal('1e400')`` is a real ``Decimal``, but rounding it to 8
    places needs more digits than the decimal context allows, so
    ``quantize`` raises ``InvalidOperation``. That is not a
    ``ValueError``. The API turns ``ValueError`` into HTTP 422 and
    would turn anything else into HTTP 500, so the conversion is
    done here.
    """
    try:
        return value.quantize(PRICE_QUANTUM, rounding=ROUND_HALF_EVEN)
    except InvalidOperation as exc:
        raise ValueError("price is not a finite decimal") from exc


def price_text(value: Decimal) -> str:
    """Canonical fixed-point string, always 8 digits after the point."""
    return format(quantize_price(value), "f")


class PriceAmount(TypeDecorator):
    """OHLC column: exact numeric on PostgreSQL, exact text on SQLite.

    ``load_dialect_impl`` picks the real column type.
    ``process_bind_param`` runs before the value is sent, and
    ``process_result_value`` runs when the value comes back.
    ``cache_ok`` lets SQLAlchemy cache statements that use the column.
    """

    impl = Numeric(PRICE_PRECISION, PRICE_SCALE)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            # TEXT, not NUMERIC. NUMERIC would bind through float().
            return dialect.type_descriptor(Text())
        return dialect.type_descriptor(Numeric(PRICE_PRECISION, PRICE_SCALE))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        try:
            if isinstance(value, bool) or not isinstance(value, Decimal):
                # Decimal(str(value)) keeps a float's short decimal
                # (``0.1``) rather than the binary expansion.
                value = Decimal(str(value))
            quantized = quantize_price(value)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("price is not a finite decimal") from exc
        if abs(quantized) >= PRICE_LIMIT:
            raise ValueError("price exceeds Numeric(20, 8)")
        if dialect.name == "sqlite":
            return price_text(quantized)
        return quantized

    def process_result_value(self, value, dialect):
        if value is None or isinstance(value, UnreadablePrice):
            return value
        try:
            if isinstance(value, Decimal):
                return value
            return Decimal(str(value))
        except (InvalidOperation, ValueError, ArithmeticError):
            # Do not log the cell. A bad value can be enormous, and
            # the repository logs the bar id when it skips the row.
            return UnreadablePrice()


def price_compare(left: str, operator: str, right: str) -> "_PriceCompare":
    """The OHLC comparison used by the ``price_bars`` checks."""
    return _PriceCompare(left, operator, right)


class _PriceCompare(ColumnElement):
    """One OHLC comparison, compiled per database.

    On PostgreSQL the columns are numeric, so ``high_price >=
    open_price`` is the real order. On SQLite the columns are text.
    ``'10' >= '9'`` is false as text, because ``'1' < '9'``, and a
    valid candle (low 9, open 10) would be rejected. ``CAST(... AS
    REAL)`` compares the numbers. The API model remains the exact
    check: a binary float cannot separate two prices that differ
    only past its precision, but the cast keeps the numeric order,
    so a candle the model accepted still passes.
    """

    inherit_cache = True
    type = Boolean()

    def __init__(self, left: str, operator: str, right: str):
        self.left = left
        self.operator = operator
        self.right = right


@compiles(_PriceCompare)
def _compile_price_compare(element, compiler, **kwargs):
    return f"{element.left} {element.operator} {element.right}"


@compiles(_PriceCompare, "sqlite")
def _compile_price_compare_sqlite(element, compiler, **kwargs):
    return (
        f"CAST({element.left} AS REAL) {element.operator} "
        f"CAST({element.right} AS REAL)"
    )
