"""seed_demo marks rows demo in every mode, including --base-url.

The public JSON body still cannot set source or is_synthetic.
A loopback create is marked demo only when it also shows the
seeder proof: the HMAC of this process's SECRET_KEY. An update
ignores that header.
"""

import asyncio
import json
import re
from urllib.parse import urlsplit

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.demo_seed_auth import (
    DEMO_SEED_HEADER,
    demo_seed_authorized,
    demo_seed_token,
)
from app.models.database_models import CompanyDB, FinancialMetricsDB
from scripts import seed_demo as seed


def _token():
    return demo_seed_token(settings.SECRET_KEY)


def _stored(client, model, row_id):
    session = client.app.state.testing_session_local()
    try:
        return session.get(model, row_id)
    finally:
        session.close()


def test_token_is_the_hmac_of_the_secret_and_not_the_secret_itself():
    first = demo_seed_token("a" * 32)
    second = demo_seed_token("a" * 32)
    other = demo_seed_token("b" * 32)
    assert first == second
    assert first != other
    assert settings.SECRET_KEY not in first
    assert len(first) == 64


_HEX = "ab" * 32


@pytest.mark.parametrize(
    ("host", "header", "allowed"),
    [
        ("127.0.0.1", None, False),
        ("127.0.0.1", "demo", False),
        ("127.0.0.1", "1", False),
        ("127.0.0.1", "é" * 64, False),
        ("127.0.0.1", "AB" * 32, False),
        ("203.0.113.5", _HEX, False),
        ("localhost", _HEX, False),
        (None, _HEX, False),
        ("::1", _HEX, True),
        ("127.0.0.1", _HEX, True),
    ],
)
def test_authorization_is_loopback_and_the_exact_token(host, header, allowed):
    assert (
        demo_seed_authorized(
            client_host=host,
            header=header,
            expected_token=_HEX,
        )
        is allowed
    )


