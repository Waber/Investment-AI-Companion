"""Watchlist revision and repository behavior on PostgreSQL.

The public schema stays on create_all. Migration checks use their own
schema and drop it when they finish.
"""

from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.core.database import Base
from tests.company_migration import (
    upgrade_head,
    without_unreflectable_ticker_index,
)
from tests.test_ui_watchlist import assert_watchlist_query_count_is_flat
from tests.watchlist_checks import (
    assert_add_is_idempotent_and_keeps_the_first_label,
    assert_company_update_leaves_the_watchlist_row,
    assert_list_orders_by_added_at_then_id,
    assert_missing_company_is_raised_outside_the_handler,
    assert_race_keeps_earlier_pending_work,
    assert_race_returns_the_existing_row,
    assert_remove_is_bool_and_company_delete_cascades,
    assert_unrelated_integrity_error_is_raised_outside_the_handler,
)
from tests.watchlist_migration import (
    ROOT,
    _config,
    assert_autogenerate_is_empty,
    assert_rendered_revision_is_empty,
    downgrade_to,
    prepare_legacy,
    watchlist_diffs,
    watchlist_structure,
)

pytestmark = pytest.mark.integration

SCHEMA = "watchlist_migration"


def _scratch(connection, schema):
    connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    connection.execute(text(f"CREATE SCHEMA {schema}"))
    connection.execute(text(f"SET search_path TO {schema}"))
    connection.commit()


def _drop_scratch(connection, schema):
    connection.rollback()
    connection.execute(text("SET search_path TO public"))
    connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    connection.commit()


def test_upgrade_downgrade_upgrade_on_postgresql(postgres_engine):
    with postgres_engine.connect() as connection:
        _scratch(connection, SCHEMA)
        try:
            prepare_legacy(connection)
            connection.commit()
            upgrade_head(connection)
            assert "watchlist_items" in inspect(connection).get_table_names()
            connection.execute(
                text(
                    "INSERT INTO watchlist_items "
                    "(company_id, added_at, label) "
                    "VALUES (1, '2024-01-02 00:00:00+00', 'core')"
                )
            )
            connection.commit()
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO watchlist_items (company_id, added_at) "
                        "VALUES (1, '2024-02-02 00:00:00+00')"
                    )
                )
            connection.rollback()
            connection.execute(text(f"SET search_path TO {SCHEMA}"))
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO watchlist_items (company_id, added_at) "
                        "VALUES (999, '2024-02-02 00:00:00+00')"
                    )
                )
            connection.rollback()
            connection.execute(text(f"SET search_path TO {SCHEMA}"))
            connection.execute(text("DELETE FROM companies WHERE id = 1"))
            connection.commit()
            remaining = connection.execute(
                text("SELECT COUNT(*) FROM watchlist_items")
            ).scalar()
            assert remaining == 0

            connection.execute(
                text(
                    "INSERT INTO companies "
                    "(id, name, ticker, instrument_type) "
                    "VALUES (1, 'Apple', 'AAPL', 'STOCK')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO watchlist_items (company_id, added_at) "
                    "VALUES (1, '2024-03-01 00:00:00+00')"
                )
            )
            connection.commit()
            downgrade_to(connection, "0003")
            assert (
                "watchlist_items" not in inspect(connection).get_table_names()
            )
            assert "price_bars" in inspect(connection).get_table_names()
            assert (
                connection.execute(
                    text("SELECT ticker FROM companies WHERE id = 1")
                ).scalar()
                == "AAPL"
            )
            upgrade_head(connection)
            assert "watchlist_items" in inspect(connection).get_table_names()
            assert (
                connection.execute(
                    text("SELECT COUNT(*) FROM watchlist_items")
                ).scalar()
                == 0
            )
            assert watchlist_diffs(connection) == []
        finally:
            _drop_scratch(connection, SCHEMA)


def test_migrated_postgresql_watchlist_matches_the_model(postgres_engine):
    schema = "watchlist_migration_match"
    with postgres_engine.connect() as public:
        public.execute(text("SET search_path TO public"))
        from_model = watchlist_structure(public)

    with postgres_engine.connect() as connection:
        _scratch(connection, schema)
        try:
            prepare_legacy(connection)
            connection.commit()
            upgrade_head(connection)
            from_migration = watchlist_structure(connection)
            assert from_migration == from_model
            ondelete = from_model["foreign_keys"][0][4]
            assert ondelete is not None
            assert ondelete.upper() == "CASCADE"
        finally:
            _drop_scratch(connection, schema)


def test_autogenerate_against_postgresql_watchlist_is_empty(postgres_engine):
    schema = "watchlist_autogen"
    written = None
    with postgres_engine.connect() as connection:
        _scratch(connection, schema)
        try:
            Base.metadata.create_all(bind=connection)
            # create_all already built these. Revision 0004 recreates
            # the watchlist. Revision 0005 recreates notes and theses.
            connection.execute(text("DROP TABLE theses"))
            connection.execute(text("DROP TABLE notes"))
            connection.execute(text("DROP TABLE watchlist_items"))
            connection.commit()
            config = _config(connection)
            command.stamp(config, "0003")
            upgrade_head(connection)
            assert_autogenerate_is_empty(connection)
            with without_unreflectable_ticker_index():
                script = command.revision(
                    config,
                    message="empty check",
                    autogenerate=True,
                    rev_id="9996",
                )
            written = Path(script.path)
            source = written.read_text()
        finally:
            if written is not None and written.exists():
                written.unlink()
            _drop_scratch(connection, schema)

    assert_rendered_revision_is_empty(source)
    assert not (ROOT / "alembic" / "versions" / "9996_empty_check.py").exists()


