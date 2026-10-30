import pytest
from pydantic import ValidationError

from app.models.company import COMPANY_NAME_MAX, CompanyCreate, CompanyUpdate
from app.models.database_models import CompanyDB


def test_name_is_stripped_and_a_blank_name_is_rejected():
    created = CompanyCreate(name="  Acme  ", ticker="AAA")
    updated = CompanyUpdate(name="  New  ")

    assert created.name == "Acme"
    assert updated.name == "New"
    assert "name" not in CompanyUpdate().model_dump(exclude_unset=True)
    with pytest.raises(ValidationError) as blank:
        CompanyCreate(name="   ", ticker="AAA")
    blank_error = blank.value.errors()[0]
    assert blank_error["type"] == "value_error"
    assert blank_error["msg"] == (
        "Value error, name must contain a visible character"
    )
    assert blank_error["ctx"]["error"].code == "blank"
    assert blank_error["ctx"]["error"].field == "name"
    with pytest.raises(ValidationError):
        CompanyUpdate(name=" ")
    for invisible in ("\u200b", "\ufeff", "\u200c\u200d", "  \u200b  "):
        with pytest.raises(ValidationError):
            CompanyCreate(name=invisible, ticker="AAA")
        with pytest.raises(ValidationError):
            CompanyUpdate(name=invisible)
    # After strip, a name with no character outside whitespace and
    # Unicode category C* is blank. Cc is a control, Cf is format,
    # Co is private use, Cn is unassigned. A letter next to a format
    # character is a real name and is kept.
    for invisible in (
        "\u200b \u200b",
        "\x00",
        "\ue000",
        "\u0378",
        "\x00 \ue000",
    ):
        with pytest.raises(ValidationError):
            CompanyCreate(name=invisible, ticker="AAA")
        with pytest.raises(ValidationError):
            CompanyUpdate(name=invisible)
    for marks_only in ("\u0301", "\u093e", "\u20dd"):
        with pytest.raises(ValidationError) as marks:
            CompanyCreate(name=marks_only, ticker="AAA")
        assert marks.value.errors()[0]["ctx"]["error"].code == "blank"
    based = CompanyCreate(name="A\u093e\u20dd", ticker="AAA")
    assert based.name == "A\u093e\u20dd"
    kept = CompanyCreate(name="Acme\u200b", ticker="AAA")
    assert kept.name == "Acme\u200b"
    beside = CompanyCreate(name="A\u200bB", ticker="AAA")
    assert beside.name == "A\u200bB"
    # Cc anywhere after strip is rejected. NUL and DEL survive strip,
    # so a letter beside them is not a stored name. A format character
    # beside a letter is still kept, above.
    for control in ("\x00Kept", "Kept\x00", "Ke\x00pt", "Kept\x7f"):
        with pytest.raises(ValidationError, match="control"):
            CompanyCreate(name=control, ticker="AAA")
        with pytest.raises(ValidationError, match="control"):
            CompanyUpdate(name=control)


