"""A volume above the PostgreSQL INTEGER limit is stored.

The column is BIGINT. 3_000_000_000 would be a DataError on INTEGER
and a 500 from the API. This test uses the PostgreSQL client only.
"""

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_postgres_stores_a_volume_of_three_billion(postgres_client):
    created = await postgres_client.post(
        "/api/v1/companies/",
        json={
            "name": "Synthetic volume",
            "ticker": "DEMO_BIG_VOL",
            "currency": "USD",
        },
    )
    assert created.status_code == 201, created.text
    instrument_id = created.json()["id"]
    path = f"/api/v1/instruments/{instrument_id}/prices"
    stored = await postgres_client.post(
        path,
        json={
            "date": "2026-01-05",
            "open": 10.0,
            "high": 12.0,
            "low": 9.0,
            "close": 11.0,
            "volume": 3_000_000_000,
            "currency": "USD",
            "source": "fake",
            "retrieved_at": "2026-09-30T18:00:00Z",
        },
    )
    assert stored.status_code == 201, stored.text
    assert stored.json()["volume"] == 3_000_000_000
    listed = await postgres_client.get(path)
    assert listed.status_code == 200
    assert listed.json()[0]["volume"] == 3_000_000_000
