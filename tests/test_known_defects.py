"""Same period_end instant with another UTC offset is a duplicate (#20).

QA pinned this case as a strict xfail. The marker is removed in the fix:
the repository normalizes the instant to aware UTC before the uniqueness
check. PostgreSQL coverage of this case waits for issue #9. The other
known-defect cases stay with issues #18, #19, and #21.
"""

import pytest

COMPANIES = "/api/v1/companies/"
METRICS = "/api/v1/financial-metrics/"


@pytest.mark.asyncio
async def test_same_instant_with_other_offset_is_a_duplicate(client):
    company = (
        await client.post(COMPANIES, json={"name": "TZ", "ticker": "TZCO"})
    ).json()
    base = {"company_id": company["id"], "period_type": "annual"}
    first = await client.post(
        METRICS, json={**base, "period_end": "2025-12-31T00:00:00Z"}
    )
    assert first.status_code == 201

    response = await client.post(
        METRICS, json={**base, "period_end": "2025-12-31T02:00:00+02:00"}
    )

    assert response.status_code == 400
