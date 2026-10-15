"""fetch-company through the collector guard, offline and in fake time."""

import pytest

from app.api.data_collection import get_collector
from app.data_collectors.base import ProviderError, TransientProviderError
from app.data_collectors.guard import GuardPolicy, guard_collector
from tests.collector_stubs import (
    FakeClock,
    ScriptedLookup,
    SpyCollector,
    sourced,
)

FETCH = "/api/v1/data-collection/fetch-company"


def serve(client, inner, **policy):
    """Make fetch-company use one guarded ``inner`` for every request."""
    clock = FakeClock()
    guarded = guard_collector(
        inner,
        GuardPolicy(**policy),
        clock=clock,
        sleep=clock.sleep,
        rand=lambda: 0.0,
    )
    client.app.dependency_overrides[get_collector] = lambda: guarded
    return guarded


@pytest.mark.asyncio
async def test_no_data_through_the_guard_is_404(client):
    inner = ScriptedLookup(None)
    serve(client, inner)

    response = await client.post(FETCH, json={"ticker": "NOPE"})

    assert response.status_code == 404
    assert inner.calls == 1


@pytest.mark.asyncio
async def test_provider_error_through_the_guard_is_502(client):
    inner = ScriptedLookup(ProviderError("down"))
    serve(client, inner)

    response = await client.post(FETCH, json={"ticker": "DOWN"})

    assert response.status_code == 502
    assert response.json() == {"detail": "Data provider error"}
    assert inner.calls == 1


@pytest.mark.asyncio
async def test_exhausted_retries_are_502(client):
    busy = TransientProviderError("busy")
    inner = ScriptedLookup(busy, busy)
    serve(client, inner, max_retries=1)

    response = await client.post(FETCH, json={"ticker": "BUSY"})

    assert response.status_code == 502
    assert response.json() == {"detail": "Data provider error"}
    assert inner.calls == 2


@pytest.mark.asyncio
async def test_retry_success_creates_the_company(client):
    inner = ScriptedLookup(
        TransientProviderError("busy"),
        sourced({"name": "Acme", "currency": "USD"}),
    )
    serve(client, inner)

    response = await client.post(FETCH, json={"ticker": "ACME"})

    assert response.status_code == 200
    assert inner.calls == 2


@pytest.mark.asyncio
async def test_full_rate_limit_is_502(client):
    inner = ScriptedLookup(sourced({"name": "Acme", "currency": "USD"}))
    serve(client, inner, rate_limit_calls=1, rate_limit_max_wait=0)
    first = await client.post(FETCH, json={"ticker": "ACME"})

    response = await client.post(FETCH, json={"ticker": "OTHER"})

    assert first.status_code == 200
    assert response.status_code == 502
    assert response.json() == {"detail": "Data provider error"}
    assert inner.calls == 1


@pytest.mark.asyncio
async def test_repeat_fetch_is_served_from_the_cache(client):
    inner = SpyCollector()
    serve(client, inner)

    first = await client.post(FETCH, json={"ticker": "DEMO_PL_TECH"})
    second = await client.post(FETCH, json={"ticker": "DEMO_PL_TECH"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert inner.calls == [("fetch_company_info", "DEMO_PL_TECH")]
