"""Watchlist behavior shared by the SQLite and PostgreSQL suites.

The two databases report a failed insert differently. These checks
do not read that text. A duplicate add returns the existing row, and
any other failure is raised after the integrity handler.
"""

from datetime import datetime, timezone

import pytest

from app.models.database_models import CompanyDB, WatchlistItemDB
from app.repositories.company_errors import CompanyNotFoundError
from app.repositories.company_repository import CompanyRepository
from app.repositories.watchlist_repository import (
    WatchlistRepository,
    WatchlistStorageError,
)


def add_company(session, name, ticker):
    row = CompanyDB(name=name, ticker=ticker)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def assert_model_declares_cascade_and_one_row_per_company():
    """The ORM flags the migration and the repository both rely on."""
    foreign_key = next(iter(WatchlistItemDB.company_id.foreign_keys))
    assert foreign_key.ondelete == "CASCADE"
    assert foreign_key.column.table.name == "companies"
    names = {item.name for item in WatchlistItemDB.__table__.constraints}
    assert "uq_watchlist_items_company_id" in names
    index_names = {item.name for item in WatchlistItemDB.__table__.indexes}
    assert "ix_watchlist_items_id" not in index_names
    relationship = CompanyDB.watchlist_item.property
    assert relationship.passive_deletes is True
    assert relationship.uselist is False


def assert_add_is_idempotent_and_keeps_the_first_label(session):
    company = add_company(session, "Acme", "ACME")
    repo = WatchlistRepository(session)

    first, created = repo.add(company.id, "  core  ")
    second, again = repo.add(company.id, "replaced")

    assert created is True
    assert again is False
    assert second.id == first.id
    assert second.label == "core"
    assert first.added_at.tzinfo is not None
    assert first.added_at.utcoffset().total_seconds() == 0
    assert repo.contains(company.id) is True
    assert repo.contains(company.id + 1) is False
    assert session.query(WatchlistItemDB).count() == 1


def assert_blank_label_is_stored_as_null(session):
    company = add_company(session, "Blank", "BLANK")
    row, created = WatchlistRepository(session).add(company.id, "   ")
    assert created is True
    assert row.label is None


def assert_race_returns_the_existing_row(monkeypatch, session):
    """The first lookup misses, so the unique constraint fires.

    The row that won the race is returned. The driver error is not
    raised, and a second row is not kept.
    """
    company = add_company(session, "Race", "RACE")
    repo = WatchlistRepository(session)
    first, created = repo.add(company.id, "keep")
    assert created is True
    original = repo.get_by_company_id
    calls = {"count": 0}

    def hide_the_first_lookup(company_id):
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return original(company_id)

    monkeypatch.setattr(repo, "get_by_company_id", hide_the_first_lookup)

    second, again = repo.add(company.id, "other")

    assert again is False
    assert second.id == first.id
    assert second.label == "keep"
    assert calls["count"] == 2
    stored_for_company = (
        session.query(WatchlistItemDB)
        .filter(WatchlistItemDB.company_id == company.id)
        .count()
    )
    assert stored_for_company == 1


def assert_missing_company_is_raised_outside_the_handler(session):
    """A foreign-key failure does not chain the driver error.

    The same session can still insert a real company afterwards.
    """
    repo = WatchlistRepository(session)

    with pytest.raises(CompanyNotFoundError) as caught:
        repo.add(999)

    assert caught.value.company_id == 999
    assert str(caught.value) == "Company 999 was not found"
    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None
    assert "FOREIGN" not in str(caught.value)
    assert "UNIQUE" not in str(caught.value)

    company = add_company(session, "After", "AFTER")
    stored, created = repo.add(company.id, "ok")
    assert created is True
    assert stored.company_id == company.id


def assert_unrelated_integrity_error_is_raised_outside_the_handler(
    monkeypatch, session
):
    """An integrity error that is not a missing company stays fixed.

    The company row is still there, and no watchlist row was stored.
    The error is raised after the handler, so the driver text is not
    on ``__context__``.
    """
    from sqlalchemy.exc import IntegrityError

    company = add_company(session, "Stuck", "STUCK")
    repo = WatchlistRepository(session)

    def fail_commit():
        raise IntegrityError("INSERT", {}, Exception("constraint"))

    monkeypatch.setattr(session, "commit", fail_commit)

    with pytest.raises(WatchlistStorageError) as caught:
        repo.add(company.id, "x")

    assert str(caught.value) == "Watchlist item could not be stored"
    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None
    assert "constraint" not in str(caught.value)
    assert "IntegrityError" not in str(caught.value)


def assert_list_orders_by_added_at_then_id(session):
    first_company = add_company(session, "First", "FIRST")
    second_company = add_company(session, "Second", "SECOND")
    repo = WatchlistRepository(session)
    older, _created = repo.add(first_company.id)
    newer, _created = repo.add(second_company.id)
    older_id = older.id
    newer_id = newer.id
    older = session.get(WatchlistItemDB, older_id)
    newer = session.get(WatchlistItemDB, newer_id)
    # The later insert gets the earlier instant, so id order and
    # added_at order disagree. added_at wins.
    older.added_at = datetime(2024, 6, 1, tzinfo=timezone.utc)
    newer.added_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    session.commit()

    assert [row.id for row in repo.list_items()] == [newer_id, older_id]

    older.added_at = newer.added_at
    session.commit()
    assert [row.id for row in repo.list_items()] == [older_id, newer_id]


def assert_remove_is_bool_and_company_delete_cascades(session):
    company = add_company(session, "Gone", "GONE")
    other = add_company(session, "Stay", "STAY")
    repo = WatchlistRepository(session)
    repo.add(company.id, "drop")
    kept, _created = repo.add(other.id, "keep")

    assert repo.remove(company.id) is True
    assert repo.remove(company.id) is False
    assert repo.get_by_company_id(company.id) is None
    assert repo.get_by_company_id(other.id).id == kept.id

    # Do not touch company.watchlist_item. passive_deletes must let
    # the database remove the row without loading it first.
    stored_company = session.get(CompanyDB, other.id)
    session.delete(stored_company)
    session.commit()
    assert repo.get_by_company_id(other.id) is None
    assert session.query(WatchlistItemDB).count() == 0


def assert_company_update_leaves_the_watchlist_row(session):
    """A data refresh updates the company and keeps the watchlist row."""
    from app.models.company import CompanyUpdate

    company = add_company(session, "Refresh", "REFRESH")
    repo = WatchlistRepository(session)
    item, _created = repo.add(company.id, "still")

    updated = CompanyRepository(session).update(
        company.id, CompanyUpdate(name="Refresh Co")
    )

    assert updated.name == "Refresh Co"
    assert repo.get_by_company_id(company.id).id == item.id
    assert repo.get_by_company_id(company.id).label == "still"
