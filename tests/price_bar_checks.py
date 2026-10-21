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


def price_bar_structure(connection):
    """The parts of ``price_bars`` the model and revision 0002 share.

    Indexes named ``ix_price_bars_id`` and
    ``ix_price_bars_instrument_id`` are the redundant ones. A match
    here is the autogenerate diff for this table: empty.
    """
    from sqlalchemy import inspect

    inspector = inspect(connection)
    columns = tuple(
        sorted(
            (
                column["name"],
                str(column["type"]).upper(),
                bool(column["nullable"]),
            )
            for column in inspector.get_columns("price_bars")
        )
    )
    foreign_keys = tuple(
        sorted(
            (
                fk.get("name"),
                tuple(fk["constrained_columns"]),
                (fk.get("options") or {}).get("ondelete"),
            )
            for fk in inspector.get_foreign_keys("price_bars")
        )
    )
    indexes = tuple(
        sorted(index["name"] for index in inspector.get_indexes("price_bars"))
    )
    check_sql = tuple(
        sorted(
            (
                item["name"],
                " ".join(item["sqltext"].split()),
            )
            for item in inspector.get_check_constraints("price_bars")
        )
    )
    return {
        "columns": columns,
        "foreign_keys": foreign_keys,
        "indexes": indexes,
        "checks": tuple(sorted(check_names(connection))),
        "check_sql": check_sql,
    }


def model_check_names(model):
    """Names of the check constraints declared on the SQLAlchemy model."""
    return {
        constraint.name
        for constraint in model.__table__.constraints
        if constraint.name and constraint.name.startswith("ck_price_bars_")
    }
