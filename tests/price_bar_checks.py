"""Candle checks shared by the SQLite and PostgreSQL migration tests.

Each violation breaks one constraint and leaves the others true or
null, so the database reports that one name.
"""

CANDLE_CHECK_NAMES = (
    "ck_price_bars_high_gte_open",
    "ck_price_bars_high_gte_close",
    "ck_price_bars_low_lte_open",
    "ck_price_bars_low_lte_close",
    "ck_price_bars_high_gte_low",
    "ck_price_bars_volume_gte_zero",
)

# Extra columns, extra values, and the check that must fail.
CANDLE_VIOLATIONS = (
    ("open_price, high_price", "10, 9", "ck_price_bars_high_gte_open"),
    ("close_price, high_price", "10, 9", "ck_price_bars_high_gte_close"),
    ("open_price, low_price", "8, 9", "ck_price_bars_low_lte_open"),
    ("close_price, low_price", "8, 9", "ck_price_bars_low_lte_close"),
    ("high_price, low_price", "1, 2", "ck_price_bars_high_gte_low"),
    ("volume", "-1", "ck_price_bars_volume_gte_zero"),
)

# A bar with no prices and no volume. Every check is null, so it
# must be stored. id 2 keeps it distinct from a rejected id 1.
NULL_BAR_SQL = (
    "INSERT INTO price_bars ("
    "id, instrument_id, bar_date, currency, source, retrieved_at"
    ") VALUES (2, 1, '2024-01-09', 'USD', 'fake', "
    "'2024-01-09 00:00:00+00')"
)


def violation_sql(columns, values):
    """One insert that should fail ``columns``'s check."""
    return (
        "INSERT INTO price_bars ("
        "id, instrument_id, bar_date, currency, source, retrieved_at, "
        f"{columns}) VALUES ("
        "1, 1, '2024-01-02', 'USD', 'fake', "
        f"'2024-01-02 00:00:00+00', {values})"
    )


def check_names(connection):
    """Names of the check constraints on the live ``price_bars`` table."""
    from sqlalchemy import inspect

    return {
        item["name"]
        for item in inspect(connection).get_check_constraints("price_bars")
    }


def model_check_names(model):
    """Names of the check constraints declared on the SQLAlchemy model."""
    return {
        constraint.name
        for constraint in model.__table__.constraints
        if constraint.name and constraint.name.startswith("ck_price_bars_")
    }
