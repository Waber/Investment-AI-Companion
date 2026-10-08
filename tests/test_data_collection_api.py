import pytest

from app.api.data_collection import get_yahoo_finance_collector


class FakeYahooFinanceCollector:
    def fetch_company_info(self, ticker):
        return {
            "name": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "description": "Test fixture company",
            "website": "https://www.apple.com",
            "country": "USA",
            "exchange": "NASDAQ",
            "currency": "USD",
        }


@pytest.mark.asyncio
async def test_fetch_company_uses_injected_collector(client):
    client.app.dependency_overrides[get_yahoo_finance_collector] = (
        lambda: FakeYahooFinanceCollector()
    )

    response = await client.post(
        "/api/v1/data-collection/fetch-company",
        json={"ticker": "aapl"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["company_id"] is not None

    companies_response = await client.get("/api/v1/companies/")
    assert companies_response.status_code == 200
    assert companies_response.json()[0]["ticker"] == "AAPL"
