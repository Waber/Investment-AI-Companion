"""fetch-company through the collector guard, offline and in fake time."""

import asyncio
import threading
import time

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


@pytest.mark.asyncio
async def test_hung_upstream_does_not_stall_other_routes(client):
    """A burst must not fill the worker pool.

    Two calls per second, a hung provider, 50 distinct tickers and 40
    copies of ACME. Only ``max_inflight`` requests may stay running.
    The rest fail at once. ``/api/v1/companies/`` and ``/ui`` still
    answer while the hung calls are blocked. No network.
    """
    release = threading.Event()
    state = {"inside": 0, "max_inside": 0}
    state_lock = threading.Lock()

    class Hung:
        def fetch_company_info(self, ticker):
            with state_lock:
                state["inside"] += 1
                state["max_inside"] = max(state["max_inside"], state["inside"])
            try:
                assert release.wait(timeout=8)
            finally:
                with state_lock:
                    state["inside"] -= 1
            return sourced({"name": "Held", "currency": "USD"})

    policy = GuardPolicy(
        rate_limit_calls=2,
        rate_limit_period=1,
        rate_limit_max_wait=5,
        max_inflight=4,
        total_deadline=15,
    )
    guarded = guard_collector(Hung(), policy)
    client.app.dependency_overrides[get_collector] = lambda: guarded

    async def fetch(ticker):
        return await client.post(FETCH, json={"ticker": ticker})

    tasks = [asyncio.create_task(fetch(f"T{i:02d}")) for i in range(50)]
    tasks.extend(asyncio.create_task(fetch("ACME")) for _ in range(40))

    deadline = time.monotonic() + 1
    pending = len(tasks)
    while time.monotonic() < deadline:
        pending = sum(not task.done() for task in tasks)
        if pending <= policy.max_inflight:
            break
        await asyncio.sleep(0.05)
    assert pending <= policy.max_inflight

    started = time.monotonic()
    companies = await client.get("/api/v1/companies/")
    page = await client.get("/ui")
    elapsed = time.monotonic() - started

    assert companies.status_code == 200
    assert page.status_code == 200
    assert elapsed < 1
    with guarded._lock:
        tokens = len(guarded._calls)
    held = policy.max_inflight - guarded._inflight._value
    assert tokens <= policy.max_inflight
    assert 0 <= held <= policy.max_inflight
    assert state["max_inside"] <= policy.max_inflight

    release.set()
    responses = await asyncio.wait_for(asyncio.gather(*tasks), timeout=8)
    assert sum(response.status_code == 502 for response in responses) >= 80
    assert all(response.status_code in (200, 502) for response in responses)
    assert state["inside"] == 0
