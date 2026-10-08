"""PostgreSQL behaviour that SQLite does not prove.

Issue #9. Schema comes from the models (``metadata.create_all``), not
from Alembic. Every test is marked ``integration``. Without
``-m integration`` pytest deselects the module. Without
``TEST_POSTGRES_DSN`` the database fixtures skip.

The session time zone is Europe/Warsaw, matching the manual check on
PostgreSQL 16: ``+02:00``, ``Z``, and naive ``period_end`` values read
back as the UTC instant, and a second write of that instant is rejected.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core import database as database_module
from app.models.database_models import CompanyDB, FinancialMetricsDB

pytestmark = pytest.mark.integration

COMPANIES = "/api/v1/companies/"
METRICS = "/api/v1/financial-metrics/"
UNIQUE_PERIOD = (
    "Financial metrics for this company, period end, "
    "and period type must be unique"
)
UTC_INSTANT = datetime(2025, 12, 31, tzinfo=timezone.utc)
# Same instant as UTC_INSTANT, five different spellings.
SAME_INSTANT_OFFSETS = (
    "2025-12-31T02:00:00+02:00",
    "2025-12-31T01:00:00+01:00",
    "2025-12-30T22:00:00-02:00",
    "2025-12-30T19:00:00-05:00",
    "2025-12-31T00:00:00+00:00",
)


def _explicit_utc(value):
    """Parse an API timestamp that must name UTC (``Z`` or ``+00:00``)."""
    assert value.endswith("Z") or value.endswith("+00:00"), value
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.utcoffset() == timedelta(0)
    return parsed


def _aware_utc(value):
    assert value is not None
    assert value.tzinfo is not None and value.utcoffset() is not None
    assert value.utcoffset() == timedelta(0)
    return value


def test_server_is_postgresql(postgres_engine):
    with postgres_engine.connect() as connection:
        version = connection.exec_driver_sql("SELECT version()").scalar()
    print(f"PostgreSQL server version: {version}")
    assert version.startswith("PostgreSQL ")


def test_transactions_use_europe_warsaw(postgres_engine):
    """The zone is set per transaction, so a committed SET does not stick."""
    with postgres_engine.connect() as connection:
        assert (
            connection.exec_driver_sql("SHOW TIME ZONE").scalar()
            == "Europe/Warsaw"
        )
    with postgres_engine.begin() as connection:
        connection.exec_driver_sql("SET TIME ZONE 'UTC'")
        assert connection.exec_driver_sql("SHOW TIME ZONE").scalar() == "UTC"
    with postgres_engine.connect() as connection:
        assert (
            connection.exec_driver_sql("SHOW TIME ZONE").scalar()
            == "Europe/Warsaw"
        )


def test_schema_comes_from_the_models(postgres_engine):
    """``create_all`` builds timestamptz columns and no Alembic version."""
    with postgres_engine.connect() as connection:
        tables = set(
            connection.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            ).scalars()
        )
        period_end_type = connection.execute(
            text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_schema = 'public' "
                "AND table_name = 'financial_metrics' "
                "AND column_name = 'period_end'"
            )
        ).scalar()
    assert {"companies", "financial_metrics"} <= tables
    assert "alembic_version" not in tables
    assert period_end_type == "timestamp with time zone"


def test_harness_does_not_open_the_application_engine(postgres_engine):
    """The import-time engine stays unused and names another database."""
    application_engine = database_module.engine
    assert postgres_engine is not application_engine
    assert postgres_engine.url.database != application_engine.url.database
    assert application_engine.pool.checkedout() == 0
    assert application_engine.pool.checkedin() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw_period_end", "instant"),
    [
        ("2025-12-31T02:00:00+02:00", UTC_INSTANT),
        ("2025-12-31T00:00:00Z", UTC_INSTANT),
        ("2025-12-31T00:00:00", UTC_INSTANT),
    ],
    ids=["plus-02", "zulu", "naive"],
)
async def test_period_end_reads_back_as_the_utc_instant(
    postgres_client, postgres_session_factory, raw_period_end, instant
):
    """Warsaw is not UTC, so a double shift would move this clock.

    ``+02:00`` in December is an hour away from the session zone
    (UTC+1). A naive value interpreted in that zone would land on the
    previous evening. Both must come back as 2025-12-31 00:00 UTC.
    """
    company = (
        await postgres_client.post(
            COMPANIES, json={"name": "UTC", "ticker": "UTC"}
        )
    ).json()
    created = await postgres_client.post(
        METRICS,
        json={
            "company_id": company["id"],
            "period_type": "annual",
            "period_end": raw_period_end,
        },
    )
    assert created.status_code == 201, created.text
    assert _explicit_utc(created.json()["period_end"]) == instant

    listed = await postgres_client.get(f"{METRICS}company/{company['id']}")
    assert listed.status_code == 200
    assert _explicit_utc(listed.json()[0]["period_end"]) == instant

    with postgres_session_factory() as db:
        row = db.query(FinancialMetricsDB).one()
        assert _aware_utc(row.period_end) == instant
        stored_utc_wall = db.execute(
            text(
                "SELECT period_end AT TIME ZONE 'UTC' "
                "FROM financial_metrics"
            )
        ).scalar()
    assert stored_utc_wall == instant.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_company_timestamp_keeps_the_instant_under_warsaw(
    postgres_client, postgres_session_factory
):
    """An aware +02:00 clock in December is 00:00 UTC, not 01:00 UTC."""
    company = (
        await postgres_client.post(
            COMPANIES, json={"name": "Clock", "ticker": "CLOCK"}
        )
    ).json()
    plus_two = timezone(timedelta(hours=2))
    written = datetime(2025, 12, 31, 2, 0, tzinfo=plus_two)
    with postgres_session_factory() as db:
        row = db.get(CompanyDB, company["id"])
        row.last_data_update = written
        db.commit()
    with postgres_session_factory() as db:
        row = db.get(CompanyDB, company["id"])
        assert _aware_utc(row.last_data_update) == UTC_INSTANT
        assert _aware_utc(row.created_at)
        assert _aware_utc(row.updated_at)


@pytest.mark.asyncio
async def test_five_same_instant_offsets_are_one_row(
    postgres_client, postgres_session_factory
):
    """Issue #20 on PostgreSQL: another offset is a duplicate, HTTP 400.

    The first write uses ``Z``. Five more spellings of that instant
    are rejected, and the table still has one row.
    """
    company = (
        await postgres_client.post(
            COMPANIES, json={"name": "Dup", "ticker": "INST"}
        )
    ).json()
    base = {"company_id": company["id"], "period_type": "annual"}
    first = await postgres_client.post(
        METRICS, json={**base, "period_end": "2025-12-31T00:00:00Z"}
    )
    assert first.status_code == 201, first.text

    for raw_period_end in SAME_INSTANT_OFFSETS:
        duplicate = await postgres_client.post(
            METRICS, json={**base, "period_end": raw_period_end}
        )
        assert duplicate.status_code == 400, (
            raw_period_end,
            duplicate.status_code,
            duplicate.text,
        )
        assert duplicate.json()["detail"] == UNIQUE_PERIOD

    with postgres_session_factory() as db:
        rows = db.query(FinancialMetricsDB).all()
        assert len(rows) == 1
        assert _aware_utc(rows[0].period_end) == UTC_INSTANT


def test_direct_insert_of_the_same_instant_hits_the_unique_constraint(
    postgres_session_factory,
):
    """Bypass the repository pre-check. The database constraint remains."""
    plus_two = timezone(timedelta(hours=2))
    with postgres_session_factory() as db:
        company = CompanyDB(name="Direct", ticker="DIRECT")
        db.add(company)
        db.commit()
        company_id = company.id
        db.add(
            FinancialMetricsDB(
                company_id=company_id,
                period_end=UTC_INSTANT,
                period_type="annual",
            )
        )
        db.commit()

    with postgres_session_factory() as db:
        db.add(
            FinancialMetricsDB(
                company_id=company_id,
                period_end=datetime(2025, 12, 31, 2, tzinfo=plus_two),
                period_type="annual",
            )
        )
        with pytest.raises(IntegrityError) as caught:
            db.commit()
        db.rollback()
    assert "uq_metrics_company_period" in str(caught.value)

    with postgres_session_factory() as db:
        assert db.query(FinancialMetricsDB).count() == 1


@pytest.mark.asyncio
async def test_missing_company_is_400_and_the_foreign_key_rejects_insert(
    postgres_client, postgres_session_factory
):
    response = await postgres_client.post(
        METRICS,
        json={
            "company_id": 999999,
            "period_end": "2025-12-31T00:00:00Z",
            "period_type": "annual",
        },
    )
    assert response.status_code == 400
    with postgres_session_factory() as db:
        assert db.query(FinancialMetricsDB).count() == 0
        db.add(
            FinancialMetricsDB(
                company_id=999999,
                period_end=UTC_INSTANT,
                period_type="annual",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.query(FinancialMetricsDB).count() == 0


def test_sql_delete_is_blocked_and_orm_delete_removes_metrics(
    postgres_session_factory,
):
    """The foreign key has no ON DELETE CASCADE.

    A raw ``DELETE FROM companies`` fails while metrics exist. Deleting
    the company through the ORM uses the relationship cascade and
    removes those metrics.
    """
    with postgres_session_factory() as db:
        company = CompanyDB(name="Parent", ticker="PARENT")
        db.add(company)
        db.commit()
        company_id = company.id
        db.add(
            FinancialMetricsDB(
                company_id=company_id,
                period_end=UTC_INSTANT,
                period_type="annual",
            )
        )
        db.commit()

    with postgres_session_factory() as db:
        # PostgreSQL checks the foreign key when the statement runs,
        # so the error is raised here rather than at commit.
        with pytest.raises(IntegrityError) as caught:
            db.execute(
                text("DELETE FROM companies WHERE id = :company_id"),
                {"company_id": company_id},
            )
        assert "financial_metrics_company_id_fkey" in str(caught.value)
        db.rollback()
        assert db.get(CompanyDB, company_id) is not None
        assert db.query(FinancialMetricsDB).count() == 1

    with postgres_session_factory() as db:
        company = db.get(CompanyDB, company_id)
        db.delete(company)
        db.commit()

    with postgres_session_factory() as db:
        assert db.get(CompanyDB, company_id) is None
        assert db.query(FinancialMetricsDB).count() == 0


def test_session_accepts_a_write_after_a_constraint_rollback(
    postgres_session_factory,
):
    """A failed insert rolls back, and the same session can commit again."""
    with postgres_session_factory() as db:
        db.add(
            FinancialMetricsDB(
                company_id=999999,
                period_end=UTC_INSTANT,
                period_type="annual",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        company = CompanyDB(name="After", ticker="AFTER")
        db.add(company)
        db.commit()
        company_id = company.id

    with postgres_session_factory() as db:
        assert db.get(CompanyDB, company_id) is not None
        assert db.query(FinancialMetricsDB).count() == 0


@pytest.mark.asyncio
async def test_duplicate_ticker_is_500_and_lowercase_is_stored(
    postgres_client, postgres_session_factory
):
    """Current PostgreSQL behaviour for issue #16. This file does not fix it.

    The ticker unique index is not ``uq_company_name_ticker``, so the
    repository re-raises ``IntegrityError`` and the API returns 500
    with a fixed detail. ``dup`` is a different ticker and is stored.
    The write after the 500 also shows the request session recovered.
    """
    first = await postgres_client.post(
        COMPANIES, json={"name": "A", "ticker": "DUP"}
    )
    assert first.status_code == 201, first.text

    duplicate = await postgres_client.post(
        COMPANIES, json={"name": "B", "ticker": "DUP"}
    )
    assert duplicate.status_code == 500
    assert duplicate.json()["detail"] == "Internal server error"
    assert "IntegrityError" not in duplicate.text
    assert "duplicate" not in duplicate.text.lower()

    lower = await postgres_client.post(
        COMPANIES, json={"name": "C", "ticker": "dup"}
    )
    assert lower.status_code == 201, lower.text

    with postgres_session_factory() as db:
        tickers = {row.ticker for row in db.query(CompanyDB).all()}
    assert tickers == {"DUP", "dup"}


@pytest.mark.asyncio
@pytest.mark.xfail(
    strict=True,
    reason=(
        "Issue #16 is open. Duplicate ticker should be 400 or 409, "
        "and dup should collide with DUP. Today the duplicate is 500 "
        "and dup is stored. Remove this marker when that behaviour "
        "lands."
    ),
)
async def test_duplicate_ticker_is_a_client_error_and_case_collides(
    postgres_client, postgres_session_factory
):
    """Target behaviour for issue #16.

    ``strict=True`` fails the suite when this starts passing, so the
    fix has to delete the marker in the same change. A fixture setup
    error is not an expected failure: a broken harness still fails CI.
    """
    first = await postgres_client.post(
        COMPANIES, json={"name": "A", "ticker": "DUP"}
    )
    assert first.status_code == 201, first.text

    duplicate = await postgres_client.post(
        COMPANIES, json={"name": "B", "ticker": "DUP"}
    )
    assert duplicate.status_code in (400, 409), duplicate.text

    lower = await postgres_client.post(
        COMPANIES, json={"name": "C", "ticker": "dup"}
    )
    assert lower.status_code in (400, 409), lower.text

    with postgres_session_factory() as db:
        assert db.query(CompanyDB).count() == 1