@pytest.mark.asyncio
async def test_blank_name_is_422_on_create_and_update(client):
    created = await client.post(
        "/api/v1/companies/", json={"name": "  Kept  ", "ticker": "KEEP"}
    )
    assert created.status_code == 201
    assert created.json()["name"] == "Kept"
    company_id = created.json()["id"]

    blank_create = await client.post(
        "/api/v1/companies/", json={"name": "   ", "ticker": "BLANK"}
    )
    assert blank_create.status_code == 422
    assert "name" in blank_create.text

    blank_update = await client.put(
        f"/api/v1/companies/{company_id}", json={"name": " "}
    )
    assert blank_update.status_code == 422
    fetched = await client.get(f"/api/v1/companies/{company_id}")
    assert fetched.json()["name"] == "Kept"

    renamed = await client.put(
        f"/api/v1/companies/{company_id}", json={"name": "  Renamed  "}
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Renamed"

    for invisible in ("\u200b \u200b", "\x00", "\ue000"):
        rejected = await client.post(
            "/api/v1/companies/", json={"name": invisible, "ticker": "INVIS"}
        )
        assert rejected.status_code == 422
        rejected_update = await client.put(
            f"/api/v1/companies/{company_id}", json={"name": invisible}
        )
        assert rejected_update.status_code == 422
    fetched = await client.get(f"/api/v1/companies/{company_id}")
    assert fetched.json()["name"] == "Renamed"
    for marks_only in ("\u0301", "\u093e", "\u20dd", "\u200b\u0301"):
        rejected = await client.post(
            "/api/v1/companies/",
            json={"name": marks_only, "ticker": "MARKS"},
        )
        assert rejected.status_code == 422, repr(marks_only)
        _assert_text_contract(
            rejected,
            "name",
            "blank",
            "Value error, name must contain a visible character",
        )
        rejected_update = await client.put(
            f"/api/v1/companies/{company_id}",
            json={"name": marks_only},
        )
        assert rejected_update.status_code == 422, repr(marks_only)
        _assert_text_contract(
            rejected_update,
            "name",
            "blank",
            "Value error, name must contain a visible character",
        )
    # A letter keeps a combining mark. That name is not blank.
    accented = await client.put(
        f"/api/v1/companies/{company_id}", json={"name": "e\u0301"}
    )
    assert accented.status_code == 200
    assert accented.json()["name"] == "e\u0301"
    kept = await client.put(
        f"/api/v1/companies/{company_id}", json={"name": "A\u200bB"}
    )
    assert kept.status_code == 200
    assert kept.json()["name"] == "A\u200bB"

    db = client.app.state.testing_session_local()
    try:
        assert db.query(CompanyDB).count() == 1
        assert db.get(CompanyDB, company_id).name == "A\u200bB"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_create_and_list_company_persists_website_as_string(client):
    payload = {
        "name": "Acme Corp",
        "ticker": "ACME",
        "sector": "Technology",
        "industry": "Software",
        "website": "https://example.com",
        "country": "USA",
        "exchange": "NASDAQ",
        "currency": "USD",
    }

    create_response = await client.post("/api/v1/companies/", json=payload)

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["ticker"] == "ACME"
    assert created["website"] == "https://example.com/"

    list_response = await client.get("/api/v1/companies/")

    assert list_response.status_code == 200
    companies = list_response.json()
    assert len(companies) == 1
    assert companies[0]["website"] == "https://example.com/"

    db = client.app.state.testing_session_local()
    try:
        stored = db.query(CompanyDB).filter(CompanyDB.ticker == "ACME").one()
        assert stored.website == "https://example.com/"
        assert isinstance(stored.website, str)
    finally:
        db.close()


def _field_error(response, field):
    """The 422 object for one field."""
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    matched = [item for item in detail if item.get("loc", [None])[-1] == field]
    assert len(matched) == 1
    return matched[0]


def _field_message(response, field):
    """The 422 sentence for one field. It must not echo the input."""
    return _field_error(response, field)["msg"]


def _assert_text_contract(response, field, code, msg, max_length=None):
    """Lock type, msg, and ctx for one text failure.

    ``too_long`` is Pydantic ``string_too_long``. The other codes are
    ``value_error``, and ``ctx.error`` carries ``code`` and ``field``.
    """
    error = _field_error(response, field)
    assert error["msg"] == msg
    if code == "too_long":
        assert error["type"] == "string_too_long"
        assert error["ctx"] == {"max_length": max_length}
        return
    assert error["type"] == "value_error"
    assert error["ctx"]["error"] == {"code": code, "field": field}


def test_company_name_length_stays_a_max_length_error():
    """A too-long name stays Pydantic's string_too_long error.

    Raising ``too_long`` inside ``normalize_name`` would change this
    HTTP error to ``value_error``. The ``/ui`` form calls
    ``clean_text`` and maps ``too_long`` on its own.
    """
    with pytest.raises(ValidationError) as caught:
        CompanyCreate(name="N" * (COMPANY_NAME_MAX + 1), ticker="AAA")
    assert caught.value.errors()[0]["type"] == "string_too_long"
    created = CompanyCreate(name="N" * COMPANY_NAME_MAX, ticker="AAA")
    assert created.name == "N" * COMPANY_NAME_MAX
    padded = CompanyCreate(
        name=" " + ("N" * COMPANY_NAME_MAX) + " ", ticker="AAA"
    )
    assert padded.name == "N" * COMPANY_NAME_MAX


@pytest.mark.asyncio
async def test_company_api_rejects_bidi_control_and_surrogate(client):
    """Create and update both return 422. The stored name stays put.

    The message names the problem and does not repeat the text.
    """
    kept = await client.post(
        "/api/v1/companies/",
        json={"name": "Stored", "ticker": "KEPT1"},
    )
    assert kept.status_code == 201
    company_id = kept.json()["id"]
    cases = (
        ("Kept\u202e", "bidi"),
        ("A\x00B", "control"),
        ("ETF\n", "control"),
    )
    for name, word in cases:
        created = await client.post(
            "/api/v1/companies/",
            json={"name": name, "ticker": "BADNM"},
        )
        assert created.status_code == 422, repr(name)
        message = _field_message(created, "name")
        assert word in message
        assert "Kept" not in message
        assert "ETF" not in message
        assert "\u202e" not in message
        assert "\x00" not in message
        assert "\ud800" not in message
        updated = await client.put(
            f"/api/v1/companies/{company_id}",
            json={"name": name},
        )
        assert updated.status_code == 422, repr(name)
        update_message = _field_message(updated, "name")
        assert word in update_message
        assert "\u202e" not in update_message
        assert "\ud800" not in update_message
    # A lone surrogate is not valid UTF-8. The JSON text uses the
    # \\u escape, which the parser turns into category Cs.
    surrogate = await client.post(
        "/api/v1/companies/",
        content=b'{"name": "A\\ud800B", "ticker": "BADNM"}',
        headers={"content-type": "application/json"},
    )
    assert surrogate.status_code == 422
    # The body is UTF-8. The raw surrogate is not in it. The input
    # shows the ASCII \\u escape instead, which is why this is 422
    # and not a 500 from the JSON encoder.
    surrogate.content.decode("utf-8")
    assert "\ud800" not in surrogate.text
    assert "\\ud800" in surrogate.text
    surrogate_message = _field_message(surrogate, "name")
    assert "surrogate" in surrogate_message
    assert "\\ud800" not in surrogate_message
    assert "\ud800" not in surrogate_message
    surrogate_update = await client.put(
        f"/api/v1/companies/{company_id}",
        content=b'{"name": "A\\ud800B"}',
        headers={"content-type": "application/json"},
    )
    assert surrogate_update.status_code == 422
    assert "surrogate" in _field_message(surrogate_update, "name")
    fetched = await client.get(f"/api/v1/companies/{company_id}")
    assert fetched.json()["name"] == "Stored"


_COMPANY_TEXT_CASES = (
    (
        "blank",
        "   ",
        "Value error, name must contain a visible character",
        None,
    ),
    (
        "too_long",
        "N" * (COMPANY_NAME_MAX + 1),
        "String should have at most %d characters" % COMPANY_NAME_MAX,
        COMPANY_NAME_MAX,
    ),
    (
        "control_char",
        "ETF\n",
        "Value error, name must not contain control characters",
        None,
    ),
    (
        "bidi",
        "Kept\u202e",
        "Value error, name must not contain hidden or bidi controls",
        None,
    ),
    (
        "surrogate",
        None,
        "Value error, name must not contain unpaired surrogates",
        None,
    ),
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "name", "msg", "max_length"),
    _COMPANY_TEXT_CASES,
    ids=["blank", "too_long", "control_char", "bidi", "surrogate"],
)
async def test_company_text_error_contract(
    client, code, name, msg, max_length
):
    """Create and update both lock type, msg, and ctx for one code."""
    kept = await client.post(
        "/api/v1/companies/",
        json={"name": "Stored", "ticker": "K" + code[:4].upper()},
    )
    assert kept.status_code == 201
    company_id = kept.json()["id"]
    if code == "surrogate":
        created = await client.post(
            "/api/v1/companies/",
            content=b'{"name": "A\\ud800B", "ticker": "BADNM"}',
            headers={"content-type": "application/json"},
        )
        updated = await client.put(
            f"/api/v1/companies/{company_id}",
            content=b'{"name": "A\\ud800B"}',
            headers={"content-type": "application/json"},
        )
    else:
        created = await client.post(
            "/api/v1/companies/",
            json={"name": name, "ticker": "BADNM"},
        )
        updated = await client.put(
            f"/api/v1/companies/{company_id}",
            json={"name": name},
        )
    assert created.status_code == 422
    assert updated.status_code == 422
    _assert_text_contract(created, "name", code, msg, max_length)
    _assert_text_contract(updated, "name", code, msg, max_length)
    fetched = await client.get(f"/api/v1/companies/{company_id}")
    assert fetched.json()["name"] == "Stored"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        b'{"\\udc00": 1, "name": "X"}',
        b'{"name": "X", "nested": {"\\udc00": 1}}',
    ],
    ids=["surrogate-key", "nested-surrogate-key"],
)
async def test_surrogate_object_key_with_a_missing_ticker_is_422(
    client, content
):
    """A missing ticker puts the whole body in the 422 input.

    The key U+DC00 is a lone surrogate. Leaving it raw makes the
    JSON encoder raise, so the client would see 500. A nested key
    is the same character one level down.
    """
    response = await client.post(
        "/api/v1/companies/",
        content=content,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    response.content.decode("utf-8")
    assert "\udc00" not in response.text
    assert "\\udc00" in response.text


@pytest.mark.asyncio
async def test_extra_text_error_attribute_is_not_in_the_body(
    client, monkeypatch
):
    """ctx.error is only code and field. A new attribute must not leak."""
    from app.validation.text import TextValidationError

    original = TextValidationError.__init__

    def init(self, code, field, max_len=None, *, message=None):
        original(self, code, field, max_len, message=message)
        self.leak = "secret-token"

    monkeypatch.setattr(TextValidationError, "__init__", init)
    response = await client.post(
        "/api/v1/companies/",
        json={"name": "   ", "ticker": "LEAK1"},
    )
    assert response.status_code == 422
    error = _field_error(response, "name")
    assert error["ctx"]["error"] == {"code": "blank", "field": "name"}
    assert "secret-token" not in response.text
    assert "leak" not in response.text
