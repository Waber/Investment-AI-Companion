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
    assert_race_keeps_earlier_pending_work,
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
    with pytest.raises(ValidationError) as too_long:
        WatchlistItemCreate(
            company_id=1, label="x" * (WATCHLIST_LABEL_MAX_LENGTH + 1)
        )
    length_error = too_long.value.errors()[0]
    assert length_error["loc"] == ("label",)
    assert length_error["type"] == "string_too_long"
    assert length_error["ctx"]["max_length"] == WATCHLIST_LABEL_MAX_LENGTH


# (label, code). Ids name the unprintable characters as U+XXXX.
_REJECTED_LABELS = (
    ("\x00", "control_char"),
    ("A\x00B", "control_char"),
    ("\x7f", "control_char"),
    ("\u202a", "bidi"),
    ("\u202e", "bidi"),
    ("\u2066", "bidi"),
    ("\u2069", "bidi"),
    ("\u200e", "bidi"),
    ("\u200f", "bidi"),
    ("\u061c", "bidi"),
    ("A\u061cB", "bidi"),
    ("\u206a", "bidi"),
    ("\u206f", "bidi"),
    ("A\u206aB", "bidi"),
    ("A\u200eB", "bidi"),
    ("A\u200fB", "bidi"),
    ("\U000e0001", "bidi"),
    ("A\U000e007fB", "bidi"),
    ("\n", "control_char"),
    ("note\n", "control_char"),
)


def _label_case_id(pair):
    label, code = pair
    parts = []
    letters = []

    def flush():
        if letters:
            parts.append("".join(letters))
            letters.clear()

    for char in label:
        if char.isprintable() and char != " ":
            letters.append(char)
            continue
        flush()
        parts.append("U+%04X" % ord(char))
    flush()
    return "+".join(parts) + "-" + code


@pytest.mark.parametrize(
    ("label", "code"),
    _REJECTED_LABELS,
    ids=[_label_case_id(pair) for pair in _REJECTED_LABELS],
)
def test_create_model_rejects_controls_and_bidi(label, code):
    """Cc (including NUL) and the listed bidi controls are invalid.

    U+200E and U+200F are format characters, and they are still
    rejected. A label that is only one of them is not stored as null.
    """
    with pytest.raises(ValidationError) as caught:
        WatchlistItemCreate(company_id=1, label=label)
    error = caught.value.errors()[0]
    assert error["loc"] == ("label",)
    assert error["type"] == "value_error"
    cause = error["ctx"]["error"]
    assert cause.code == code
    assert cause.field == "label"


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
        "\ue000",
        "\u0378",
    ],
)
def test_create_model_treats_blank_and_format_only_labels_as_null(label):
    """Whitespace, Cf, Co, and Cn notes are the same as omitting the label."""
    created = WatchlistItemCreate(company_id=1, label=label)
    assert created.label is None


def test_create_model_keeps_a_format_character_beside_a_letter():
    created = WatchlistItemCreate(company_id=1, label=" A\u200bB ")
    assert created.label == "A\u200bB"
    kept = WatchlistItemCreate(company_id=1, label="A\u200cB")
    assert kept.label == "A\u200cB"


def test_stale_price_days_defaults_to_seven(monkeypatch):
    monkeypatch.delenv("WATCHLIST_STALE_PRICE_DAYS", raising=False)
    built = Settings(_env_file=None, SECRET_KEY=SECRET)
    assert built.WATCHLIST_STALE_PRICE_DAYS == 7


def test_stale_price_days_reads_the_environment(monkeypatch):
    """The env name matches the field, like the other settings."""
    monkeypatch.setenv("WATCHLIST_STALE_PRICE_DAYS", "3")
    built = Settings(_env_file=None, SECRET_KEY=SECRET)
    assert built.WATCHLIST_STALE_PRICE_DAYS == 3
    monkeypatch.setenv("WATCHLIST_STALE_PRICE_DAYS", "nope")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, SECRET_KEY=SECRET)


@pytest.mark.parametrize("days", [0, -1])
def test_stale_price_days_rejects_non_positive(monkeypatch, days):
    monkeypatch.delenv("WATCHLIST_STALE_PRICE_DAYS", raising=False)
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            SECRET_KEY=SECRET,
            WATCHLIST_STALE_PRICE_DAYS=days,
        )


def test_add_is_idempotent_and_keeps_the_first_label(session):
    assert_add_is_idempotent_and_keeps_the_first_label(session)


def test_blank_label_is_stored_as_null(session):
    assert_blank_label_is_stored_as_null(session)


def test_race_returns_the_existing_row(monkeypatch, session):
    assert_race_returns_the_existing_row(monkeypatch, session)


def test_race_keeps_earlier_pending_work(monkeypatch, session):
    assert_race_keeps_earlier_pending_work(monkeypatch, session)


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
    length_error = [
        item
        for item in too_long.json()["detail"]
        if item.get("loc", [None])[-1] == "label"
    ]
    assert len(length_error) == 1
    assert length_error[0]["type"] == "string_too_long"
    assert length_error[0]["msg"] == (
        "String should have at most %d characters" % WATCHLIST_LABEL_MAX_LENGTH
    )
    assert length_error[0]["ctx"] == {"max_length": WATCHLIST_LABEL_MAX_LENGTH}
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
    operation = schema["paths"]["/api/v1/watchlist/"]["post"]
    responses = operation["responses"]
    assert "200" in responses
    assert "201" in responses
    assert "404" in responses
    description = " ".join(operation["description"].split())
    repeat = " ".join(responses["200"]["description"].split())
    assert "keeps the original label" in description
    assert "keeps the original label" in repeat


