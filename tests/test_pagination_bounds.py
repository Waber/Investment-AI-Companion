"""Issue #19: skip and limit are bounded on the three list endpoints.

Before the fix, skip=-1 and limit=-1 were accepted. SQLite treats
LIMIT -1 as "no limit", so one request could read a whole table.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.api.pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT
from app.models.database_models import CompanyDB, FinancialMetricsDB

COMPANIES_URL = "/api/v1/companies/"
METRICS_URL = "/api/v1/financial-metrics/"
COMPANY_METRICS_URL = "/api/v1/financial-metrics/company/{company_id}"


@pytest.fixture(params=["companies", "metrics", "company_metrics"])
def list_url(request, client):
    """The URL of each list endpoint. The test runs once per endpoint."""
    if request.param == "companies":
        return COMPANIES_URL
    if request.param == "metrics":
        return METRICS_URL
    # The company route needs a company id, but an unknown id still
    # returns 200 with an empty list, so no row has to exist.
    return COMPANY_METRICS_URL.format(company_id=1)


async def _get(client, url, query):
    return await client.get(url, params=query)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query, parameter",
    [
        ({"skip": -1}, "skip"),
        ({"limit": -1}, "limit"),
        ({"limit": 0}, "limit"),
        ({"limit": MAX_PAGE_LIMIT + 1}, "limit"),
    ],
)
async def test_out_of_range_values_return_422(
    client, list_url, query, parameter
):
    response = await _get(client, list_url, query)

    assert response.status_code == 422, response.text
    # The app's own 422 handler keeps the standard {"detail": [...]} shape.
    locations = [error["loc"] for error in response.json()["detail"]]
    assert ["query", parameter] in locations


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        {"limit": MAX_PAGE_LIMIT},
        {"skip": 0, "limit": 1},
        {},
    ],
)
async def test_in_range_values_return_200(client, list_url, query):
    response = await _get(client, list_url, query)

    assert response.status_code == 200, response.text
    assert response.json() == []


def _seed_companies(client, count):
    with client.app.state.testing_session_local() as db:
        db.add_all(
            CompanyDB(name=f"Company {i}", ticker=f"T{i}")
            for i in range(count)
        )
        db.commit()


@pytest.mark.asyncio
async def test_default_page_size_is_applied(client):
    assert DEFAULT_PAGE_LIMIT == 100
    _seed_companies(client, DEFAULT_PAGE_LIMIT + 1)

    response = await client.get(COMPANIES_URL)

    assert response.status_code == 200
    assert len(response.json()) == DEFAULT_PAGE_LIMIT


@pytest.mark.asyncio
async def test_default_page_size_for_company_metrics(client):
    _seed_companies(client, 1)
    start = datetime(2000, 1, 1, tzinfo=timezone.utc)
    with client.app.state.testing_session_local() as db:
        company_id = db.query(CompanyDB).one().id
        db.add_all(
            FinancialMetricsDB(
                company_id=company_id,
                period_end=start + timedelta(days=i),
                period_type="annual",
            )
            for i in range(DEFAULT_PAGE_LIMIT + 1)
        )
        db.commit()

    for url in (
        METRICS_URL,
        COMPANY_METRICS_URL.format(company_id=company_id),
    ):
        response = await client.get(url)

        assert response.status_code == 200
        assert len(response.json()) == DEFAULT_PAGE_LIMIT
