import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import select

from app.models import financial_metrics as fm
from app.models.database_models import FinancialMetricsDB

METRIC_FIELDS = (
    "revenue",
    "net_income",
    "total_assets",
    "total_liabilities",
    "total_equity",
    "roe",
    "roa",
    "gross_margin",
    "net_margin",
    "current_ratio",
    "quick_ratio",
    "debt_to_equity",
    "debt_to_assets",
    "asset_turnover",
    "inventory_turnover",
    "revenue_growth",
    "net_income_growth",
    "pe_ratio",
    "pb_ratio",
    "ev_ebitda",
)
CREATE_FIELDS = {
    "company_id": 1,
    "period_end": "2024-12-31T00:00:00Z",
    "period_type": "annual",
}
METRICS_URL = "/api/v1/financial-metrics/"
SCHEMAS = (fm.FinancialMetricsCreate, fm.FinancialMetricsUpdate)


@pytest.mark.parametrize("schema", SCHEMAS)
@pytest.mark.parametrize("field", METRIC_FIELDS)
@pytest.mark.parametrize(
    "value",
    [
        float("inf"),
        float("-inf"),
        float("nan"),
        "Infinity",
        "-Infinity",
        "NaN",
    ],
    ids=[
        "inf-number",
        "-inf-number",
        "nan-number",
        "inf-str",
        "-inf-str",
        "nan-str",
    ],
)
def test_metrics_reject_non_finite_values(schema, field, value):
    payload = {**CREATE_FIELDS} if schema is fm.FinancialMetricsCreate else {}
    payload[field] = value

    with pytest.raises(ValidationError) as exc_info:
        schema(**payload)

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert errors[0]["loc"] == (field,)
    assert errors[0]["type"] == "finite_number"


@pytest.mark.parametrize("schema", SCHEMAS)
@pytest.mark.parametrize("field", METRIC_FIELDS)
@pytest.mark.parametrize("value", [-12.5, 0, 12.5, "-12.5", "0", "12.5", None])
def test_metrics_accept_finite_values_and_explicit_none(schema, field, value):
    payload = {**CREATE_FIELDS} if schema is fm.FinancialMetricsCreate else {}
    payload[field] = value

    metrics = schema(**payload)

    actual = getattr(metrics, field)
    if value is None:
        assert actual is None
    else:
        assert isinstance(actual, float)
        assert actual == float(value)
    assert metrics.model_dump(exclude_unset=True)[field] == actual


@pytest.mark.parametrize("schema", SCHEMAS)
def test_metrics_allow_omitted_fields_without_setting_them(schema):
    payload = {**CREATE_FIELDS} if schema is fm.FinancialMetricsCreate else {}

    metrics = schema(**payload)

    for field in METRIC_FIELDS:
        assert getattr(metrics, field) is None
        assert field not in metrics.model_dump(exclude_unset=True)


@pytest_asyncio.fixture
async def created_metrics(client):
    company = await client.post(
        "/api/v1/companies/", json={"name": "Acme Corp", "ticker": "ACME"}
    )
    assert company.status_code == 201
    response = await client.post(
        METRICS_URL,
        json={
            **CREATE_FIELDS,
            "company_id": company.json()["id"],
            "roe": 0.16,
            "revenue": 100.0,
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["POST", "PUT"])
@pytest.mark.parametrize("value", ["Infinity", "-Infinity", "NaN"])
async def test_api_rejects_non_finite_before_persistence(
    client, created_metrics, method, value
):
    query = select(FinancialMetricsDB.__table__)
    with client.app.state.testing_session_local() as db:
        before = db.execute(query).mappings().all()

    payload = {"roe": value, "revenue": -999.0}
    url = METRICS_URL
    if method == "POST":
        payload.update(
            CREATE_FIELDS,
            company_id=created_metrics["company_id"],
            period_end="2025-12-31T00:00:00Z",
        )
    else:
        url += str(created_metrics["id"])

    # Observe regressions as HTTP 500 responses instead of server exceptions.
    async with AsyncClient(
        transport=ASGITransport(app=client.app, raise_app_exceptions=False),
        base_url="http://127.0.0.1",
    ) as request_client:
        response = await request_client.request(method, url, json=payload)

    assert response.status_code == 422, response.text
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "roe"]
    assert error["type"] == "finite_number"
    with client.app.state.testing_session_local() as db:
        after = db.execute(query).mappings().all()
    assert after == before
    listing = await client.get(METRICS_URL)
    assert listing.status_code == 200
    assert listing.json() == [created_metrics]


@pytest.mark.asyncio
async def test_api_update_preserves_finite_and_optional_semantics(
    client, created_metrics
):
    response = await client.put(
        f"{METRICS_URL}{created_metrics['id']}",
        json={"revenue": -12.5, "net_income": 0},
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["revenue"] == -12.5
    assert updated["net_income"] == 0.0
    assert updated["roe"] == created_metrics["roe"]

    response = await client.put(
        f"{METRICS_URL}{created_metrics['id']}", json={"roe": None}
    )
    assert response.status_code == 200
    assert response.json()["roe"] is None
    with client.app.state.testing_session_local() as db:
        stored = db.get(FinancialMetricsDB, created_metrics["id"])
        assert stored.roe is None
        assert stored.revenue == -12.5
        assert stored.net_income == 0.0
    listing = await client.get(METRICS_URL)
    assert listing.status_code == 200
    assert listing.json() == [response.json()]