@pytest.mark.asyncio
async def test_watchlist_post_without_a_trailing_slash_redirects(client):
    """FastAPI's slash redirect is 307, so the POST method is kept."""
    response = await client.post(
        "/api/v1/watchlist",
        json={"company_id": 1},
        follow_redirects=False,
    )
    assert response.status_code == 307
    assert response.headers["location"].endswith("/api/v1/watchlist/")


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


def _field_error(response, field):
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    matched = [item for item in detail if item.get("loc", [None])[-1] == field]
    assert len(matched) == 1
    return matched[0]


def _field_message(response, field):
    return _field_error(response, field)["msg"]


def _assert_text_contract(response, field, code, msg, max_length=None):
    """Lock type, msg, and the error code on one 422 field."""
    error = _field_error(response, field)
    assert error["msg"] == msg
    if code == "too_long":
        assert error["type"] == "string_too_long"
        assert error["ctx"] == {"max_length": max_length}
        return
    assert error["type"] == "value_error"
    assert error["ctx"]["error"] == {"code": code, "field": field}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ticker", "label", "word"),
    [
        ("BIDI1", "Kept\u202e", "bidi"),
        ("CTRL1", "A\x00B", "control"),
        ("NLBL1", "ETF\n", "control"),
        ("DEP1", "A\u206aB", "bidi"),
        ("TAG1", "A\U000e0001B", "bidi"),
    ],
)
async def test_watchlist_api_rejects_hidden_and_control_labels(
    client, ticker, label, word
):
    """A bad label is 422 and does not insert a row.

    The message does not repeat the label.
    """
    company_id = await _company(client, ticker)
    response = await client.post(
        "/api/v1/watchlist/",
        json={"company_id": company_id, "label": label},
    )
    assert response.status_code == 422
    message = _field_message(response, "label")
    assert word in message
    assert "Kept" not in message
    assert "ETF" not in message
    assert "\u202e" not in message
    assert "\x00" not in message
    assert "\ud800" not in message
    listed = await client.get("/api/v1/watchlist/")
    assert listed.json() == []


@pytest.mark.asyncio
async def test_watchlist_api_rejects_a_surrogate_label(client):
    """The JSON \\u escape becomes a lone surrogate and is 422."""
    company_id = await _company(client, "SURR1")
    body = ('{"company_id": %d, "label": "A\\ud800B"}' % company_id).encode()
    response = await client.post(
        "/api/v1/watchlist/",
        content=body,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    response.content.decode("utf-8")
    assert "\ud800" not in response.text
    assert "\\ud800" in response.text
    message = _field_message(response, "label")
    assert "surrogate" in message
    assert "\ud800" not in message
    listed = await client.get("/api/v1/watchlist/")
    assert listed.json() == []


_WATCHLIST_TEXT_CASES = (
    ("blank", "   ", None, None),
    ("blank", "\ue000", None, None),
    (
        "too_long",
        "x" * (WATCHLIST_LABEL_MAX_LENGTH + 1),
        "String should have at most %d characters"
        % WATCHLIST_LABEL_MAX_LENGTH,
        WATCHLIST_LABEL_MAX_LENGTH,
    ),
    (
        "control_char",
        "ETF\n",
        "Value error, label must not contain control characters",
        None,
    ),
    (
        "bidi",
        "Kept\u202e",
        "Value error, label must not contain hidden or bidi controls",
        None,
    ),
    (
        "surrogate",
        None,
        "Value error, label must not contain unpaired surrogates",
        None,
    ),
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "label", "msg", "max_length"),
    _WATCHLIST_TEXT_CASES,
    ids=[
        "blank-spaces",
        "blank-U+E000",
        "too_long",
        "control_char",
        "bidi",
        "surrogate",
    ],
)
async def test_watchlist_text_error_contract(
    client, code, label, msg, max_length
):
    """Lock type, msg, and ctx.error.code for each text failure.

    A blank label is not a 422, so it has no error type. Whitespace
    and a private-use-only label are stored as null. On master the
    private-use label was stored as that text.
    """
    company_id = await _company(client, "W" + code[:5].upper())
    if code == "blank":
        created = await client.post(
            "/api/v1/watchlist/",
            json={"company_id": company_id, "label": label},
        )
        assert created.status_code == 201
        assert created.json()["label"] is None
        return
    if code == "surrogate":
        body = (
            '{"company_id": %d, "label": "A\\ud800B"}' % company_id
        ).encode()
        response = await client.post(
            "/api/v1/watchlist/",
            content=body,
            headers={"content-type": "application/json"},
        )
    else:
        response = await client.post(
            "/api/v1/watchlist/",
            json={"company_id": company_id, "label": label},
        )
    assert response.status_code == 422
    _assert_text_contract(response, "label", code, msg, max_length)
    if code == "surrogate":
        response.content.decode("utf-8")
        assert "\ud800" not in response.text
    listed = await client.get("/api/v1/watchlist/")
    assert listed.json() == []