@pytest.mark.asyncio
async def test_public_json_cannot_set_source_or_the_synthetic_flag(client):
    response = await client.post(
        "/api/v1/companies/",
        json={
            "name": "Hand Typed",
            "ticker": "HAND1",
            "description": "[IAC-DEMO-V1] typed by hand",
            "source": "demo",
            "is_synthetic": True,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert "source" not in body
    assert "is_synthetic" not in body
    row = _stored(client, CompanyDB, body["id"])
    assert row.is_synthetic is False
    assert row.source == "manual"


@pytest.mark.asyncio
async def test_loopback_seed_header_marks_the_company_and_its_metric(
    client, monkeypatch
):
    """The seeder proof marks a new company and a new metric as demo.

    The page label is the one word demo. A later edit still keeps
    the flag and records source manual. The header cannot turn a
    manual company synthetic.
    """
    monkeypatch.setattr(settings, "DEMO_SEED_ENABLED", True)
    created = await client.post(
        "/api/v1/companies/",
        json={
            "name": "Seeded",
            "ticker": "SEED1",
            "description": "[IAC-DEMO-V2] fixture",
        },
        headers={DEMO_SEED_HEADER: _token()},
    )
    assert created.status_code == 201
    company_id = created.json()["id"]
    company = _stored(client, CompanyDB, company_id)
    assert company.is_synthetic is True
    assert company.source == "demo"

    client.cookies.set("ui_lang", "en")
    detail = await client.get(f"/ui/instruments/{company_id}")
    assert detail.status_code == 200
    assert "synthetic data" in detail.text
    assert re.search(r'data-field="source">\s*demo\s*<', detail.text)

    metric = await client.post(
        "/api/v1/financial-metrics/",
        json={
            "company_id": company_id,
            "period_end": "2024-12-31T00:00:00Z",
            "period_type": "annual",
            "revenue": 1,
        },
        headers={DEMO_SEED_HEADER: _token()},
    )
    assert metric.status_code == 201
    stored_metric = _stored(client, FinancialMetricsDB, metric.json()["id"])
    assert stored_metric.source == "demo"

    edited = await client.put(
        f"/api/v1/companies/{company_id}",
        json={"description": "edited"},
        headers={DEMO_SEED_HEADER: _token()},
    )
    assert edited.status_code == 200
    after = _stored(client, CompanyDB, company_id)
    assert after.is_synthetic is True
    assert after.source == "manual"
    assert after.description == "edited"


@pytest.mark.asyncio
async def test_wrong_token_and_a_remote_peer_stay_manual(client, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_SEED_ENABLED", True)
    wrong = await client.post(
        "/api/v1/companies/",
        json={"name": "Wrong", "ticker": "WRONG1"},
        headers={DEMO_SEED_HEADER: "0" * 64},
    )
    assert wrong.status_code == 201
    row = _stored(client, CompanyDB, wrong.json()["id"])
    assert row.is_synthetic is False
    assert row.source == "manual"

    transport = ASGITransport(app=client.app, client=("203.0.113.5", 9))
    async with AsyncClient(
        transport=transport, base_url="http://127.0.0.1"
    ) as remote:
        remote_response = await remote.post(
            "/api/v1/companies/",
            json={"name": "Remote", "ticker": "FAR01"},
            headers={DEMO_SEED_HEADER: _token()},
        )
    assert remote_response.status_code == 201
    remote_row = _stored(client, CompanyDB, remote_response.json()["id"])
    assert remote_row.is_synthetic is False
    assert remote_row.source == "manual"


def test_demo_seed_enabled_defaults_to_false():
    """Production stays closed. The demo turns the flag on itself."""
    from app.core.config import Settings

    assert Settings.model_fields["DEMO_SEED_ENABLED"].default is False


@pytest.mark.asyncio
async def test_header_is_ignored_when_demo_seed_is_disabled(
    client, monkeypatch
):
    """A valid loopback header stores a manual row while the flag is off."""
    monkeypatch.setattr(settings, "DEMO_SEED_ENABLED", False)
    response = await client.post(
        "/api/v1/companies/",
        json={"name": "Disabled", "ticker": "OFF1"},
        headers={DEMO_SEED_HEADER: _token()},
    )
    assert response.status_code == 201
    row = _stored(client, CompanyDB, response.json()["id"])
    assert row.is_synthetic is False
    assert row.source == "manual"


@pytest.mark.asyncio
async def test_header_is_honored_when_demo_seed_is_enabled(
    client, monkeypatch
):
    monkeypatch.setattr(settings, "DEMO_SEED_ENABLED", True)
    response = await client.post(
        "/api/v1/companies/",
        json={"name": "Enabled", "ticker": "ON1"},
        headers={DEMO_SEED_HEADER: _token()},
    )
    assert response.status_code == 201
    row = _stored(client, CompanyDB, response.json()["id"])
    assert row.is_synthetic is True
    assert row.source == "demo"


@pytest.mark.asyncio
async def test_non_ascii_seed_header_is_a_manual_row_not_a_500(
    client, monkeypatch
):
    """A same-length non-ASCII header must not reach compare_digest.

    httpx refuses a non-ASCII header, so this call is raw ASGI.
    The value is 64 Latin-1 characters, the same length as the
    hex token. The create is 201 and the row stays manual.
    """
    monkeypatch.setattr(settings, "DEMO_SEED_ENABLED", True)
    body = b'{"name":"Odd","ticker":"ODD1"}'
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/companies/",
        "raw_path": b"/api/v1/companies/",
        "query_string": b"",
        "headers": [
            (b"host", b"127.0.0.1"),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"x-iac-demo-seed", ("\u00e9" * 64).encode("latin-1")),
        ],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 80),
    }
    status = {}

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            status["code"] = message["status"]
        elif message["type"] == "http.response.body":
            status["body"] = status.get("body", b"") + message.get("body", b"")

    await client.app(scope, receive, send)
    assert status["code"] == 201
    created = json.loads(status["body"])
    row = _stored(client, CompanyDB, created["id"])
    assert row.is_synthetic is False
    assert row.source == "manual"


@pytest.mark.asyncio
async def test_proxy_headers_downgrade_a_remote_forwarded_for(
    client, monkeypatch
):
    """uvicorn rewrites the peer from X-Forwarded-For.

    The TCP peer is 127.0.0.1 and the header is a remote address.
    ProxyHeadersMiddleware, with the default trusted host
    127.0.0.1, makes request.client that remote address. The row
    stays manual. ``::1`` is not in that default trusted list.
    """
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    monkeypatch.setattr(settings, "DEMO_SEED_ENABLED", True)
    wrapped = ProxyHeadersMiddleware(client.app, trusted_hosts="127.0.0.1")
    body = b'{"name":"Forwarded","ticker":"XFF1"}'
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/companies/",
        "raw_path": b"/api/v1/companies/",
        "query_string": b"",
        "headers": [
            (b"host", b"127.0.0.1"),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"x-forwarded-for", b"203.0.113.5"),
            (b"x-iac-demo-seed", _token().encode("ascii")),
        ],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 80),
    }
    status = {}

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            status["code"] = message["status"]
        elif message["type"] == "http.response.body":
            status["body"] = status.get("body", b"") + message.get("body", b"")

    await wrapped(scope, receive, send)
    assert status["code"] == 201
    created = json.loads(status["body"])
    row = _stored(client, CompanyDB, created["id"])
    assert row.is_synthetic is False
    assert row.source == "manual"