def _session(postgres_session_factory):
    return postgres_session_factory()


def test_add_is_idempotent_on_postgresql(postgres_session_factory):
    session = _session(postgres_session_factory)
    try:
        assert_add_is_idempotent_and_keeps_the_first_label(session)
    finally:
        session.close()


def test_race_returns_the_existing_row_on_postgresql(
    postgres_session_factory, monkeypatch
):
    session = _session(postgres_session_factory)
    try:
        assert_race_returns_the_existing_row(monkeypatch, session)
    finally:
        session.close()


def test_race_keeps_earlier_pending_work_on_postgresql(
    postgres_session_factory, monkeypatch
):
    session = _session(postgres_session_factory)
    try:
        assert_race_keeps_earlier_pending_work(monkeypatch, session)
    finally:
        session.close()


def test_missing_company_is_raised_outside_the_handler_on_postgresql(
    postgres_session_factory,
):
    session = _session(postgres_session_factory)
    try:
        assert_missing_company_is_raised_outside_the_handler(session)
    finally:
        session.close()


def test_unrelated_integrity_error_on_postgresql(
    postgres_session_factory, monkeypatch
):
    session = _session(postgres_session_factory)
    try:
        assert_unrelated_integrity_error_is_raised_outside_the_handler(
            monkeypatch, session
        )
    finally:
        session.close()


def test_list_orders_by_added_at_then_id_on_postgresql(
    postgres_session_factory,
):
    session = _session(postgres_session_factory)
    try:
        assert_list_orders_by_added_at_then_id(session)
    finally:
        session.close()


def test_remove_and_cascade_on_postgresql(postgres_session_factory):
    session = _session(postgres_session_factory)
    try:
        assert_remove_is_bool_and_company_delete_cascades(session)
    finally:
        session.close()


def test_company_update_leaves_the_watchlist_row_on_postgresql(
    postgres_session_factory,
):
    session = _session(postgres_session_factory)
    try:
        assert_company_update_leaves_the_watchlist_row(session)
    finally:
        session.close()


@pytest.mark.asyncio
async def test_watchlist_api_on_postgresql(postgres_client):
    missing = await postgres_client.post(
        "/api/v1/watchlist/", json={"company_id": 999}
    )
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Company not found"

    created_company = await postgres_client.post(
        "/api/v1/companies/",
        json={"name": "Pg Co", "ticker": "PGCO"},
    )
    assert created_company.status_code == 201
    company_id = created_company.json()["id"]

    created = await postgres_client.post(
        "/api/v1/watchlist/",
        json={"company_id": company_id, "label": "  core  "},
    )
    assert created.status_code == 201
    assert created.json()["label"] == "core"
    again = await postgres_client.post(
        "/api/v1/watchlist/",
        json={"company_id": company_id, "label": "other"},
    )
    assert again.status_code == 200
    assert again.json()["id"] == created.json()["id"]
    assert again.json()["label"] == "core"

    deleted = await postgres_client.delete(f"/api/v1/companies/{company_id}")
    assert deleted.status_code == 204
    listed = await postgres_client.get("/api/v1/watchlist/")
    assert listed.status_code == 200
    assert listed.json() == []


@pytest.mark.asyncio
async def test_nul_label_is_422_on_postgresql(postgres_client):
    """A NUL in the label is 422, not a PostgreSQL 500.

    The check runs in the write model, before the insert. PostgreSQL
    would reject a NUL inside a string if the model let it through.
    """
    created_company = await postgres_client.post(
        "/api/v1/companies/",
        json={"name": "Nul Co", "ticker": "NULCO"},
    )
    assert created_company.status_code == 201
    company_id = created_company.json()["id"]
    response = await postgres_client.post(
        "/api/v1/watchlist/",
        json={"company_id": company_id, "label": "A\x00B"},
    )
    assert response.status_code == 422
    assert response.status_code != 500
    assert "IntegrityError" not in response.text
    listed = await postgres_client.get("/api/v1/watchlist/")
    assert listed.json() == []


@pytest.mark.asyncio
async def test_company_deleted_before_insert_is_404_on_postgresql(
    postgres_client, monkeypatch
):
    """A company deleted between the check and the insert is 404.

    PostgreSQL raises a foreign-key IntegrityError. The API maps that
    to the same not-found detail, without the driver text.
    """
    from app.models.database_models import CompanyDB
    from app.repositories.watchlist_repository import WatchlistRepository

    created_company = await postgres_client.post(
        "/api/v1/companies/",
        json={"name": "Gone Co", "ticker": "GONECO"},
    )
    assert created_company.status_code == 201
    company_id = created_company.json()["id"]
    original = WatchlistRepository.add

    def delete_then_add(self, company_id, label=None):
        company = self.db.get(CompanyDB, company_id)
        self.db.delete(company)
        self.db.commit()
        return original(self, company_id, label)

    monkeypatch.setattr(WatchlistRepository, "add", delete_then_add)
    response = await postgres_client.post(
        "/api/v1/watchlist/",
        json={"company_id": company_id, "label": "late"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Company not found"
    assert "IntegrityError" not in response.text
    assert "FOREIGN" not in response.text
    listed = await postgres_client.get("/api/v1/watchlist/")
    assert listed.json() == []


@pytest.mark.asyncio
async def test_watchlist_page_query_count_does_not_grow(postgres_client):
    """The watchlist page stays a fixed number of statements on PostgreSQL.

    Same seed as the SQLite test: one priced row, then ten. The Warsaw
    session timezone can add a statement the SQLite file does not see,
    so this test checks that the count does not grow and stays small.
    """
    count = await assert_watchlist_query_count_is_flat(postgres_client)
    assert count <= 8, count
