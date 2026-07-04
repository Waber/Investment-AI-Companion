import pytest

from app.models.database_models import CompanyDB


@pytest.mark.asyncio
async def test_create_and_list_company_persists_website_as_string(client):
    payload = {
        "name": "Acme Corp",
        "ticker": "ACME",
        "sector": "Technology",
        "industry": "Software",
        "website": "https://example.com",
        "country": "USA",
        "exchange": "NASDAQ",
        "currency": "USD",
    }

    create_response = await client.post("/api/v1/companies/", json=payload)

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["ticker"] == "ACME"
    assert created["website"] == "https://example.com/"

    list_response = await client.get("/api/v1/companies/")

    assert list_response.status_code == 200
    companies = list_response.json()
    assert len(companies) == 1
    assert companies[0]["website"] == "https://example.com/"

    db = client.app.state.testing_session_local()
    try:
        stored = db.query(CompanyDB).filter(CompanyDB.ticker == "ACME").one()
        assert stored.website == "https://example.com/"
        assert isinstance(stored.website, str)
    finally:
        db.close()
