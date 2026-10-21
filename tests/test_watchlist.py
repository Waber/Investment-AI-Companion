"""Watchlist repository, read/write models, setting, and HTTP API."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.database import Base, create_db_engine
from app.models.database_models import WatchlistItemDB
from app.models.watchlist import (
    WATCHLIST_LABEL_MAX_LENGTH,
    WatchlistItemCreate,
)
from app.repositories.watchlist_repository import WatchlistRepository
from tests.watchlist_checks import (
    assert_add_is_idempotent_and_keeps_the_first_label,
    assert_blank_label_is_stored_as_null,
    assert_company_update_leaves_the_watchlist_row,
    assert_list_orders_by_added_at_then_id,
    assert_missing_company_is_raised_outside_the_handler,
    assert_model_declares_cascade_and_one_row_per_company,
    assert_race_returns_the_existing_row,
    assert_remove_is_bool_and_company_delete_cascades,
    assert_unrelated_integrity_error_is_raised_outside_the_handler,
)

SECRET = "test-secret-key-for-pytest-0123456789"


@pytest.fixture
def session():
    # The application engine enables SQLite foreign keys. A plain
    # create_engine would let a missing company be inserted.
    engine = create_db_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, autoflush=False)()
    yield db
    db.close()
    engine.dispose()


def test_model_declares_cascade_and_one_row_per_company():
    assert_model_declares_cascade_and_one_row_per_company()
    column = WatchlistItemDB.__table__.columns["label"]
    assert column.type.length == WATCHLIST_LABEL_MAX_LENGTH
    assert column.nullable is True


def test_create_model_strips_the_label_and_rejects_a_long_one():
    created = WatchlistItemCreate(company_id=1, label="  core  ")
    assert created.label == "core"
    blank = WatchlistItemCreate(company_id=1, label="   ")
    assert blank.label is None
    omitted = WatchlistItemCreate(company_id=1)
    assert omitted.label is None
    with pytest.raises(ValidationError):
        WatchlistItemCreate(company_id=0, label="x")
    with pytest.raises(ValidationError):
        WatchlistItemCreate(company_id=1, label="x" * 81)


@pytest.mark.parametrize(
    "label",
    [
        "\x00",
        "A\x00B",
        "\x7f",
        "\u202a",
        "\u202e",
        "\u2066",
        "\u2069",
        "\u200e",
        "\u200f",
        "A\u200eB",
        "A\u200fB",
    ],
)
def test_create_model_rejects_controls_and_bidi(label):
    """Cc (including NUL) and the listed bidi controls are invalid.

    U+200E and U+200F are format characters, and they are still
    rejected. A label that is only one of them is not stored as null.
    """
    with pytest.raises(ValidationError) as caught:
        WatchlistItemCreate(company_id=1, label=label)
    assert caught.value.errors()[0]["loc"] == ("label",)


@pytest.mark.parametrize(
    "label",
    [
        "",
        "   ",
        "\u200b",
        "\ufeff",
        " \u200b ",
        "\u200c\u200b",
        "\ufeff\u200b",
    ],
)
def test_create_model_treats_blank_and_format_only_labels_as_null(label):
    """Whitespace and Cf-only notes are the same as omitting the label."""
    created = WatchlistItemCreate(company_id=1, label=label)
    assert created.label is None


def test_create_model_keeps_a_format_character_beside_a_letter():
    created = WatchlistItemCreate(company_id=1, label=" A\u200bB ")
    assert created.label == "A\u200bB"
    kept = WatchlistItemCreate(company_id=1, label="A\u200cB")
    assert kept.label == "A\u200cB"


def test_stale_price_days_defaults_to_seven(monkeypatch):
    monkeypatch.delenv("watchlist_stale_price_days", raising=False)
    built = Settings(_env_file=None, SECRET_KEY=SECRET)
    assert built.watchlist_stale_price_days == 7


def test_stale_price_days_reads_the_environment(monkeypatch):
    monkeypatch.setenv("watchlist_stale_price_days", "3")
    built = Settings(_env_file=None, SECRET_KEY=SECRET)
    assert built.watchlist_stale_price_days == 3
    monkeypatch.setenv("watchlist_stale_price_days", "nope")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, SECRET_KEY=SECRET)


@pytest.mark.parametrize("days", [0, -1])
def test_stale_price_days_rejects_non_positive(monkeypatch, days):
    monkeypatch.delenv("watchlist_stale_price_days", raising=False)
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            SECRET_KEY=SECRET,
            watchlist_stale_price_days=days,
        )


def test_add_is_idempotent_and_keeps_the_first_label(session):
    assert_add_is_idempotent_and_keeps_the_first_label(session)


def test_blank_label_is_stored_as_null(session):
    assert_blank_label_is_stored_as_null(session)


def test_race_returns_the_existing_row(monkeypatch, session):
    assert_race_returns_the_existing_row(monkeypatch, session)


def test_missing_company_is_raised_outside_the_handler(session):
    assert_missing_company_is_raised_outside_the_handler(session)


def test_unrelated_integrity_error_is_raised_outside_the_handler(
    monkeypatch, session
):
    assert_unrelated_integrity_error_is_raised_outside_the_handler(
        monkeypatch, session
    )


def test_list_orders_by_added_at_then_id(session):
    assert_list_orders_by_added_at_then_id(session)


def test_remove_is_bool_and_company_delete_cascades(session):
    assert_remove_is_bool_and_company_delete_cascades(session)


def test_company_update_leaves_the_watchlist_row(session):
    assert_company_update_leaves_the_watchlist_row(session)


async def _company(client, ticker):
    response = await client.post(
        "/api/v1/companies/",
        json={"name": ticker + " Co", "ticker": ticker},
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_watchlist_api_adds_lists_and_removes(client):
    missing = await client.post(
        "/api/v1/watchlist/", json={"company_id": 999, "label": "nope"}
    )
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Company not found"

    first_id = await _company(client, "AAA")
    second_id = await _company(client, "BBB")
    created = await client.post(
        "/api/v1/watchlist/",
        json={"company_id": first_id, "label": "  core  "},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["company_id"] == first_id
    assert body["label"] == "core"
    assert body["added_at"].endswith("Z") or body["added_at"].endswith(
        "+00:00"
    )
    parsed = datetime.fromisoformat(body["added_at"].replace("Z", "+00:00"))
    assert parsed.utcoffset().total_seconds() == 0

    again = await client.post(
        "/api/v1/watchlist/",
        json={"company_id": first_id, "label": "other"},
    )
    assert again.status_code == 200
    assert again.json()["id"] == body["id"]
    assert again.json()["label"] == "core"

    second = await client.post(
        "/api/v1/watchlist/", json={"company_id": second_id}
    )
    assert second.status_code == 201

    db = client.app.state.testing_session_local()
    try:
        rows = (
            db.query(WatchlistItemDB).order_by(WatchlistItemDB.id.asc()).all()
        )
        rows[0].added_at = datetime(2024, 6, 1, tzinfo=timezone.utc)
        rows[1].added_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        db.commit()
        second_row_id = rows[1].id
        first_row_id = rows[0].id
    finally:
        db.close()

    listed = await client.get("/api/v1/watchlist/")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [
        second_row_id,
        first_row_id,
    ]

    removed = await client.delete(f"/api/v1/watchlist/{first_id}")
    assert removed.status_code == 204
    absent = await client.delete(f"/api/v1/watchlist/{first_id}")
    assert absent.status_code == 404
    assert absent.json()["detail"] == "Not on the watchlist"
    unknown = await client.delete("/api/v1/watchlist/999")
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "Company not found"

    deleted_company = await client.delete(f"/api/v1/companies/{second_id}")
    assert deleted_company.status_code == 204
    emptied = await client.get("/api/v1/watchlist/")
    assert emptied.json() == []


@pytest.mark.asyncio
async def test_watchlist_api_rejects_a_bad_body(client):
    company_id = await _company(client, "CCC")
    too_long = await client.post(
        "/api/v1/watchlist/",
        json={"company_id": company_id, "label": "x" * 81},
    )
    assert too_long.status_code == 422
    missing_id = await client.post("/api/v1/watchlist/", json={"label": "x"})
    assert missing_id.status_code == 422
    listed = await client.get("/api/v1/watchlist/")
    assert listed.json() == []


@pytest.mark.asyncio
async def test_watchlist_storage_error_is_a_fixed_500(client, monkeypatch):
    """A constraint failure that is not a duplicate add is HTTP 500.

    The body is the fixed sentence. The driver text is not included.
    """
    from app.repositories.watchlist_repository import WatchlistStorageError

    company_id = await _company(client, "DDD")

    def raise_storage(self, company_id, label=None):
        raise WatchlistStorageError()

    monkeypatch.setattr(WatchlistRepository, "add", raise_storage)
    response = await client.post(
        "/api/v1/watchlist/", json={"company_id": company_id, "label": "x"}
    )
    assert response.status_code == 500
    assert response.json()["detail"] == "Watchlist item could not be stored"
    assert "IntegrityError" not in response.text
    listed = await client.get("/api/v1/watchlist/")
    assert listed.json() == []


@pytest.mark.asyncio
async def test_control_label_is_422_and_stores_nothing(client):
    """NUL is rejected by the model, including on the way to PostgreSQL.

    The SQLite client covers the same rule. The PostgreSQL test is in
    the integration module, because a NUL that reached the column
    would be a database error rather than 422.
    """
    company_id = await _company(client, "NUL")
    response = await client.post(
        "/api/v1/watchlist/",
        json={"company_id": company_id, "label": "A\x00B"},
    )
    assert response.status_code == 422
    assert "IntegrityError" not in response.text
    listed = await client.get("/api/v1/watchlist/")
    assert listed.json() == []


@pytest.mark.asyncio
async def test_format_only_label_is_stored_as_null(client):
    company_id = await _company(client, "FMT")
    invisible = await client.post(
        "/api/v1/watchlist/",
        json={"company_id": company_id, "label": "\u200b\ufeff"},
    )
    assert invisible.status_code == 201
    assert invisible.json()["label"] is None
    other_id = await _company(client, "FM2")
    kept = await client.post(
        "/api/v1/watchlist/",
        json={"company_id": other_id, "label": "A\u200bB"},
    )
    assert kept.status_code == 201
    assert kept.json()["label"] == "A\u200bB"


@pytest.mark.asyncio
async def test_post_rejects_non_json_content_types(client):
    """text/plain, a form body, and a missing type are all 422.

    None of them insert a row. The endpoint reads a JSON object.
    """
    company_id = await _company(client, "EEE")
    payload = '{"company_id": %s, "label": "x"}' % company_id
    plain = await client.post(
        "/api/v1/watchlist/",
        content=payload.encode(),
        headers={"Content-Type": "text/plain"},
    )
    assert plain.status_code == 422
    form = await client.post(
        "/api/v1/watchlist/",
        data={"company_id": str(company_id), "label": "x"},
    )
    assert form.status_code == 422
    missing_type = await client.post(
        "/api/v1/watchlist/",
        content=payload.encode(),
    )
    assert missing_type.request.headers.get("content-type") is None
    assert missing_type.status_code == 422
    listed = await client.get("/api/v1/watchlist/")
    assert listed.json() == []


@pytest.mark.asyncio
async def test_delete_rejects_a_non_positive_company_id(client):
    zero = await client.delete("/api/v1/watchlist/0")
    assert zero.status_code == 422
    negative = await client.delete("/api/v1/watchlist/-1")
    assert negative.status_code == 422


@pytest.mark.asyncio
async def test_openapi_documents_watchlist_post_statuses(client):
    schema = (await client.get("/api/v1/openapi.json")).json()
    responses = schema["paths"]["/api/v1/watchlist/"]["post"]["responses"]
    assert "200" in responses
    assert "201" in responses
    assert "404" in responses


@pytest.mark.asyncio
async def test_company_deleted_before_insert_is_404(client, monkeypatch):
    """The company can disappear after the existence check.

    The foreign-key failure becomes the same 404 as an unknown
    company. The driver text is not in the body.
    """
    from app.models.database_models import CompanyDB

    company_id = await _company(client, "DEL")
    original = WatchlistRepository.add

    def delete_then_add(self, company_id, label=None):
        company = self.db.get(CompanyDB, company_id)
        self.db.delete(company)
        self.db.commit()
        return original(self, company_id, label)

    monkeypatch.setattr(WatchlistRepository, "add", delete_then_add)
    response = await client.post(
        "/api/v1/watchlist/",
        json={"company_id": company_id, "label": "late"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Company not found"
    assert "IntegrityError" not in response.text
    assert "FOREIGN" not in response.text
    listed = await client.get("/api/v1/watchlist/")
    assert listed.json() == []


@pytest.mark.asyncio
async def test_race_loser_is_200(client, monkeypatch):
    """The request that loses the unique constraint is 200, not 201.

    The first lookup is hidden, so both calls would otherwise think
    they created the row. ``created`` comes from the insert result.
    """
    company_id = await _company(client, "RCE")
    first = await client.post(
        "/api/v1/watchlist/",
        json={"company_id": company_id, "label": "keep"},
    )
    assert first.status_code == 201
    original = WatchlistRepository.get_by_company_id
    calls = {"count": 0}

    def hide_the_first_lookup(self, looked_up):
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return original(self, looked_up)

    monkeypatch.setattr(
        WatchlistRepository, "get_by_company_id", hide_the_first_lookup
    )
    again = await client.post(
        "/api/v1/watchlist/",
        json={"company_id": company_id, "label": "other"},
    )
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    assert again.json()["label"] == "keep"
    assert calls["count"] == 2
