"""DATA_COLLECTOR setting, the get_collector dependency and the guard."""

import os
import socket
import tempfile

import pytest
from pydantic import ValidationError

from app.api.data_collection import get_collector, reset_collector
from app.core.config import Settings, settings
from app.data_collectors import yahoo_finance
from app.data_collectors.base import FundAttributes, InstrumentLookup
from app.data_collectors.fake import FakeCollector
from app.data_collectors.yahoo_finance import YahooFinanceCollector
from app.repositories.company_repository import CompanyRepository
from tests import network_guard
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
    # The root conftest.py forces the variable before the app is imported.
    assert settings.DATA_COLLECTOR == "fake"


def test_get_collector_returns_the_fake(monkeypatch):
    monkeypatch.setattr(settings, "DATA_COLLECTOR", "fake")

    assert isinstance(get_collector(), FakeCollector)


def test_get_collector_returns_one_guarded_yahoo(monkeypatch):
    monkeypatch.setattr(settings, "DATA_COLLECTOR", "yahoo")

    first = get_collector()

    assert isinstance(first.inner, YahooFinanceCollector)
    assert get_collector() is first
    assert isinstance(first, InstrumentLookup)
    assert not isinstance(first, FundAttributes)


def test_reset_collector_builds_a_new_guarded_yahoo(monkeypatch):
    monkeypatch.setattr(settings, "DATA_COLLECTOR", "yahoo")
    first = get_collector()

    reset_collector()

    assert get_collector() is not first


def test_shared_yahoo_reads_the_guard_settings(monkeypatch):
    monkeypatch.setattr(settings, "DATA_COLLECTOR", "yahoo")
    monkeypatch.setattr(settings, "COLLECTOR_RATE_LIMIT_CALLS", 7)
    monkeypatch.setattr(
        settings, "COLLECTOR_CACHE_TTL_COMPANY_INFO_SECONDS", 0
    )

    policy = get_collector().policy

    assert policy.rate_limit_calls == 7
    assert policy.ttl_company_info == 0


def test_fake_mode_is_not_guarded(monkeypatch):
    monkeypatch.setattr(settings, "DATA_COLLECTOR", "fake")

    assert type(get_collector()) is FakeCollector


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


@pytest.fixture
def offline_network(monkeypatch, block_network):
    """Make it impossible for a guard test to reach the network.

    1. Replace the socket primitives with stand-ins that raise, then
       re-install the guard so it wraps the stand-ins. A call the guard
       lets through reaches a stand-in, never the operating system.
    2. Make curl_cffi (libcurl, which the guard cannot see) raise too.
    3. Remove proxy settings, so no request can be sent to a proxy.
    4. Give yfinance dummy caches, so the developer's real
       ``cookies.db`` is never read.

    Yields the list of stand-ins that were reached. It must stay empty.
    """
    reached = []

    def standin(name):
        def refuse(*args, **kwargs):
            reached.append(name)
            raise RuntimeError(f"stand-in {name} reached")

        return refuse

    for name in ("getaddrinfo", "gethostbyname", "create_connection"):
        monkeypatch.setattr(socket, name, standin(name))
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, standin(name))
    network_guard.install(monkeypatch)

    curl_session = pytest.importorskip("curl_cffi.requests.session")
    curl = pytest.importorskip("curl_cffi.curl")
    monkeypatch.setattr(curl_session.Session, "request", standin("curl"))
    monkeypatch.setattr(curl.Curl, "perform", standin("curl"))

    for name in ("HTTP", "HTTPS", "ALL"):
        monkeypatch.delenv(f"{name}_PROXY", raising=False)
        monkeypatch.delenv(f"{name.lower()}_proxy", raising=False)
    # "*" makes requests and urllib skip system (macOS) proxy settings.
    monkeypatch.setenv("NO_PROXY", "*")
    monkeypatch.setenv("no_proxy", "*")

    from yfinance import cache

    monkeypatch.setattr(
        cache._CookieCacheManager, "_Cookie_cache", cache._CookieCacheDummy()
    )
    monkeypatch.setattr(
        cache._TzCacheManager, "_tz_cache", cache._TzCacheDummy()
    )
    yield reached


def test_guard_blocks_a_non_loopback_connect(offline_network, block_network):
    with pytest.raises(NetworkBlockedError):
        socket.create_connection(("192.0.2.1", 80), timeout=1)

    assert len(block_network) == 1  # recorded, so a swallowed error fails
    assert offline_network == []  # the guard stopped it, not a stand-in
    block_network.clear()


def test_guard_blocks_connect_and_connect_ex(offline_network, block_network):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkBlockedError):
            sock.connect(("192.0.2.1", 80))
        with pytest.raises(NetworkBlockedError):
            sock.connect_ex(("192.0.2.1", 80))
    finally:
        sock.close()
    assert offline_network == []
    block_network.clear()


def test_guard_blocks_dns_lookups(offline_network, block_network):
    with pytest.raises(NetworkBlockedError):
        socket.getaddrinfo("example.com", 80)
    with pytest.raises(NetworkBlockedError):
        socket.gethostbyname("example.com")

    assert len(block_network) == 2
    assert offline_network == []  # the guard stopped both lookups
    block_network.clear()


def test_guard_blocks_a_non_string_host_without_crashing(block_network):
    with pytest.raises(NetworkBlockedError):
        network_guard.refuse_remote((2, 80))
    block_network.clear()


def test_guard_allows_a_loopback_connect():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    try:
        client = socket.create_connection(server.getsockname(), timeout=2)
        client.close()
    finally:
        server.close()


def test_guard_allows_an_ipv6_loopback_connect():
    server = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    try:
        server.bind(("::1", 0))
    except OSError:
        server.close()
        pytest.skip("IPv6 loopback is not available on this machine")
    server.listen(1)
    try:
        client = socket.create_connection(server.getsockname()[:2], timeout=2)
        client.close()
    finally:
        server.close()


def test_guard_allows_a_unix_socket():
    # A short path: AF_UNIX paths are limited to about 100 characters.
    with tempfile.TemporaryDirectory(dir="/tmp") as folder:
        path = os.path.join(folder, "s")
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(path)
        server.listen(1)
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            client.connect(path)
        finally:
            client.close()
            server.close()


def test_yfinance_uses_requests_so_the_guard_can_see_it():
    from yfinance import _http

    assert _http.HAS_CURL_CFFI is False


def test_a_yfinance_call_is_blocked_before_any_network_io(
    offline_network, block_network
):
    # A real yfinance call (no stub on yf.Ticker). Every layer below the
    # guard is a raising stand-in, so this cannot reach the network even
    # if the guard or the curl_cffi fallback regresses. yfinance may
    # swallow the guard's error, so the attempt list is the proof.
    import yfinance as yf

    try:
        yf.Ticker("AAPL").info
    except Exception:
        pass

    assert block_network, "the guard did not see the yfinance request"
    assert offline_network == [], f"reached below the guard: {offline_network}"
    block_network.clear()


def test_every_blocked_attempt_is_recorded(offline_network, block_network):
    try:
        socket.create_connection(("192.0.2.1", 80), timeout=1)
    except Exception:  # code under test may swallow the guard error
        pass

    assert len(block_network) == 1
    assert offline_network == []
    block_network.clear()


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
