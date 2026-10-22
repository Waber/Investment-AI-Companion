"""Shared checks for the watchlist_items revision.

SQLite and PostgreSQL both compare a ``create_all`` database with a
database that revision 0004 upgraded. They also ask Alembic whether
autogenerate still wants to change ``watchlist_items``.
"""

from pathlib import Path

from sqlalchemy import inspect, text

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from app.core.database import Base
from tests.company_migration import (
    LEGACY_COMPANIES,
    LEGACY_METRICS,
    assert_upper_ticker_index_recorded,
    without_unreflectable_ticker_index,
)

ROOT = Path(__file__).resolve().parents[1]


def _config(connection):
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


def downgrade_to(connection, revision):
    command.downgrade(_config(connection), revision)


def prepare_legacy(connection):
    """Companies and financial_metrics as they were before revision 0001."""
    connection.execute(text(LEGACY_COMPANIES))
    connection.execute(text(LEGACY_METRICS))
    connection.execute(
        text(
            "INSERT INTO companies (id, name, ticker) "
            "VALUES (1, 'Apple', 'AAPL')"
        )
    )


def watchlist_structure(connection):
    """Column, key, and foreign-key shape of ``watchlist_items``.

    Callers compare a ``create_all`` database with one that revision
    0004 created. The two dialects report types differently, so the
    comparison is within one dialect, not across dialects.
    """
    inspector = inspect(connection)
    columns = tuple(
        (column["name"], str(column["type"]), column["nullable"])
        for column in inspector.get_columns("watchlist_items")
    )
    primary_key = tuple(
        inspector.get_pk_constraint("watchlist_items")["constrained_columns"]
    )
    uniques = tuple(
        sorted(
            (item["name"], tuple(item["column_names"] or []))
            for item in inspector.get_unique_constraints("watchlist_items")
        )
    )
    indexes = tuple(
        sorted(
            (
                index["name"],
                bool(index["unique"]),
                tuple(index["column_names"]),
            )
            for index in inspector.get_indexes("watchlist_items")
        )
    )
    foreign_keys = tuple(
        sorted(
            (
                tuple(item["constrained_columns"]),
                item["referred_table"],
                tuple(item["referred_columns"]),
                item.get("name"),
                (item.get("options") or {}).get("ondelete"),
            )
            for item in inspector.get_foreign_keys("watchlist_items")
        )
    )
    return {
        "columns": columns,
        "primary_key": primary_key,
        "uniques": uniques,
        "indexes": indexes,
        "foreign_keys": foreign_keys,
    }


def watchlist_diffs(connection):
    """Autogenerate operations that mention ``watchlist_items``.

    An empty list means the upgraded table already matches the model.
    Other tables are ignored: a legacy companies table is not the full
    model, and this helper is also used after a full ``create_all``.
    """
    with without_unreflectable_ticker_index():
        context = MigrationContext.configure(connection)
        diff = compare_metadata(context, Base.metadata)
    return [item for item in diff if "watchlist" in repr(item).lower()]


def assert_rendered_revision_is_empty(source):
    """A generated revision whose upgrade and downgrade only ``pass``.

    Alembic wraps that ``pass`` in its marker comments. No operation
    and no mention of ``watchlist_items`` means the model and the
    migration already agree.
    """
    for direction in ("upgrade", "downgrade"):
        marker = f"def {direction}() -> None:"
        section = source.split(marker, 1)[1]
        if direction == "upgrade":
            section = section.split("def downgrade", 1)[0]
        assert "pass" in section
        assert "op." not in section
    assert "watchlist_items" not in source


def assert_autogenerate_is_empty(connection):
    """The model and the database agree, including ``watchlist_items``.

    This is the check that a second ``alembic revision --autogenerate``
    would write an empty upgrade. It has to run on a database built by
    ``create_all``, with the watchlist table recreated by revision 0004,
    so a drift in that revision shows up here.
    """
    with without_unreflectable_ticker_index():
        context = MigrationContext.configure(connection)
        diff = compare_metadata(context, Base.metadata)
    assert diff == []
    # An empty diff does not prove the expression index is present.
    assert_upper_ticker_index_recorded(connection)
