"""Delete, 404, list-by-company and generic 500 paths of the CRUD API."""

import pytest

from app.repositories.company_repository import CompanyRepository
from app.repositories.financial_metrics_repository import (
    FinancialMetricsRepository,
)

COMPANIES = "/api/v1/companies/"
METRICS = "/api/v1/financial-metrics/"


async def create_company(client, ticker="DELT", name="Delete Test Co"):
    response = await client.post(
        COMPANIES, json={"name": name, "ticker": ticker}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_metrics(client, company_id, period_end, revenue=100.0):
    response = await client.post(
        METRICS,
        json={
            "company_id": company_id,
            "period_end": period_end,
            "period_type": "annual",
            "revenue": revenue,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


# company-shaped pin, see #26
@pytest.mark.asyncio
async def test_get_missing_company_returns_404(client):
    response = await client.get(f"{COMPANIES}999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Company not found"}


@pytest.mark.asyncio
async def test_delete_company_returns_204_and_removes_its_metrics(client):
    company = await create_company(client)
    metrics = await create_metrics(
        client, company["id"], "2024-12-31T00:00:00Z"
    )

    response = await client.delete(f"{COMPANIES}{company['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert (await client.get(f"{COMPANIES}{company['id']}")).status_code == 404
    assert (await client.get(f"{METRICS}{metrics['id']}")).status_code == 404
    assert (await client.get(METRICS)).json() == []


# company-shaped pin, see #26
@pytest.mark.asyncio
async def test_delete_company_keeps_other_companies(client):
    keep = await create_company(client, ticker="KEEP", name="Keep Co")
    drop = await create_company(client, ticker="DROP", name="Drop Co")
    kept_metrics = await create_metrics(
        client, keep["id"], "2024-12-31T00:00:00Z"
    )

    assert (await client.delete(f"{COMPANIES}{drop['id']}")).status_code == 204

    assert [row["ticker"] for row in (await client.get(COMPANIES)).json()] == [
        "KEEP"
    ]
    assert (
        await client.get(f"{METRICS}{kept_metrics['id']}")
    ).status_code == 200


# company-shaped pin, see #26
@pytest.mark.asyncio
async def test_delete_missing_company_returns_404(client):
    response = await client.delete(f"{COMPANIES}999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Company not found"}


@pytest.mark.asyncio
async def test_create_company_unexpected_error_returns_generic_500(
    client, monkeypatch
):
    def fail(self, company):
        raise RuntimeError("connection string with password=hunter2")

    monkeypatch.setattr(CompanyRepository, "create", fail)

    response = await client.post(
        COMPANIES, json={"name": "Boom Co", "ticker": "BOOM"}
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "hunter2" not in response.text


# company-shaped pin, see #26
@pytest.mark.asyncio
async def test_create_company_business_error_returns_400(client, monkeypatch):
    def reject(self, company):
        raise ValueError("Company name or ticker already exists")

    monkeypatch.setattr(CompanyRepository, "create", reject)

    response = await client.post(
        COMPANIES, json={"name": "Dup Co", "ticker": "DUPE"}
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Company name or ticker already exists"
    }


@pytest.mark.asyncio
async def test_get_missing_metrics_returns_404(client):
    response = await client.get(f"{METRICS}999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Financial metrics not found"}


@pytest.mark.asyncio
async def test_company_metrics_are_listed_newest_period_first(client):
    company = await create_company(client)
    other = await create_company(client, ticker="OTHR", name="Other Co")
    older = await create_metrics(client, company["id"], "2023-12-31T00:00:00Z")
    newer = await create_metrics(client, company["id"], "2024-12-31T00:00:00Z")
    await create_metrics(client, other["id"], "2025-12-31T00:00:00Z")

    response = await client.get(f"{METRICS}company/{company['id']}")

    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [newer["id"], older["id"]]


@pytest.mark.asyncio
async def test_company_metrics_respect_skip_and_limit(client):
    company = await create_company(client)
    for year in (2022, 2023, 2024):
        await create_metrics(client, company["id"], f"{year}-12-31T00:00:00Z")

    response = await client.get(
        f"{METRICS}company/{company['id']}", params={"skip": 1, "limit": 1}
    )

    assert [row["period_end"][:4] for row in response.json()] == ["2023"]


@pytest.mark.asyncio
async def test_company_without_metrics_lists_empty(client):
    company = await create_company(client)

    response = await client.get(f"{METRICS}company/{company['id']}")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_metrics_unexpected_error_returns_generic_500(
    client, monkeypatch
):
    company = await create_company(client)

    def fail(self, metrics):
        raise RuntimeError("driver detail password=hunter2")

    monkeypatch.setattr(FinancialMetricsRepository, "create", fail)

    response = await client.post(
        METRICS,
        json={
            "company_id": company["id"],
            "period_end": "2024-12-31T00:00:00Z",
            "period_type": "annual",
        },
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "hunter2" not in response.text


@pytest.mark.asyncio
async def test_delete_metrics_returns_204_then_404(client):
    company = await create_company(client)
    metrics = await create_metrics(
        client, company["id"], "2024-12-31T00:00:00Z"
    )

    first = await client.delete(f"{METRICS}{metrics['id']}")
    second = await client.delete(f"{METRICS}{metrics['id']}")

    assert first.status_code == 204
    assert second.status_code == 404
    assert second.json() == {"detail": "Financial metrics not found"}
    assert (await client.get(f"{COMPANIES}{company['id']}")).status_code == 200