def _enable(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_SEED_ENABLED", True)


async def _remote_post(app, host, ticker, extra_headers):
    """POST one company from a chosen TCP peer. No proxy middleware."""
    transport = ASGITransport(app=app, client=(host, 9))
    async with AsyncClient(
        transport=transport, base_url="http://127.0.0.1"
    ) as remote:
        return await remote.post(
            "/api/v1/companies/",
            json={"name": "Spoof", "ticker": ticker},
            headers={DEMO_SEED_HEADER: _token(), **extra_headers},
        )


@pytest.mark.asyncio
async def test_metric_put_keeps_manual_source_despite_the_header(
    client, monkeypatch
):
    """A valid seed header on metric update does not keep source demo."""
    _enable(monkeypatch)
    company = await client.post(
        "/api/v1/companies/",
        json={"name": "Metric Co", "ticker": "MET1"},
        headers={DEMO_SEED_HEADER: _token()},
    )
    assert company.status_code == 201
    created = await client.post(
        "/api/v1/financial-metrics/",
        json={
            "company_id": company.json()["id"],
            "period_end": "2024-12-31T00:00:00Z",
            "period_type": "annual",
            "revenue": 1,
        },
        headers={DEMO_SEED_HEADER: _token()},
    )
    assert created.status_code == 201
    metric_id = created.json()["id"]
    assert _stored(client, FinancialMetricsDB, metric_id).source == "demo"
    updated = await client.put(
        f"/api/v1/financial-metrics/{metric_id}",
        json={"revenue": 2},
        headers={DEMO_SEED_HEADER: _token()},
    )
    assert updated.status_code == 200
    row = _stored(client, FinancialMetricsDB, metric_id)
    assert row.source == "manual"
    assert row.revenue == 2


@pytest.mark.asyncio
async def test_fetch_company_update_keeps_the_flag_and_records_manual(
    client, monkeypatch
):
    """fetch-company update ignores a valid seed header.

    source becomes manual, which is what every API update records.
    is_synthetic stays the value the row already had.
    """
    from app.api.data_collection import get_collector

    _enable(monkeypatch)
    created = await client.post(
        "/api/v1/companies/",
        json={"name": "Before", "ticker": "FETCH1", "currency": "USD"},
        headers={DEMO_SEED_HEADER: _token()},
    )
    assert created.status_code == 201
    company_id = created.json()["id"]
    before = _stored(client, CompanyDB, company_id)
    assert before.is_synthetic is True
    assert before.source == "demo"

    class _Collector:
        def fetch_company_info(self, ticker):
            from tests.collector_stubs import sourced

            return sourced(
                {
                    "name": "After",
                    "sector": "Healthcare",
                    "industry": "Biotechnology",
                    "description": "Updated provider description",
                    "website": "https://refreshed.example.com/",
                    "country": "Canada",
                    "exchange": "TSX",
                    "currency": "CAD",
                }
            )

    client.app.dependency_overrides[get_collector] = lambda: _Collector()
    try:
        response = await client.post(
            "/api/v1/data-collection/fetch-company",
            json={"ticker": "fetch1"},
            headers={DEMO_SEED_HEADER: _token()},
        )
    finally:
        client.app.dependency_overrides.pop(get_collector, None)
    assert response.status_code == 200
    row = _stored(client, CompanyDB, company_id)
    assert row.is_synthetic is True
    assert row.source == "manual"
    assert row.name == "After"


@pytest.mark.asyncio
async def test_remote_peer_cannot_spoof_loopback_with_forwarded_headers(
    client, monkeypatch
):
    """X-Forwarded-For and X-Real-IP are not the TCP peer."""
    _enable(monkeypatch)
    forwarded = await _remote_post(
        client.app, "203.0.113.5", "XFF1", {"X-Forwarded-For": "127.0.0.1"}
    )
    assert forwarded.status_code == 201
    row = _stored(client, CompanyDB, forwarded.json()["id"])
    assert row.is_synthetic is False
    assert row.source == "manual"

    real_ip = await _remote_post(
        client.app, "203.0.113.5", "REAL1", {"X-Real-IP": "127.0.0.1"}
    )
    assert real_ip.status_code == 201
    other = _stored(client, CompanyDB, real_ip.json()["id"])
    assert other.is_synthetic is False
    assert other.source == "manual"


@pytest.mark.asyncio
async def test_proxy_middleware_ignores_xff_from_a_remote_peer(
    client, monkeypatch
):
    """A remote TCP peer is not in forwarded_allow_ips, so XFF is ignored.

    trusted_hosts is uvicorn's default, 127.0.0.1. The peer is
    203.0.113.5 and claims X-Forwarded-For: 127.0.0.1. The row
    stays manual. ::1 is not in that trusted list either.
    """
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    _enable(monkeypatch)
    wrapped = ProxyHeadersMiddleware(client.app, trusted_hosts="127.0.0.1")
    body = b'{"name":"Remote Proxy","ticker":"RMT1"}'
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/companies/",
        "raw_path": b"/api/v1/companies/",
        "query_string": b"",
        "headers": [
            (b"host", b"127.0.0.1"),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"x-forwarded-for", b"127.0.0.1"),
            (b"x-iac-demo-seed", _token().encode("ascii")),
        ],
        "client": ("203.0.113.5", 9),
        "server": ("203.0.113.5", 80),
    }
    status = {}

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            status["code"] = message["status"]
        elif message["type"] == "http.response.body":
            status["body"] = status.get("body", b"") + message.get("body", b"")

    await wrapped(scope, receive, send)
    assert status["code"] == 201
    created = json.loads(status["body"])
    row = _stored(client, CompanyDB, created["id"])
    assert row.is_synthetic is False
    assert row.source == "manual"


