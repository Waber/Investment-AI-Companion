from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.models.database_models import FinancialMetricsDB
from app.models.financial_metrics import FinancialMetricsCreate
from app.repositories import financial_metrics_repository

METRICS_URL = "/api/v1/financial-metrics/"


@pytest_asyncio.fixture
async def metric_seed(client):
    companies = []
    for name, ticker in [("First Corp", "FIRST"), ("Second Corp", "SECOND")]:
        response = await client.post(
            "/api/v1/companies/", json={"name": name, "ticker": ticker}
        )
        assert response.status_code == 201
        companies.append(response.json()["id"])

    payload = {
        "company_id": companies[0],
        "period_end": "2024-12-31T00:00:00",
        "period_type": "annual",
        "revenue": 100.0,
        "roe": 0.16,
    }
    for year in (2023, 2024):
        response = await client.post(
            METRICS_URL,
            json={**payload, "period_end": f"{year}-12-31T00:00:00"},
        )
        assert response.status_code == 201
    return payload, companies[1]


def snapshot(db):
    rows = db.execute(select(FinancialMetricsDB.__table__)).mappings()
    return {row["id"]: dict(row) for row in rows}


def fresh_snapshot(client):
    with client.app.state.testing_session_local() as db:
        return snapshot(db)


def assert_created_only(client, before, created_id, payload):
    after = fresh_snapshot(client)
    assert set(after) == {*before, created_id}
    assert created_id not in before
    assert {record_id: after[record_id] for record_id in before} == before
    stored = after[created_id]
    for field, value in payload.items():
        if field == "period_end":
            value = datetime.fromisoformat(value)
        assert stored[field] == value


@pytest.mark.asyncio
async def test_duplicate_api_create_preserves_rows_then_accepts_distinct(
    client, metric_seed
):
    payload, _ = metric_seed
    before = fresh_snapshot(client)

    response = await client.post(
        METRICS_URL, json={**payload, "revenue": -999.0, "roe": None}
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == (
        "Financial metrics for this company, period end, "
        "and period type must be unique"
    )
    assert fresh_snapshot(client) == before

    distinct = {**payload, "period_end": "2025-12-31T00:00:00"}
    response = await client.post(METRICS_URL, json=distinct)
    assert response.status_code == 201, response.text
    assert_created_only(client, before, response.json()["id"], distinct)


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["company_id", "period_end", "period_type"])
async def test_changing_one_unique_key_component_allows_create(
    client, metric_seed, field
):
    payload, other_company_id = metric_seed
    before = fresh_snapshot(client)
    replacement = {
        "company_id": other_company_id,
        "period_end": "2025-12-31T00:00:00",
        "period_type": "quarterly",
    }[field]
    distinct = {**payload, field: replacement}

    response = await client.post(METRICS_URL, json=distinct)

    assert response.status_code == 201, response.text
    assert_created_only(client, before, response.json()["id"], distinct)


@pytest.mark.asyncio
@pytest.mark.parametrize("constraint", ["foreign-key", "unique"])
async def test_real_constraint_failure_rolls_back_and_reuses_same_session(
    client, metric_seed, monkeypatch, constraint
):
    payload, other_company_id = metric_seed
    before = fresh_snapshot(client)
    invalid = {**payload, "revenue": -999.0, "roe": None}
    valid = {**payload, "period_end": "2025-12-31T00:00:00"}

    with client.app.state.testing_session_local() as db:
        repo = financial_metrics_repository.FinancialMetricsRepository(db)
        assert db.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        if constraint == "foreign-key":
            invalid["company_id"] = other_company_id + 1000
            expected_error = "FOREIGN KEY constraint failed"
        else:
            # Bypass only the precheck; the real unique constraint must fail.
            monkeypatch.setattr(repo, "is_unique", lambda *args: True)
            expected_error = "UNIQUE constraint failed"

        with pytest.raises(
            ValueError, match="^Failed to create financial metrics$"
        ) as error:
            repo.create(FinancialMetricsCreate(**invalid))

        cause = error.value.__context__
        assert isinstance(cause, IntegrityError)
        assert expected_error in str(cause.orig)
        assert db.is_active
        assert snapshot(db) == before

        # No caller rollback, replacement session, or mocked commit.
        created = repo.create(FinancialMetricsCreate(**valid))
        assert repo.db is db
        created_id = created.id

    assert_created_only(client, before, created_id, valid)
