"""JSON API for notes and theses (``app/api/research.py``).

Companies are added through ``POST /api/v1/companies/``, the way
``tests/test_watchlist.py`` does. No test calls a market-data
provider. ``tests/research_cases.py`` covers the repositories. These
tests cover the HTTP contract: status codes, the 404 texts, the id
bounds, the text rules as a 422, and the fixed 500.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.models.database_models import CompanyDB, NoteDB, ThesisDB
from app.models.research import (
    NOTE_BODY_MAX,
    THESIS_BODY_MAX,
    THESIS_BREAKERS_MAX,
    THESIS_TITLE_MAX,
    NoteCreate,
)
from app.repositories.company_errors import CompanyNotFoundError
from app.repositories.note_repository import NoteRepository
from app.repositories.research_store import ResearchStorageError
from app.repositories.thesis_repository import ThesisRepository

API = "/api/v1/instruments"
_LARGEST_ID = 2**63 - 1
_OLD = datetime(2020, 1, 1, tzinfo=timezone.utc)
_NEWER = datetime(2024, 6, 1, tzinfo=timezone.utc)
_NOTE = {"body": "Bought after an analysis."}
_THESIS = {"title": "AI infrastructure", "body": "Demand keeps growing."}
# The 404 text for each path parameter.
_MISSING = {
    "instrument_id": "Instrument not found",
    "note_id": "Note not found",
    "thesis_id": "Thesis not found",
}
_NOT_STORED = {"detail": "Note or thesis could not be stored"}


async def _company(client, ticker):
    response = await client.post(
        "/api/v1/companies/",
        json={"name": ticker + " Co", "ticker": ticker},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _add(client, company_id, resource, payload):
    """POST one note or thesis and return the stored JSON."""
    response = await client.post(
        f"{API}/{company_id}/{resource}", json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _listed(client, company_id, resource, **params):
    response = await client.get(
        f"{API}/{company_id}/{resource}", params=params
    )
    assert response.status_code == 200, response.text
    return response.json()


def _routes(instrument_id, note_id, thesis_id):
    """Every route as (method, URL, JSON body, item id name).

    The bodies are valid, so only an id can make a request fail. The
    item id name is None on the list and create routes.
    """
    notes = f"{API}/{instrument_id}/notes"
    theses = f"{API}/{instrument_id}/theses"
    note = f"{notes}/{note_id}"
    thesis = f"{theses}/{thesis_id}"
    return (
        ("GET", notes, None, None),
        ("POST", notes, _NOTE, None),
        ("GET", note, None, "note_id"),
        ("PUT", note, _NOTE, "note_id"),
        ("DELETE", note, None, "note_id"),
        ("GET", theses, None, None),
        ("POST", theses, _THESIS, None),
        ("GET", thesis, None, "thesis_id"),
        ("PUT", thesis, _THESIS, "thesis_id"),
        ("DELETE", thesis, None, "thesis_id"),
    )


def _pin_updated_at(client, model, row_id, moment):
    """Write ``updated_at`` past the API, as a fixed known time."""
    with client.app.state.testing_session_local() as db:
        db.get(model, row_id).updated_at = moment
        db.commit()


def _as_utc(value):
    """Parse an API timestamp that must carry the UTC offset.

    A naive time has no offset: ``utcoffset()`` is None, and the
    check fails.
    """
    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset() == timedelta(0), value
    return parsed


def _only_error(response):
    """The single entry of a 422 body."""
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert len(detail) == 1, detail
    return detail[0]


@pytest.mark.asyncio
async def test_note_crud_round_trip(client):
    company_id = await _company(client, "NOTE")
    url = f"{API}/{company_id}/notes"
    created = await client.post(url, json={"body": "b1"})
    assert created.status_code == 201
    note = created.json()
    assert set(note) == {
        "id",
        "company_id",
        "body",
        "created_at",
        "updated_at",
    }
    assert note["company_id"] == company_id
    assert note["body"] == "b1"
    _as_utc(note["created_at"])
    _as_utc(note["updated_at"])

    note_url = f"{url}/{note['id']}"
    assert await _listed(client, company_id, "notes") == [note]
    one = await client.get(note_url)
    assert one.status_code == 200
    assert one.json() == note

    edited = await client.put(note_url, json={"body": "b2"})
    assert edited.status_code == 200
    assert edited.json()["id"] == note["id"]
    assert edited.json()["body"] == "b2"

    # An empty PUT changes nothing. The pinned old time shows that
    # updated_at did not move.
    _pin_updated_at(client, NoteDB, note["id"], _OLD)
    unchanged = await client.put(note_url, json={})
    assert unchanged.status_code == 200
    assert unchanged.json()["body"] == "b2"
    assert _as_utc(unchanged.json()["updated_at"]) == _OLD

    deleted = await client.delete(note_url)
    assert deleted.status_code == 204
    assert deleted.content == b""
    again = await client.delete(note_url)
    assert again.status_code == 404
    assert again.json() == {"detail": "Note not found"}
    gone = await client.get(note_url)
    assert gone.status_code == 404
    assert gone.json() == {"detail": "Note not found"}
    assert await _listed(client, company_id, "notes") == []


@pytest.mark.asyncio
async def test_thesis_crud_close_and_reopen(client):
    company_id = await _company(client, "THES")
    url = f"{API}/{company_id}/theses"
    created = await client.post(
        url, json={**_THESIS, "thesis_breakers": "Sell at +20%."}
    )
    assert created.status_code == 201
    thesis = created.json()
    assert thesis["company_id"] == company_id
    assert thesis["thesis_breakers"] == "Sell at +20%."
    assert thesis["status"] == "active"
    assert thesis["closed_at"] is None
    thesis_url = f"{url}/{thesis['id']}"
    one = await client.get(thesis_url)
    assert one.status_code == 200
    assert one.json() == thesis
    assert await _listed(client, company_id, "theses") == [thesis]

    closed = await client.put(thesis_url, json={"status": "closed"})
    assert closed.status_code == 200
    stored = closed.json()
    assert stored["status"] == "closed"
    assert stored["title"] == thesis["title"]
    assert stored["closed_at"] is not None
    # One clock: closing sets closed_at to the new updated_at.
    assert _as_utc(stored["closed_at"]) == _as_utc(stored["updated_at"])
    by_status = await _listed(client, company_id, "theses", status="closed")
    assert by_status == [stored]
    assert await _listed(client, company_id, "theses", status="active") == []

    # An empty PUT changes nothing, neither clock included.
    _pin_updated_at(client, ThesisDB, thesis["id"], _OLD)
    before = (await client.get(thesis_url)).json()
    unchanged = await client.put(thesis_url, json={})
    assert unchanged.status_code == 200
    assert unchanged.json() == before
    assert _as_utc(before["updated_at"]) == _OLD
    assert before["closed_at"] == stored["closed_at"]

    reopened = await client.put(thesis_url, json={"status": "active"})
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "active"
    assert reopened.json()["closed_at"] is None
    assert await _listed(client, company_id, "theses", status="closed") == []

    deleted = await client.delete(thesis_url)
    assert deleted.status_code == 204
    assert deleted.content == b""
    again = await client.delete(thesis_url)
    assert again.status_code == 404
    assert again.json() == {"detail": "Thesis not found"}
    assert await _listed(client, company_id, "theses") == []

    # The API can also create a thesis that is closed already.
    created_closed = await _add(
        client, company_id, "theses", {**_THESIS, "status": "closed"}
    )
    assert created_closed["status"] == "closed"
    _as_utc(created_closed["closed_at"])


@pytest.mark.asyncio
async def test_lists_use_repository_order(client):
    """Newest edit first (``updated_at`` desc), then the higher id.

    The pinned times put the first item on top, although it was
    created first, and the tie shows the id order. A real edit then
    moves an item to the top. The UI sorts for display; the API does
    not.
    """
    company_id = await _company(client, "ORDR")
    for resource, model, payload in (
        ("notes", NoteDB, _NOTE),
        ("theses", ThesisDB, _THESIS),
    ):
        first, second, third = [
            (await _add(client, company_id, resource, payload))["id"]
            for _ in range(3)
        ]
        _pin_updated_at(client, model, first, _NEWER)
        _pin_updated_at(client, model, second, _OLD)
        _pin_updated_at(client, model, third, _OLD)
        listed = await _listed(client, company_id, resource)
        assert [item["id"] for item in listed] == [first, third, second]

        edited = await client.put(
            f"{API}/{company_id}/{resource}/{second}",
            json={"body": "Edited."},
        )
        assert edited.status_code == 200
        listed = await _listed(client, company_id, resource)
        assert [item["id"] for item in listed] == [second, first, third]


@pytest.mark.asyncio
async def test_unknown_instrument_is_checked_first(client):
    """Instrument 999 is 404 on all ten routes, never an empty list.

    The note and thesis ids are real ids of another company. A route
    that looked the item up before the instrument would answer with
    the item's own 404. The repository alone would list ``[]``.
    """
    company_id = await _company(client, "REAL")
    note = await _add(client, company_id, "notes", _NOTE)
    thesis = await _add(client, company_id, "theses", _THESIS)
    for method, url, body, _ in _routes(999, note["id"], thesis["id"]):
        response = await client.request(method, url, json=body)
        assert response.status_code == 404, (method, url)
        assert response.json() == {"detail": "Instrument not found"}
    assert await _listed(client, company_id, "notes") == [note]
    assert await _listed(client, company_id, "theses") == [thesis]


@pytest.mark.asyncio
async def test_item_of_another_instrument_is_404(client):
    """Company A's note or thesis, sent through company B, is missing.

    Reading, editing, and deleting all answer with the item's own
    404, and A's note and thesis stay as they were.
    """
    owner = await _company(client, "OWNA")
    other = await _company(client, "OTHB")
    note = await _add(client, owner, "notes", _NOTE)
    thesis = await _add(client, owner, "theses", _THESIS)
    for method, url, body, item in _routes(other, note["id"], thesis["id"]):
        if item is None:
            continue
        response = await client.request(method, url, json=body)
        assert response.status_code == 404, (method, url)
        assert response.json() == {"detail": _MISSING[item]}
    assert await _listed(client, owner, "notes") == [note]
    assert await _listed(client, owner, "theses") == [thesis]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0", 422),
        ("-1", 422),
        ("abc", 422),
        (str(2**63), 422),
        (str(_LARGEST_ID), 404),
    ],
    ids=["zero", "negative", "text", "2**63", "2**63-1"],
)
async def test_ids_are_bounded(client, raw, expected):
    """Every id is an integer from 1 to 2**63 - 1, else 422, never 500.

    ``raw`` goes in each id position of every route. The largest id
    passes the check and finds nothing, so it is the 404 of that
    position.
    """
    company_id = await _company(client, "IDS")
    note = await _add(client, company_id, "notes", _NOTE)
    thesis = await _add(client, company_id, "theses", _THESIS)
    # ``raw`` as the instrument id on all ten routes, then as the
    # note or thesis id on the six item routes.
    cases = [
        (method, url, body, "instrument_id")
        for method, url, body, _ in _routes(raw, note["id"], thesis["id"])
    ] + [
        (method, url, body, item)
        for method, url, body, item in _routes(company_id, raw, raw)
        if item is not None
    ]
    for method, url, body, name in cases:
        response = await client.request(method, url, json=body)
        assert response.status_code == expected, (method, url)
        if expected == 422:
            assert _only_error(response)["loc"] == ["path", name]
        else:
            assert response.json() == {"detail": _MISSING[name]}
    assert await _listed(client, company_id, "notes") == [note]
    assert await _listed(client, company_id, "theses") == [thesis]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value", ["open", "ACTIVE", ""], ids=["open", "upper-case", "empty"]
)
async def test_status_filter_rejects_other_values(client, value):
    """Only ``active`` and ``closed`` filter, in lowercase."""
    company_id = await _company(client, "STAT")
    response = await client.get(
        f"{API}/{company_id}/theses", params={"status": value}
    )
    error = _only_error(response)
    assert error["loc"] == ["query", "status"]
    assert error["type"] == "enum"


# (resource, field, its limit, the other required fields)
_LENGTH_CASES = (
    ("notes", "body", NOTE_BODY_MAX, {}),
    ("theses", "title", THESIS_TITLE_MAX, {"body": "b"}),
    ("theses", "body", THESIS_BODY_MAX, {"title": "t"}),
    ("theses", "thesis_breakers", THESIS_BREAKERS_MAX, _THESIS),
)


@pytest.mark.asyncio
async def test_lengths_and_text_rules(client):
    """The write models' text rules reach the API as 201, 200, or 422.

    Each limit passes and one more character is ``string_too_long``,
    on POST and on PUT. CRLF is stored as LF. A blank body and an
    unknown key are 422. A 422 stores nothing.
    """
    company_id = await _company(client, "TEXT")
    base = f"{API}/{company_id}"
    for resource, field, limit, rest in _LENGTH_CASES:
        case = (resource, field)
        fits = await client.post(
            f"{base}/{resource}", json={**rest, field: "x" * limit}
        )
        assert fits.status_code == 201, case
        assert fits.json()[field] == "x" * limit
        item_url = f"{base}/{resource}/{fits.json()['id']}"
        too_long = (
            await client.post(
                f"{base}/{resource}", json={**rest, field: "x" * (limit + 1)}
            ),
            await client.put(item_url, json={field: "y" * (limit + 1)}),
        )
        for response in too_long:
            error = _only_error(response)
            assert error["loc"] == ["body", field], case
            assert error["type"] == "string_too_long", case
            assert error["ctx"] == {"max_length": limit}, case
        edited = await client.put(item_url, json={field: "y" * limit})
        assert edited.status_code == 200, case
        assert edited.json()[field] == "y" * limit

    # A Windows newline is stored as one LF.
    note = await _add(client, company_id, "notes", {"body": "a\r\nb"})
    thesis = await _add(
        client,
        company_id,
        "theses",
        {"title": "t", "body": "a\r\nb", "thesis_breakers": "a\r\nb"},
    )
    stored_note = (await client.get(f"{base}/notes/{note['id']}")).json()
    assert stored_note["body"] == "a\nb"
    stored = (await client.get(f"{base}/theses/{thesis['id']}")).json()
    assert stored["body"] == "a\nb"
    assert stored["thesis_breakers"] == "a\nb"

    for resource, payload in (
        ("notes", {"body": "   "}),
        ("theses", {"title": "t", "body": "   "}),
    ):
        blank = await client.post(f"{base}/{resource}", json=payload)
        error = _only_error(blank)
        assert error["loc"] == ["body", "body"]
        assert error["ctx"]["error"]["code"] == "blank"

    misspelled = await client.post(
        f"{base}/notes", json={**_NOTE, "boddy": "x"}
    )
    error = _only_error(misspelled)
    assert error["type"] == "extra_forbidden"
    assert error["loc"] == ["body", "boddy"]
    unknown = await client.put(
        f"{base}/theses/{thesis['id']}", json={"state": "closed"}
    )
    error = _only_error(unknown)
    assert error["type"] == "extra_forbidden"
    assert error["loc"] == ["body", "state"]

    # One note per length case plus the CRLF note; the same for theses.
    assert len(await _listed(client, company_id, "notes")) == 2
    assert len(await _listed(client, company_id, "theses")) == 4


# (repository, its method, HTTP method, path after the instrument, body)
_WRITES = (
    (NoteRepository, "create", "POST", "notes", _NOTE),
    (NoteRepository, "update", "PUT", "notes/{note}", _NOTE),
    (NoteRepository, "delete", "DELETE", "notes/{note}", None),
    (ThesisRepository, "create", "POST", "theses", _THESIS),
    (
        ThesisRepository,
        "update",
        "PUT",
        "theses/{thesis}",
        {"status": "closed"},
    ),
    (ThesisRepository, "delete", "DELETE", "theses/{thesis}", None),
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("repository", "name", "method", "path", "body"),
    _WRITES,
    ids=[
        "note-create",
        "note-update",
        "note-delete",
        "thesis-create",
        "thesis-update",
        "thesis-delete",
    ],
)
async def test_storage_failure_is_a_fixed_500(
    client, monkeypatch, repository, name, method, path, body
):
    """``ResearchStorageError`` on any write is 500 with one sentence.

    The body is exactly that sentence. Nothing else from the
    exception is sent.
    """
    company_id = await _company(client, "FAIL")
    note = await _add(client, company_id, "notes", _NOTE)
    thesis = await _add(client, company_id, "theses", _THESIS)

    def fail(self, *args):
        raise ResearchStorageError()

    monkeypatch.setattr(repository, name, fail)
    url = f"{API}/{company_id}/" + path.format(
        note=note["id"], thesis=thesis["id"]
    )
    response = await client.request(method, url, json=body)
    assert response.status_code == 500
    assert response.json() == _NOT_STORED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("repository", "resource", "payload"),
    [(NoteRepository, "notes", _NOTE), (ThesisRepository, "theses", _THESIS)],
    ids=["note", "thesis"],
)
async def test_company_deleted_before_the_insert_is_the_instrument_404(
    client, monkeypatch, repository, resource, payload
):
    """The company can disappear after the route's own check.

    ``create`` then raises ``CompanyNotFoundError``. That is the same
    404 as an unknown instrument, not the 500.
    """
    company_id = await _company(client, "GONE")
    original = repository.create

    def delete_then_create(self, company_id, item):
        self.db.delete(self.db.get(CompanyDB, company_id))
        self.db.commit()
        return original(self, company_id, item)

    monkeypatch.setattr(repository, "create", delete_then_create)
    response = await client.post(
        f"{API}/{company_id}/{resource}", json=payload
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Instrument not found"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status_code"),
    [(ResearchStorageError(), 500), (CompanyNotFoundError(1), 404)],
    ids=["storage", "company"],
)
async def test_http_errors_are_raised_outside_the_handler(
    client, monkeypatch, error, status_code
):
    """The HTTP error does not carry the repository error.

    Raised inside the ``except`` block, even with ``from None``, the
    HTTP error would keep the repository error on ``__context__``.
    """
    from app.api.research import create_note

    company_id = await _company(client, "CTX")

    def fail(self, *args):
        raise error

    monkeypatch.setattr(NoteRepository, "create", fail)
    with client.app.state.testing_session_local() as db:
        with pytest.raises(HTTPException) as caught:
            create_note(
                instrument_id=company_id, note=NoteCreate(**_NOTE), db=db
            )
    assert caught.value.status_code == status_code
    assert caught.value.__context__ is None


@pytest.mark.asyncio
async def test_openapi_lists_notes_and_theses(client):
    schema = (await client.get("/api/v1/openapi.json")).json()
    paths = schema["paths"]
    notes = "/api/v1/instruments/{instrument_id}/notes"
    theses = "/api/v1/instruments/{instrument_id}/theses"
    # {method: success status}
    on_list = {"get": "200", "post": "201"}
    on_item = {"get": "200", "put": "200", "delete": "204"}
    expected = {
        notes: ("notes", on_list),
        notes + "/{note_id}": ("notes", on_item),
        theses: ("theses", on_list),
        theses + "/{thesis_id}": ("theses", on_item),
    }
    for path, (tag, operations) in expected.items():
        assert set(paths[path]) == set(operations), path
        for method, success in operations.items():
            assert paths[path][method]["tags"] == [tag]
            assert success in paths[path][method]["responses"]

    components = schema["components"]["schemas"]
    note_body = components["NoteCreate"]["properties"]["body"]
    assert note_body["maxLength"] == NOTE_BODY_MAX
    title = components["ThesisCreate"]["properties"]["title"]
    assert title["maxLength"] == THESIS_TITLE_MAX

    # The id bound is documented as the exact integer, not a float.
    parameters = {
        parameter["name"]: parameter["schema"]
        for parameter in paths[notes + "/{note_id}"]["get"]["parameters"]
    }
    for name in ("instrument_id", "note_id"):
        assert parameters[name]["exclusiveMinimum"] == 0
        assert parameters[name]["maximum"] == _LARGEST_ID
        assert type(parameters[name]["maximum"]) is int
