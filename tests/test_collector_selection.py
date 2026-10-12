"""DATA_COLLECTOR setting, the get_collector dependency and the guard."""

import socket

import pytest
from pydantic import ValidationError

from app.api.data_collection import get_collector
from app.core.config import Settings, settings
from app.data_collectors import yahoo_finance
from app.data_collectors.fake import FakeCollector
from app.data_collectors.yahoo_finance import YahooFinanceCollector
from app.repositories.company_repository import CompanyRepository
from tests.network_guard import NetworkBlockedError

FETCH_URL = "/api/v1/data-collection/fetch-company"


def build_settings(monkeypatch, **env):
    """Settings from the environment only, never from a developer .env."""
    monkeypatch.delenv("DATA_COLLECTOR", raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return Settings(_env_file=None)


def test_data_collector_defaults_to_yahoo(monkeypatch):
    assert build_settings(monkeypatch).DATA_COLLECTOR == "yahoo"


def test_data_collector_is_stripped_and_lowercased(monkeypatch):
    built = build_settings(monkeypatch, DATA_COLLECTOR=" Fake ")

    assert built.DATA_COLLECTOR == "fake"


def test_unknown_data_collector_fails_settings(monkeypatch):
    with pytest.raises(ValidationError):
        build_settings(monkeypatch, DATA_COLLECTOR="other")


def test_tests_run_with_the_fake_collector():
    # tests/conftest.py forces the variable before the app is imported.
    assert settings.DATA_COLLECTOR == "fake"


def test_get_collector_returns_the_fake(monkeypatch):
    monkeypatch.setattr(settings, "DATA_COLLECTOR", "fake")

    assert isinstance(get_collector(), FakeCollector)


def test_get_collector_returns_yahoo(monkeypatch):
    monkeypatch.setattr(settings, "DATA_COLLECTOR", "yahoo")

    assert isinstance(get_collector(), YahooFinanceCollector)


def company_rows(client):
    session = client.app.state.testing_session_local()
    try:
        return CompanyRepository(session).get_all()
    finally:
        session.close()


@pytest.mark.asyncio
async def test_fetch_company_with_the_fake_creates_then_updates(client):
    first = await client.post(FETCH_URL, json={"ticker": "DEMO_PL_TECH"})
    second = await client.post(FETCH_URL, json={"ticker": "DEMO_PL_TECH"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["company_id"] == first.json()["company_id"]
    rows = company_rows(client)
    assert len(rows) == 1
    assert rows[0].name == "Demo Vistula Software"
    assert rows[0].description.startswith("[IAC-DEMO-V1]")


@pytest.mark.asyncio
async def test_fetch_company_with_the_fake_creates_a_fund_row(client):
    response = await client.post(FETCH_URL, json={"ticker": "DEMO_ETF_WORLD"})

    assert response.status_code == 200
    rows = company_rows(client)
    assert [row.ticker for row in rows] == ["DEMO_ETF_WORLD"]
    assert rows[0].description.startswith("[IAC-DEMO-V1]")


@pytest.mark.asyncio
async def test_fetch_company_with_the_fake_returns_404_for_unknown(client):
    response = await client.post(FETCH_URL, json={"ticker": "NOPE_XYZ"})

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Company with ticker NOPE_XYZ not found at the data provider"
    )
    assert company_rows(client) == []


def test_guard_blocks_a_non_loopback_connect():
    with pytest.raises(NetworkBlockedError):
        socket.create_connection(("192.0.2.1", 80), timeout=1)


def test_guard_blocks_connect_and_connect_ex():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkBlockedError):
            sock.connect(("192.0.2.1", 80))
        with pytest.raises(NetworkBlockedError):
            sock.connect_ex(("192.0.2.1", 80))
    finally:
        sock.close()


def test_guard_allows_a_loopback_connect():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    try:
        client = socket.create_connection(server.getsockname(), timeout=2)
        client.close()
    finally:
        server.close()


class NearEmptyTicker:
    """What yfinance 1.7 returns for an unknown ticker (no exception)."""

    def __init__(self, symbol):
        self.info = {"trailingPegRatio": None}


@pytest.mark.asyncio
async def test_yahoo_near_empty_info_is_a_404_not_a_502(client, monkeypatch):
    monkeypatch.setattr(settings, "DATA_COLLECTOR", "yahoo")
    monkeypatch.setattr(yahoo_finance.yf, "Ticker", NearEmptyTicker)

    response = await client.post(FETCH_URL, json={"ticker": "NOPE"})

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Company with ticker NOPE not found at the data provider"
    )
