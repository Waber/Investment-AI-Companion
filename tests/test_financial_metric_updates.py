from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.database_models import FinancialMetricsDB

METRICS_URL = "/api/v1/financial-metrics/"
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


@pytest_asyncio.fixture
async def metrics_records(client):
    company = await client.post(
        "/api/v1/companies/",
        json={"name": "Acme Corp", "ticker": "ACME"},
    )
    assert company.status_code == 201
    records = []
    for year in (2023, 2024):
        response = await client.post(
            METRICS_URL,
            json={
                "company_id": company.json()["id"],
                "period_end": f"{year}-12-31T00:00:00Z",
                "period_type": "annual",
                **{
                    field: index + 0.5
                    for index, field in enumerate(METRIC_FIELDS, start=1)
                },
            },
        )
        assert response.status_code == 201
        records.append(response.json())
    return records


def database_snapshot(client):
    with client.app.state.testing_session_local() as db:
        rows = db.execute(select(FinancialMetricsDB.__table__)).mappings()
        return {row["id"]: dict(row) for row in rows}


async def assert_readback(client, expected):
    response = await client.get(f"{METRICS_URL}{expected['id']}")
    assert response.status_code == 200
    assert response.json() == expected


async def assert_successful_update(client, records, payload):
    original, unaffected = records
    before = database_snapshot(client)

    response = await client.put(f"{METRICS_URL}{original['id']}", json=payload)

    assert response.status_code == 200, response.text
    updated = response.json()
    # The current API refreshes updated_at even for an empty update.
    # Do not make wall-clock ordering or timestamp precision assumptions.
    assert updated == {
        **original,
        **payload,
        "updated_at": updated["updated_at"],
    }
    await assert_readback(client, updated)
    await assert_readback(client, unaffected)

    expected = {record_id: dict(row) for record_id, row in before.items()}
    expected[original["id"]].update(payload)
    expected[original["id"]]["updated_at"] = datetime.fromisoformat(
        updated["updated_at"]
    )
    assert database_snapshot(client) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("field", METRIC_FIELDS)
@pytest.mark.parametrize(
    "value",
    [
        pytest.param(-12.5, id="replacement"),
        pytest.param(0, id="zero"),
        pytest.param(None, id="explicit-null"),
    ],
)
async def test_partial_update_preserves_omitted_metrics(
    client, metrics_records, field, value
):
    await assert_successful_update(client, metrics_records, {field: value})


@pytest.mark.asyncio
async def test_mixed_update_sets_clears_and_preserves(client, metrics_records):
    await assert_successful_update(
        client,
        metrics_records,
        {"revenue": 0, "net_income": -12.5, "roe": None, "pe_ratio": None},
    )


@pytest.mark.asyncio
async def test_empty_update_preserves_business_fields(client, metrics_records):
    await assert_successful_update(client, metrics_records, {})


@pytest.mark.asyncio
@pytest.mark.parametrize("field", METRIC_FIELDS)
async def test_invalid_string_update_leaves_all_records_unchanged(
    client, metrics_records, field
):
    original, unaffected = metrics_records
    before = database_snapshot(client)
    other_fields = [name for name in METRIC_FIELDS if name != field]

    response = await client.put(
        f"{METRICS_URL}{original['id']}",
        json={
            field: "not-a-number",
            other_fields[0]: 0,
            other_fields[1]: None,
        },
    )

    assert response.status_code == 422, response.text
    errors = response.json()["detail"]
    assert any(error["loc"] == ["body", field] for error in errors)
    await assert_readback(client, original)
    await assert_readback(client, unaffected)
    # Compare every persisted column, including both timestamps.
    assert database_snapshot(client) == before
