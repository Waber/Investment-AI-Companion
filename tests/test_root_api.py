import pytest
from httpx import ASGITransport, AsyncClient

from main import create_app


@pytest.mark.asyncio
async def test_root_returns_project_metadata():
    app = create_app(init_database_on_startup=False)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://127.0.0.1",
    ) as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Welcome to Investment AI Companion API",
        "version": "1.0.0",
        "docs_url": "/docs",
    }
