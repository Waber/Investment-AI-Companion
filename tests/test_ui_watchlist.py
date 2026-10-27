"""The /ui watchlist page and the heart toggle on the detail page.

Rows, companies, and bars are written straight into the test SQLite
database. No market-data provider is called. ``utc_today`` is frozen
so the stale marker does not depend on the day the suite runs.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models.database_models import CompanyDB, PriceBarDB
from app.repositories.watchlist_repository import WatchlistRepository
from app.ui import watchlist_view

TODAY = date(2026, 10, 27)
RETRIEVED = datetime(2026, 10, 27, 6, 0, tzinfo=timezone.utc)
_ORIGIN = "http://127.0.0.1"


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr(watchlist_view, "utc_today", lambda: TODAY)


def _session(client):
    return client.app.state.testing_session_local()


def _company(client, ticker="AAPL", name="Apple Inc.", description=None):
    session = _session(client)
    try:
        row = CompanyDB(
            name=name, ticker=ticker, currency="USD", description=description
        )
        session.add(row)
        session.commit()
        return row.id
    finally:
        session.close()


def _watch(client, company_id, label=None):
    session = _session(client)
    try:
        WatchlistRepository(session).add(company_id, label)
    finally:
        session.close()


def _bars(client, company_id, closes, source="fake"):
    session = _session(client)
    try:
        for day, close in closes:
            session.add(
                PriceBarDB(
                    instrument_id=company_id,
                    bar_date=day,
                    close_price=Decimal(close),
                    currency="USD",
                    source=source,
                    retrieved_at=RETRIEVED,
                )
            )
        session.commit()
    finally:
        session.close()


def _assert_ui_headers(response):
    policy = response.headers["content-security-policy"]
    assert policy == (
        "default-src 'self'; base-uri 'self'; "
        "form-action 'self'; frame-ancestors 'none'"
    )
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_watchlist_lists_price_change_trend_and_date(client):
    company_id = _company(client)
    _watch(client, company_id, label="long term")
    _bars(
        client,
        company_id,
        [(date(2026, 10, 19), "100"), (date(2026, 10, 26), "101.24")],
    )
    response = await client.get("/ui/watchlist")
    assert response.status_code == 200
    html = response.text
    assert "101,24" in html
    assert "+1,24" in html
    assert "<polyline" in html
    assert "26.10.2026" in html
    assert f'href="/ui/instruments/{company_id}"' in html
    assert "long term" in html
    assert "AAPL" in html
    assert "nieaktualne" not in html


@pytest.mark.asyncio
async def test_watchlist_empty_state_links_to_instruments(client):
    response = await client.get("/ui/watchlist")
    assert response.status_code == 200
    assert "Watchlista jest pusta" in response.text
    assert 'href="/ui"' in response.text
    assert "<table" not in response.text


@pytest.mark.asyncio
async def test_watchlist_marks_a_stale_price(client):
    company_id = _company(client)
    _watch(client, company_id)
    _bars(client, company_id, [(date(2026, 9, 28), "10")])
    response = await client.get("/ui/watchlist")
    assert "nieaktualne" in response.text
    assert "Notowanie starsze niż 7 dni" in response.text


@pytest.mark.asyncio
async def test_watchlist_row_without_prices(client):
    company_id = _company(client)
    _watch(client, company_id)
    response = await client.get("/ui/watchlist")
    assert "brak notowań" in response.text
    assert "<polyline" not in response.text
    assert "nieaktualne" not in response.text


@pytest.mark.asyncio
async def test_watchlist_single_bar_has_no_change(client):
    company_id = _company(client)
    _watch(client, company_id)
    _bars(client, company_id, [(date(2026, 10, 26), "42.5")])
    html = (await client.get("/ui/watchlist")).text
    assert "42,50" in html
    change_cell = html.split('data-field="change"', 1)[1].split("</td>", 1)[0]
    assert "—" in change_cell
    assert "%" not in change_cell


@pytest.mark.asyncio
async def test_watchlist_english_strings(client):
    company_id = _company(client)
    _watch(client, company_id)
    _bars(
        client,
        company_id,
        [(date(2026, 9, 21), "10"), (date(2026, 9, 28), "9.5")],
    )
    client.cookies.set("ui_lang", "en")
    html = (await client.get("/ui/watchlist")).text
    assert "<h1>Watchlist</h1>" in html
    assert "Change" in html
    assert "stale" in html
    assert "Sep 28, 2026" in html
    assert "-5.00" in html
    assert "vs Sep 21, 2026" in html


@pytest.mark.asyncio
async def test_watchlist_shows_source_and_synthetic_badge(client):
    company_id = _company(
        client, description="[IAC-DEMO-V2] Synthetic company"
    )
    _watch(client, company_id)
    _bars(client, company_id, [(date(2026, 10, 26), "5")], "[IAC-DEMO-V2]")
    html = (await client.get("/ui/watchlist")).text
    assert "źródło: [IAC-DEMO-V2]" in html
    assert "dane syntetyczne" in html


@pytest.mark.asyncio
async def test_watchlist_headers_nav_and_no_inline_style(client):
    company_id = _company(client)
    _watch(client, company_id)
    _bars(
        client,
        company_id,
        [(date(2026, 10, 19), "1"), (date(2026, 10, 26), "2")],
    )
    response = await client.get("/ui/watchlist")
    _assert_ui_headers(response)
    assert 'href="/ui/watchlist"' in response.text
    assert "style=" not in response.text
    detail = await client.get(f"/ui/instruments/{company_id}")
    assert 'href="/ui/watchlist"' in detail.text
