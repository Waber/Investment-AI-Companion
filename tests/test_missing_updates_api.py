import pytest
import pytest_asyncio
from sqlalchemy import event, select

from app.models.database_models import CompanyDB, FinancialMetricsDB
from app.repositories import financial_metrics_repository
from app.repositories.company_repository import CompanyRepository


@pytest_asyncio.fixture
async def existing_records(client):
    company_response = await client.post(
        "/api/v1/companies/",
        json={
            "name": "Acme Corp",
            "ticker": "ACME",
            "sector": "Technology",
            "industry": "Software",
            "country": "USA",
            "exchange": "NASDAQ",
            "currency": "USD",
        },
    )
    assert company_response.status_code == 201
    company = company_response.json()
    metrics_response = await client.post(
        "/api/v1/financial-metrics/",
        json={
            "company_id": company["id"],
            "period_end": "2024-12-31T00:00:00Z",
            "period_type": "annual",
            "revenue": 1000.0,
        },
    )
    assert metrics_response.status_code == 201
    return {"companies": company, "financial-metrics": metrics_response.json()}


def database_snapshot(client):
    with client.app.state.testing_session_local() as db:
        return {
            model.__tablename__: db.execute(
                select(model.__table__).order_by(model.id)
            ).all()
            for model in (CompanyDB, FinancialMetricsDB)
        }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resource,payload,detail",
    [
        ("companies", {"description": "Changed"}, "Company not found"),
        (
            "financial-metrics",
            {"revenue": 2000.0},
            "Financial metrics not found",
        ),
    ],
)
async def test_missing_update_returns_404_without_writes(
    client, existing_records, resource, payload, detail
):
    before = database_snapshot(client)
    writes = []

    def record_writes(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        if context.isinsert or context.isupdate or context.isdelete:
            writes.append(statement)

    with client.app.state.testing_session_local() as db:
        engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", record_writes)
    try:
        missing_id = existing_records[resource]["id"] + 1000
        response = await client.put(
            f"/api/v1/{resource}/{missing_id}",
            json=payload,
        )
    finally:
        event.remove(engine, "before_cursor_execute", record_writes)

    assert writes == []
    assert database_snapshot(client) == before
    assert response.status_code == 404
    assert response.json() == {"detail": detail}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resource,model,payload",
    [
        ("companies", CompanyDB, {"description": "Changed"}),
        ("financial-metrics", FinancialMetricsDB, {"revenue": 2000.0}),
    ],
)
async def test_existing_update_succeeds_and_persists(
    client, existing_records, resource, model, payload
):
    record_id = existing_records[resource]["id"]
    response = await client.put(
        f"/api/v1/{resource}/{record_id}",
        json=payload,
    )

    assert response.status_code == 200
    assert response.json()["id"] == record_id
    with client.app.state.testing_session_local() as db:
        stored = db.get(model, record_id)
        for field, value in payload.items():
            assert response.json()[field] == value
            assert getattr(stored, field) == value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resource,repository,payload",
    [
        ("companies", CompanyRepository, {"description": "Changed"}),
        (
            "financial-metrics",
            financial_metrics_repository.FinancialMetricsRepository,
            {"revenue": 2000.0},
        ),
    ],
)
@pytest.mark.parametrize(
    "error_type,status_code,detail",
    [
        (ValueError, 400, "Update rejected"),
        (RuntimeError, 500, "Internal server error"),
    ],
)
async def test_update_preserves_error_mapping(
    client,
    existing_records,
    monkeypatch,
    resource,
    repository,
    payload,
    error_type,
    status_code,
    detail,
):
    def fail_update(self, record_id, update):
        raise error_type("Update rejected")

    before = database_snapshot(client)
    monkeypatch.setattr(repository, "update", fail_update)
    record_id = existing_records[resource]["id"]
    response = await client.put(
        f"/api/v1/{resource}/{record_id}",
        json=payload,
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}
    assert database_snapshot(client) == before
