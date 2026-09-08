import pytest

from app.models.database_models import CompanyDB, FinancialMetricsDB


@pytest.mark.asyncio
async def test_financial_metrics_reject_missing_company_without_saving(client):
    with client.app.state.testing_session_local() as db:
        assert db.get(CompanyDB, 999) is None

    response = await client.post(
        "/api/v1/financial-metrics/",
        json={
            "company_id": 999,
            "period_end": "2024-12-31T00:00:00Z",
            "period_type": "annual",
            "revenue": 1_000_000.0,
        },
    )

    assert response.status_code == 400
    with client.app.state.testing_session_local() as db:
        assert db.query(FinancialMetricsDB).count() == 0


@pytest.mark.asyncio
async def test_financial_metrics_save_with_existing_company(client):
    company_response = await client.post(
        "/api/v1/companies/",
        json={"name": "Acme Corp", "ticker": "ACME"},
    )
    assert company_response.status_code == 201
    company_id = company_response.json()["id"]

    response = await client.post(
        "/api/v1/financial-metrics/",
        json={
            "company_id": company_id,
            "period_end": "2024-12-31T00:00:00Z",
            "period_type": "annual",
            "revenue": 1_000_000.0,
        },
    )

    assert response.status_code == 201
    with client.app.state.testing_session_local() as db:
        stored = db.query(FinancialMetricsDB).one()
        assert stored.id == response.json()["id"]
        assert stored.company_id == company_id
        assert stored.revenue == 1_000_000.0


@pytest.mark.asyncio
async def test_foreign_keys_enabled_on_initial_and_replacement_connections(
    client,
):
    with client.app.state.testing_session_local() as db:
        engine = db.get_bind()

    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1

    # Disposing StaticPool forces a new physical connection and in-memory DB.
    engine.dispose()
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
