"""Issue #19: skip and limit are bounded on the three list endpoints.

Before the fix, skip=-1 and limit=-1 were accepted. SQLite treats
LIMIT -1 as "no limit", so one request could read a whole table.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.api.pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, MAX_SKIP
from app.models.database_models import CompanyDB, FinancialMetricsDB

COMPANIES_URL = "/api/v1/companies/"
METRICS_URL = "/api/v1/financial-metrics/"
COMPANY_METRICS_URL = "/api/v1/financial-metrics/company/{company_id}"


def _seed_companies(client, count):
    with client.app.state.testing_session_local() as db:
        db.add_all(
            CompanyDB(name=f"Company {i}", ticker=f"T{i}")
            for i in range(count)
        )
        db.commit()


@pytest.fixture(params=["companies", "metrics", "company_metrics"])
def list_url(request, client):
    """The URL of each list endpoint. The test runs once per endpoint."""
    if request.param == "companies":
        return COMPANIES_URL
    if request.param == "metrics":
        return METRICS_URL
    # The company route needs a real company, so the path is valid.
    _seed_companies(client, 1)
    with client.app.state.testing_session_local() as db:
        company_id = db.query(CompanyDB).one().id
    return COMPANY_METRICS_URL.format(company_id=company_id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query, parameter",
    [
        ({"skip": -1}, "skip"),
        ({"skip": MAX_SKIP + 1}, "skip"),
        ({"limit": -1}, "limit"),
        ({"limit": 0}, "limit"),
        ({"limit": MAX_PAGE_LIMIT + 1}, "limit"),
    ],
)
async def test_negative_pagination_is_rejected(
    client, list_url, query, parameter
):
    response = await client.get(list_url, params=query)

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
        {"skip": MAX_SKIP},
        {},
    ],
)
async def test_in_range_values_return_200(client, list_url, query):
    response = await client.get(list_url, params=query)

    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_default_page_size_is_applied(client):
    assert DEFAULT_PAGE_LIMIT == 100
    _seed_companies(client, DEFAULT_PAGE_LIMIT + 1)

    response = await client.get(COMPANIES_URL)

    assert response.status_code == 200
    assert len(response.json()) == DEFAULT_PAGE_LIMIT


@pytest.mark.asyncio
async def test_default_page_size_is_applied_to_financial_metrics_lists(
    client,
):
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

    urls = (METRICS_URL, COMPANY_METRICS_URL.format(company_id=company_id))
    for url in urls:
        response = await client.get(url)

        assert response.status_code == 200
        assert len(response.json()) == DEFAULT_PAGE_LIMIT


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/companies/",
        "/api/v1/financial-metrics/",
        "/api/v1/financial-metrics/company/{company_id}",
    ],
)
async def test_openapi_documents_the_bounds(client, path):
    schema = (await client.get("/api/v1/openapi.json")).json()
    parameters = {
        parameter["name"]: parameter["schema"]
        for parameter in schema["paths"][path]["get"]["parameters"]
    }

    assert parameters["skip"]["minimum"] == 0
    assert parameters["skip"]["maximum"] == MAX_SKIP
    assert parameters["skip"]["default"] == 0
    assert parameters["limit"]["minimum"] == 1
    assert parameters["limit"]["maximum"] == MAX_PAGE_LIMIT
    assert parameters["limit"]["default"] == DEFAULT_PAGE_LIMIT
