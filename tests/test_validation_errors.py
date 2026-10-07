import json
from dataclasses import dataclass
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from starlette.requests import Request

from app.models.database_models import FinancialMetricsDB
from app.models.financial_metrics import FinancialMetricsUpdate

METRICS_URL = "/api/v1/financial-metrics/"


@pytest_asyncio.fixture
async def populated_metrics(client):
    company = await client.post(
        "/api/v1/companies/",
        json={"name": "Overflow Test", "ticker": "OVER"},
    )
    assert company.status_code == 201
    response = await client.post(
        METRICS_URL,
        json={
            "company_id": company.json()["id"],
            "period_end": "2024-12-31T00:00:00Z",
            "period_type": "annual",
            "revenue": 100.0,
            "net_income": 25.0,
            "roe": 0.16,
        },
    )
    assert response.status_code == 201
    return response.json()


def database_snapshot(client):
    with client.app.state.testing_session_local() as db:
        rows = db.execute(select(FinancialMetricsDB.__table__)).mappings()
        return [dict(row) for row in rows]


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["POST", "PUT"])
@pytest.mark.parametrize("overflow", ["1e400", "-1e400"])
async def test_raw_json_overflow_rejected_without_persistence(
    client, populated_metrics, method, overflow
):
    before = database_snapshot(client)
    url = METRICS_URL
    payload = {"revenue": -999.0, "net_income": None}
    if method == "POST":
        payload.update(
            company_id=populated_metrics["company_id"],
            period_end="2025-12-31T00:00:00Z",
            period_type="annual",
        )
    else:
        url += str(populated_metrics["id"])
    # Raw JSON is required: the HTTP client's JSON encoder rejects infinity.
    content = json.dumps(payload)[:-1] + ', "roe": ' + overflow + "}"
    async with AsyncClient(
        transport=ASGITransport(app=client.app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as request_client:
        response = await request_client.request(
            method,
            url,
            content=content,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422, response.text
        assert list(response.json()) == ["detail"]
        errors = response.json()["detail"]
        assert len(errors) == 1
        assert errors[0]["type"] == "finite_number"
        assert errors[0]["loc"] == ["body", "roe"]
        assert errors[0]["msg"] == "Input should be a finite number"
        expected_input = "-inf" if overflow.startswith("-") else "inf"
        assert errors[0]["input"] == expected_input
        assert database_snapshot(client) == before
        listing = await request_client.get(METRICS_URL)
        assert listing.status_code == 200
        assert listing.json() == [populated_metrics]

        payload["roe"] = 0.25
        valid = await request_client.request(method, url, json=payload)
        assert valid.status_code == (201 if method == "POST" else 200)
        assert valid.json()["roe"] == 0.25
        with client.app.state.testing_session_local() as db:
            stored = db.get(FinancialMetricsDB, valid.json()["id"])
            assert stored.roe == 0.25
            assert stored.revenue == -999.0
            assert stored.net_income is None


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["not-a-number", "Infinity", "NaN"])
async def test_ordinary_validation_unchanged(client, populated_metrics, value):
    response = await client.put(
        f"{METRICS_URL}{populated_metrics['id']}", json={"roe": value}
    )
    assert response.status_code == 422
    with pytest.raises(ValidationError) as exc_info:
        FinancialMetricsUpdate(roe=value)
    errors = exc_info.value.errors()
    for error in errors:
        error["loc"] = ("body", *error["loc"])
    expected = await request_validation_exception_handler(
        Request({"type": "http"}), RequestValidationError(errors)
    )
    assert response.json() == json.loads(expected.body)


@pytest.mark.asyncio
async def test_finite_error_details_match_default_handler(client):
    request = Request({"type": "http"})
    exc = RequestValidationError(
        [
            {
                "type": "custom_error",
                "loc": ("body", "items", 0),
                "msg": "Invalid input",
                "input": {"values": [1.25, -2, None, True, "inf", "1e400"]},
                "ctx": {"limit": Decimal("1.25")},
            },
            {"type": "missing", "loc": ("body", "name"), "msg": "Required"},
        ],
        body={"secret": "do-not-expose"},
    )
    handler = client.app.exception_handlers[RequestValidationError]
    response = await handler(request, exc)
    expected = await request_validation_exception_handler(request, exc)
    assert response.status_code == expected.status_code == 422
    assert response.body == expected.body
    assert b"do-not-expose" not in response.body


@dataclass
class NestedInput:
    values: tuple


@pytest.mark.asyncio
async def test_nonfinite_error_input_and_context_after_encoding(client):
    exc = RequestValidationError(
        [
            {
                "type": "custom_error",
                "loc": ("body", "items", 0),
                "msg": "Invalid input",
                "input": NestedInput((float("inf"), {"x": float("-inf")})),
                "ctx": {"nested": [{"limit": float("nan"), "finite": 1.25}]},
            }
        ],
        body={"secret": "do-not-expose"},
    )
    handler = client.app.exception_handlers[RequestValidationError]
    response = await handler(Request({"type": "http"}), exc)
    assert response.status_code == 422
    assert json.loads(response.body) == {
        "detail": [
            {
                "type": "custom_error",
                "loc": ["body", "items", 0],
                "msg": "Invalid input",
                "input": {"values": ["inf", {"x": "-inf"}]},
                "ctx": {"nested": [{"limit": "nan", "finite": 1.25}]},
            }
        ]
    }