@pytest.mark.asyncio
async def test_ipv6_loopback_with_a_valid_token_is_demo(client, monkeypatch):
    _enable(monkeypatch)
    transport = ASGITransport(app=client.app, client=("::1", 123))
    async with AsyncClient(
        transport=transport, base_url="http://127.0.0.1"
    ) as local:
        response = await local.post(
            "/api/v1/companies/",
            json={"name": "IPv6", "ticker": "IPV61"},
            headers={DEMO_SEED_HEADER: _token()},
        )
    assert response.status_code == 201
    row = _stored(client, CompanyDB, response.json()["id"])
    assert row.is_synthetic is True
    assert row.source == "demo"


@pytest.mark.parametrize(
    "header",
    [
        pytest.param("a" * 63, id="63-chars"),
        pytest.param("a" * 65, id="65-chars"),
        pytest.param("", id="empty"),
        pytest.param("padded", id="whitespace-padded"),
        pytest.param("upper", id="upper-cased-real-token"),
    ],
)
def test_token_shape_is_rejected_before_compare(header):
    """Only the 64-lowercase-hex shape reaches compare_digest.

    The upper-cased real token is the same digest with A-F. The
    regex rejects it. A later compare would also fail, but the
    shape check is what keeps a non-hex value out of that call.
    """
    expected = _token()
    if header == "padded":
        header = f" {expected} "
    elif header == "upper":
        header = expected.upper()
    assert (
        demo_seed_authorized(
            client_host="127.0.0.1",
            header=header,
            expected_token=expected,
        )
        is False
    )


@pytest.mark.asyncio
async def test_upper_cased_token_is_a_manual_http_row(client, monkeypatch):
    _enable(monkeypatch)
    response = await client.post(
        "/api/v1/companies/",
        json={"name": "Upper", "ticker": "UPPR1"},
        headers={DEMO_SEED_HEADER: _token().upper()},
    )
    assert response.status_code == 201
    row = _stored(client, CompanyDB, response.json()["id"])
    assert row.is_synthetic is False
    assert row.source == "manual"


