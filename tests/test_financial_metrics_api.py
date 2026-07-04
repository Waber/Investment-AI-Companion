import pytest


@pytest.mark.asyncio
async def test_create_financial_metrics_accepts_documented_fields(client):
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
    company_id = company_response.json()["id"]

    metrics_response = await client.post(
        "/api/v1/financial-metrics/",
        json={
            "company_id": company_id,
            "period_end": "2024-12-31T00:00:00Z",
            "period_type": "annual",
            "revenue": 1_000_000.0,
            "net_income": 200_000.0,
            "total_assets": 2_000_000.0,
            "total_liabilities": 800_000.0,
            "total_equity": 1_200_000.0,
            "roe": 0.16,
            "roa": 0.10,
            "gross_margin": 0.42,
            "net_margin": 0.20,
            "current_ratio": 2.1,
            "quick_ratio": 1.4,
            "debt_to_equity": 0.67,
            "debt_to_assets": 0.40,
            "asset_turnover": 0.50,
            "inventory_turnover": 5.0,
            "revenue_growth": 0.12,
            "net_income_growth": 0.08,
            "pe_ratio": 25.0,
            "pb_ratio": 6.0,
            "ev_ebitda": 18.0,
        },
    )

    assert metrics_response.status_code == 201
    created = metrics_response.json()
    assert created["company_id"] == company_id
    assert created["revenue"] == 1_000_000.0
    assert created["net_margin"] == 0.20
    assert created["ev_ebitda"] == 18.0
