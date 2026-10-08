"""/api/v1/test-config reports presence only and is gated by DEBUG."""

import pytest

import main
from app.core.config import Settings

SECRET_VALUES = {
    "OPENAI_API_KEY": "sk-test-openai-value",
    "SECRET_KEY": "test-secret-key-value",
    "NEWS_API_KEY": "test-news-value",
    "TWITTER_API_KEY": "test-twitter-value",
}


@pytest.mark.asyncio
async def test_test_config_is_forbidden_without_debug(client, monkeypatch):
    monkeypatch.setattr(
        main, "settings", Settings(_env_file=None, DEBUG=False)
    )

    response = await client.get("/api/v1/test-config")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "This endpoint is only available in debug mode"
    }


@pytest.mark.asyncio
async def test_test_config_reports_presence_without_values(
    client, monkeypatch
):
    configured = Settings(
        _env_file=None,
        DEBUG=True,
        ELASTICSEARCH_URL="http://127.0.0.1:9200",
        **SECRET_VALUES,
    )
    monkeypatch.setattr(main, "settings", configured)

    response = await client.get("/api/v1/test-config")

    assert response.status_code == 200
    body = response.json()
    assert body["required_settings"] == {
        "OPENAI_API_KEY": "✓",
        "SECRET_KEY": "✓",
    }
    assert body["optional_settings"]["NEWS_API_KEY"] == "✓"
    assert body["optional_settings"]["TWITTER_API_KEY"] == "✓"
    assert body["optional_settings"]["ELASTICSEARCH_URL"] == "✓"
    assert body["environment"]["DEBUG"] is True
    for value in SECRET_VALUES.values():
        assert value not in response.text


@pytest.mark.asyncio
async def test_test_config_marks_missing_settings(client, monkeypatch):
    configured = Settings(
        _env_file=None,
        DEBUG=True,
        OPENAI_API_KEY="",
        SECRET_KEY="",
        DATABASE_URL="",
        REDIS_URL="",
    )
    monkeypatch.setattr(main, "settings", configured)

    body = (await client.get("/api/v1/test-config")).json()

    assert body["required_settings"] == {
        "OPENAI_API_KEY": "✗",
        "SECRET_KEY": "✗",
    }
    assert set(body["optional_settings"].values()) == {"✗ (optional)"}