@pytest.mark.asyncio
async def test_metric_json_cannot_set_source_or_synthetic(client):
    """Extra JSON names are not fields. The row stays manual."""
    company = await client.post(
        "/api/v1/companies/",
        json={"name": "Plain", "ticker": "PLAIN1"},
    )
    assert company.status_code == 201
    response = await client.post(
        "/api/v1/financial-metrics/",
        json={
            "company_id": company.json()["id"],
            "period_end": "2024-12-31T00:00:00Z",
            "period_type": "annual",
            "revenue": 3,
            "source": "demo",
            "is_synthetic": True,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert "source" not in body
    assert "is_synthetic" not in body
    row = _stored(client, FinancialMetricsDB, body["id"])
    assert row.source == "manual"


def test_valid_token_is_compared_with_compare_digest(monkeypatch):
    """The success path calls hmac.compare_digest. A bad shape does not."""
    expected = _token()
    calls = []
    real = __import__("hmac").compare_digest

    def spy(left, right):
        calls.append((left, right))
        return real(left, right)

    monkeypatch.setattr("app.demo_seed_auth.hmac.compare_digest", spy)
    assert (
        demo_seed_authorized(
            client_host="127.0.0.1",
            header=expected,
            expected_token=expected,
        )
        is True
    )
    assert calls == [(expected, expected)]
    calls.clear()
    assert (
        demo_seed_authorized(
            client_host="127.0.0.1",
            header=expected.upper(),
            expected_token=expected,
        )
        is False
    )
    assert calls == []


def _asgi_from_urllib(app, request):
    """Run one urllib request through the ASGI app. No socket is opened."""
    parsed = urlsplit(request.full_url)
    headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in request.header_items()
    ]
    if not any(key == b"host" for key, _value in headers):
        headers.append((b"host", b"127.0.0.1"))
    body = request.data or b""
    if isinstance(body, str):
        body = body.encode("utf-8")
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": request.get_method(),
        "scheme": "http",
        "path": parsed.path,
        "raw_path": parsed.path.encode("ascii"),
        "query_string": parsed.query.encode("ascii"),
        "headers": headers,
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 80),
    }
    status = {}

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            status["code"] = message["status"]
        elif message["type"] == "http.response.body":
            status["body"] = status.get("body", b"") + message.get("body", b"")

    async def call():
        await app(scope, receive, send)

    asyncio.run(call())

    class Response:
        def __init__(self):
            self.status = status["code"]
            self._body = status.get("body", b"")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return self._body

    return Response()


def test_seed_demo_base_url_marks_rows_through_asgi(monkeypatch):
    """seed_demo --base-url, with the real client, against the ASGI app.

    urllib is pointed at the in-process app. Nothing is bound to a port.
    """
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core.database import Base, create_db_engine, get_db
    from main import create_app

    _enable(monkeypatch)
    engine = create_db_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app = create_app(init_database_on_startup=False)
    app.dependency_overrides[get_db] = override_get_db

    class Opener:
        def open(self, request, timeout):
            return _asgi_from_urllib(app, request)

    monkeypatch.setattr(seed.http, "build_opener", lambda *args: Opener())
    summary = seed.seed_demo(
        seed.load_fixture(),
        seed.HttpClient("http://127.0.0.1:8081"),
        apply=True,
    )
    assert summary["companies"]["created"] == 6
    assert summary["metrics"]["created"] == 20
    session = session_factory()
    try:
        companies = session.query(CompanyDB).all()
        metrics = session.query(FinancialMetricsDB).all()
        assert {row.is_synthetic for row in companies} == {True}
        assert {row.source for row in companies} == {"demo"}
        assert {row.source for row in metrics} == {"demo"}
    finally:
        session.close()
        engine.dispose()


def test_http_client_sends_the_seed_header_only_on_creates(monkeypatch):
    seen = {}

    class Response:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b"{}"

    class Opener:
        def open(self, request, timeout):
            seen["request"] = request
            return Response()

    monkeypatch.setattr(seed.http, "build_opener", lambda *args: Opener())
    client = seed.HttpClient("http://127.0.0.1:8081")
    client.request("POST", "/api/v1/companies/", {"name": "A", "ticker": "A"})
    # urllib stores header names with str.capitalize, so the lookup
    # key is "X-iac-demo-seed". The bytes on the wire are the same
    # header. HTTP treats the name as case-insensitive.
    stored_name = DEMO_SEED_HEADER.capitalize()
    assert seen["request"].headers.get(stored_name) == _token()
    assert json.loads(seen["request"].data) == {"name": "A", "ticker": "A"}

    Response.status = 200

    def _read(self):
        return b"[]"

    Response.read = _read
    client.request("GET", "/api/v1/companies/")
    assert stored_name not in seen["request"].headers
