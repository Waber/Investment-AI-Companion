from contextlib import asynccontextmanager
from unittest.mock import Mock

import pytest
from httpx import ASGITransport, AsyncClient

import main
from app.core import init_db as database_initializer
from app.core.config import Settings

pytestmark = pytest.mark.asyncio


@asynccontextmanager
async def lifespan_client(application):
    # HTTPX's ASGI transport does not run application lifespan events itself.
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application),
            base_url="http://127.0.0.1",
        ) as client:
            yield client


@pytest.fixture
def isolated_startup(monkeypatch):
    monkeypatch.setattr(main, "settings", Settings(_env_file=None))
    engine = object()
    monkeypatch.setattr(database_initializer, "engine", engine)
    create_all = Mock()
    monkeypatch.setattr(
        database_initializer.Base.metadata, "create_all", create_all
    )
    return create_all, engine


async def test_startup_initializes_database_before_serving(isolated_startup):
    create_all, engine = isolated_startup
    application = main.create_app()
    create_all.assert_not_called()

    async with lifespan_client(application) as client:
        create_all.assert_called_once_with(bind=engine)
        assert (await client.get("/")).status_code == 200

    create_all.assert_called_once_with(bind=engine)


async def test_startup_database_failure_propagates(isolated_startup):
    create_all, engine = isolated_startup
    failure = RuntimeError("database unavailable")
    create_all.side_effect = failure

    with pytest.raises(RuntimeError) as raised:
        async with lifespan_client(main.create_app()):
            pytest.fail("Application served despite failed database startup")

    assert raised.value is failure
    create_all.assert_called_once_with(bind=engine)


async def test_disabled_startup_does_not_initialize_database(isolated_startup):
    create_all, _ = isolated_startup
    create_all.side_effect = AssertionError("Database must not be touched")

    application = main.create_app(init_database_on_startup=False)
    async with lifespan_client(application) as client:
        assert (await client.get("/")).status_code == 200

    create_all.assert_not_called()


@pytest.mark.parametrize("method", ["GET", "OPTIONS"])
@pytest.mark.parametrize(
    "origin, allowed",
    [
        ("https://frontend.example", True),
        ("http://localhost:3000", True),
        ("https://untrusted.example", False),
        ("https://frontend.example.evil.example", False),
        ("https://sub.frontend.example", False),
        ("http://frontend.example", False),
        ("https://frontend.example:8443", False),
        ("http://localhost:3001", False),
        ("https://frontend.example/", False),
        ("null", False),
    ],
)
async def test_cors_matches_only_configured_origins(
    isolated_startup, monkeypatch, method, origin, allowed
):
    configured = Settings(
        _env_file=None,
        BACKEND_CORS_ORIGINS=[
            "https://frontend.example",
            "http://localhost:3000",
        ],
    )
    assert [str(value) for value in configured.cors_origins] == [
        "https://frontend.example/",
        "http://localhost:3000/",
    ]
    monkeypatch.setattr(main, "settings", configured)
    headers = {"Origin": origin}
    if method == "OPTIONS":
        headers.update(
            {
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-Research-Token",
            }
        )

    application = main.create_app(init_database_on_startup=False)
    async with lifespan_client(application) as client:
        response = await client.request(method, "/", headers=headers)

    expected_status = 400 if method == "OPTIONS" and not allowed else 200
    assert response.status_code == expected_status
    if allowed:
        assert response.headers["access-control-allow-origin"] == origin
        assert response.headers["access-control-allow-credentials"] == "true"
        assert "origin" in response.headers["vary"].lower()
        if method == "OPTIONS":
            assert "POST" in response.headers["access-control-allow-methods"]
            assert response.headers["access-control-allow-headers"] == (
                "X-Research-Token"
            )
    else:
        assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("method", ["GET", "OPTIONS"])
async def test_empty_cors_list_grants_no_cross_origin_access(
    isolated_startup, method
):
    assert main.settings.cors_origins == []
    headers = {
        "Origin": "https://frontend.example",
        "Access-Control-Request-Method": "GET",
    }

    application = main.create_app(init_database_on_startup=False)
    async with lifespan_client(application) as client:
        response = await client.request(method, "/", headers=headers)

    assert response.status_code == (200 if method == "GET" else 405)
    assert not any(
        name.startswith("access-control-") for name in response.headers
    )
