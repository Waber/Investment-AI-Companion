"""Default provider wiring and the placeholder metrics endpoint."""

import pytest


# company-shaped pin, see #26
@pytest.mark.asyncio
async def test_fetch_financial_metrics_is_a_documented_placeholder(client):
    response = await client.post(
        "/api/v1/data-collection/fetch-financial-metrics",
        json={"ticker": "AAPL"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "This endpoint is not yet implemented",
        "ticker": "AAPL",
    }
