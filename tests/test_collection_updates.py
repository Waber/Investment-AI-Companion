from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.api.data_collection import get_collector
from app.models.database_models import CompanyDB, FinancialMetricsDB
from tests.collector_stubs import sourced

COLLECTION_URL = "/api/v1/data-collection/fetch-company"
PROVIDER_FIELDS = {
    "name": "Refreshed Corp",
    "sector": "Healthcare",
    "industry": "Biotechnology",
    "description": "Updated provider description",
    "website": "https://refreshed.example.com/",
    "country": "Canada",
    "exchange": "TSX",
    "currency": "CAD",
}


class RecordingCollector:
    def __init__(self):
        self.result = dict(PROVIDER_FIELDS)
        self.calls = []

    def fetch_company_info(self, ticker):
        self.calls.append(ticker)
        if self.result is None:
            return None
        return sourced(self.result)


@pytest.fixture
def collector(client):
    fake = RecordingCollector()
    client.app.dependency_overrides[get_collector] = lambda: fake
    return fake


def database_snapshot(client):
    # Fresh sessions inspect committed rows rather than cached ORM objects.
    with client.app.state.testing_session_local() as db:
        return {
            model.__tablename__: {
                row["id"]: dict(row)
                for row in db.execute(select(model.__table__)).mappings()
            }
            for model in (CompanyDB, FinancialMetricsDB)
        }


@pytest_asyncio.fixture
async def records(client):
    company_ids = []
    metrics = []
    for name, ticker in [("Original Corp", "ORIG"), ("Other Corp", "OTHER")]:
        response = await client.post(
            "/api/v1/companies/",
            json={
                "name": name,
                "ticker": ticker,
                "sector": "Technology",
                "industry": "Software",
                "description": f"Original {name}",
                "website": "https://original.example.com/",
                "country": "Poland",
                "exchange": "WSE",
                "currency": "PLN",
            },
        )
        assert response.status_code == 201
        company_id = response.json()["id"]
        company_ids.append(company_id)
        response = await client.post(
            "/api/v1/financial-metrics/",
            json={
                "company_id": company_id,
                "period_end": "2024-12-31T00:00:00Z",
                "period_type": "annual",
                "revenue": 123.5,
                "net_income": -10,
                "pe_ratio": 0,
            },
        )
        assert response.status_code == 201
        metrics.append(response.json())

    # Non-default metadata makes accidental identity resets observable.
    with client.app.state.testing_session_local() as db:
        original = db.get(CompanyDB, company_ids[0])
        original.created_at = datetime(2020, 1, 2)
        original.updated_at = datetime(2021, 2, 3)
        original.last_data_update = datetime(2022, 3, 4)
        original.is_active = False
        db.commit()

    companies = []
    for company_id in company_ids:
        response = await client.get(f"/api/v1/companies/{company_id}")
        assert response.status_code == 200
        companies.append(response.json())
    return companies, metrics


async def assert_readback(client, companies, metrics):
    for url, rows in (
        ("/api/v1/companies/", companies),
        ("/api/v1/financial-metrics/", metrics),
    ):
        for row in rows:
            response = await client.get(f"{url}{row['id']}")
            assert response.status_code == 200
            assert response.json() == row


async def assert_refresh(client, records, before):
    companies, metrics = records
    original, other = companies
    response = await client.post(COLLECTION_URL, json={"ticker": "orig"})
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    assert response.json()["company_id"] == original["id"]

    response = await client.get(f"/api/v1/companies/{original['id']}")
    assert response.status_code == 200
    refreshed = response.json()
    assert refreshed == {
        **original,
        **PROVIDER_FIELDS,
        "updated_at": refreshed["updated_at"],
    }
    await assert_readback(client, [refreshed, other], metrics)

    expected = {
        **before,
        "companies": {
            **before["companies"],
            original["id"]: {
                **before["companies"][original["id"]],
                **PROVIDER_FIELDS,
                "updated_at": datetime.fromisoformat(refreshed["updated_at"]),
            },
        },
    }
    assert database_snapshot(client) == expected


@pytest.mark.asyncio
async def test_repeated_refresh_updates_existing_company_without_duplicates(
    client, records, collector
):
    before = database_snapshot(client)
    for _ in range(2):
        await assert_refresh(client, records, before)
    assert collector.calls == ["ORIG", "ORIG"]


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_result", [None, {}], ids=["none", "empty"])
@pytest.mark.parametrize("ticker", ["orig", "unknown"])
async def test_missing_provider_data_preserves_entire_database(
    client, records, collector, provider_result, ticker
):
    collector.result = provider_result
    before = database_snapshot(client)

    response = await client.post(COLLECTION_URL, json={"ticker": ticker})

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == (
        f"Company with ticker {ticker.upper()} not found at the data provider"
    )
    assert collector.calls == [ticker.upper()]
    await assert_readback(client, *records)
    assert database_snapshot(client) == before


@pytest.mark.asyncio
async def test_refresh_may_reuse_another_companys_name(
    client, records, collector
):
    """Fetching ORIG may store the same name OTHER already has.

    The ticker stays ORIG. The other row is not changed. A later
    refresh can still replace that shared name.
    """
    companies, metrics = records
    original, other = companies
    collector.result["name"] = other["name"]

    response = await client.post(COLLECTION_URL, json={"ticker": "orig"})

    assert response.status_code == 200, response.text
    fetched = await client.get(f"/api/v1/companies/{original['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == other["name"]
    assert fetched.json()["ticker"] == "ORIG"
    unchanged = await client.get(f"/api/v1/companies/{other['id']}")
    assert unchanged.json() == other
    await assert_readback(client, [fetched.json(), other], metrics)

    collector.result = dict(PROVIDER_FIELDS)
    before = database_snapshot(client)
    await assert_refresh(client, records, before)
    assert collector.calls == ["ORIG", "ORIG"]
