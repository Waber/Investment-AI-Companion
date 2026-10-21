"""Schema and cascade checks for revision 0033.

SQLite and PostgreSQL tests call these helpers after ``upgrade``.
The helpers do not open a connection of their own.
"""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DataError, IntegrityError

from app.models.research import (
    NOTE_BODY_MAX,
    THESIS_BODY_MAX,
    THESIS_BREAKERS_MAX,
    THESIS_TITLE_MAX,
)


def _columns(inspector, table):
    return tuple(
        (
            column["name"],
            getattr(column["type"], "length", None),
            bool(column["nullable"]),
        )
        for column in inspector.get_columns(table)
    )


def _foreign_keys(inspector, table):
    found = []
    for fk in inspector.get_foreign_keys(table):
        options = fk.get("options") or {}
        ondelete = options.get("ondelete")
        found.append(
            (
                fk.get("name"),
                tuple(fk["constrained_columns"]),
                fk["referred_table"],
                tuple(fk["referred_columns"]),
                None if ondelete is None else ondelete.upper(),
            )
        )
    return tuple(sorted(found))


def _indexes(inspector, table):
    return tuple(
        sorted(
            (
                index["name"],
                bool(index["unique"]),
                tuple(index["column_names"]),
            )
            for index in inspector.get_indexes(table)
        )
    )


def _checks(inspector, table):
    return tuple(
        sorted(
            (
                item.get("name"),
                " ".join((item.get("sqltext") or "").split()),
            )
            for item in inspector.get_check_constraints(table)
        )
    )


def research_schema(connection):
    """The notes and theses shape the inspector reports."""
    inspector = inspect(connection)
    return {
        "notes_columns": _columns(inspector, "notes"),
        "theses_columns": _columns(inspector, "theses"),
        "notes_fks": _foreign_keys(inspector, "notes"),
        "theses_fks": _foreign_keys(inspector, "theses"),
        "notes_indexes": _indexes(inspector, "notes"),
        "theses_indexes": _indexes(inspector, "theses"),
        "theses_checks": _checks(inspector, "theses"),
    }


def assert_declared_lengths(connection):
    inspector = inspect(connection)
    lengths = {
        column["name"]: getattr(column["type"], "length", None)
        for column in inspector.get_columns("notes")
    }
    assert lengths["body"] == NOTE_BODY_MAX
    thesis_lengths = {
        column["name"]: getattr(column["type"], "length", None)
        for column in inspector.get_columns("theses")
    }
    assert thesis_lengths["title"] == THESIS_TITLE_MAX
    assert thesis_lengths["body"] == THESIS_BODY_MAX
    assert thesis_lengths["thesis_breakers"] == THESIS_BREAKERS_MAX


def exercise_migrated_research(connection):
    """Insert, reject a bad status, and cascade a company delete.

    The caller has already upgraded. ``companies`` exists and this
    connection enforces foreign keys. PostgreSQL also rejects a body
    longer than the column. SQLite does not enforce VARCHAR length;
    the declared length is checked separately.
    """
    connection.execute(
        text(
            "INSERT INTO companies (id, name, ticker) "
            "VALUES (1, 'Acme', 'ACME')"
        )
    )
    connection.execute(
        text("INSERT INTO notes (company_id, body) VALUES (1, 'hello')")
    )
    connection.execute(
        text(
            "INSERT INTO theses (company_id, title, body) "
            "VALUES (1, 'Title', 'Body')"
        )
    )
    connection.commit()
    stored = connection.execute(
        text("SELECT status, thesis_breakers FROM theses")
    ).one()
    assert stored.status == "active"
    assert stored.thesis_breakers == ""

    if connection.dialect.name == "postgresql":
        # A too-long VARCHAR is DataError. A bad status is IntegrityError.
        with pytest.raises(DataError):
            connection.execute(
                text("INSERT INTO notes (company_id, body) VALUES (1, :body)"),
                {"body": "x" * (NOTE_BODY_MAX + 1)},
            )
        connection.rollback()

    with pytest.raises(IntegrityError):
        connection.execute(
            text(
                "INSERT INTO theses (company_id, title, body, status) "
                "VALUES (1, 'Bad', 'Body', 'draft')"
            )
        )
    connection.rollback()

    connection.execute(text("DELETE FROM companies WHERE id = 1"))
    connection.commit()
    assert connection.execute(text("SELECT COUNT(*) FROM notes")).scalar() == 0
    assert (
        connection.execute(text("SELECT COUNT(*) FROM theses")).scalar() == 0
    )
