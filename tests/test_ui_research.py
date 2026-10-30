"""The sticky note beside the heart, and the research panel it opens.

The panel lists theses and notes. Its forms add, edit, and delete
notes and theses, and close and reopen theses. Notes and theses are
stored through ``NoteRepository`` and
``ThesisRepository`` on the test database. The database stamps an
insert with the current time, so every timestamp a test asserts is
pinned on the table row afterwards. No market-data provider is called.

The pinned times are UTC. The panel shows them in Polish time. Summer
time ended on 25 October 2026, so on 28 and 29 October Poland is at
UTC+1: 13:05Z is 14:05, and 23:30Z is already the next day.
"""

import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import pytest

from app.models.database_models import CompanyDB, NoteDB, ThesisDB
from app.models.research import (
    Note,
    NoteCreate,
    NoteUpdate,
    Thesis,
    ThesisCreate,
    ThesisStatus,
)
from app.repositories.company_errors import CompanyNotFoundError
from app.repositories.note_repository import NoteRepository
from app.repositories.research_store import ResearchStorageError
from app.repositories.thesis_repository import ThesisRepository
from app.ui.catalog import CATALOGS
from app.ui.formatting import format_local_date, format_local_datetime
from app.ui.research_view import NewNote, PanelForm, ResearchPanel
from app.ui.templating import MessageCatalog, templates
from tests.ui_html import FormInParagraph, assert_labeled

UI_CSS = Path(__file__).resolve().parents[1] / "static" / "ui.css"
_SCRIPT = "<script>alert(1)</script>"
_ESCAPED = "&lt;script&gt;alert(1)&lt;/script&gt;"
_HTMX = {"hx-request": "true"}
_ORIGIN = "http://127.0.0.1"
_NOT_STORED = "Nie udało się zapisać. Spróbuj ponownie."
# A valid thesis form, as the browser posts it.
_NEW_THESIS = {
    "title": "Nowa teza",
    "body": "Nowy powód.",
    "thesis_breakers": "Nowy próg.",
}
# Elements without an end tag. The text parser below must not wait
# for one.
_VOID = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    }
)


def _utc(text):
    """``"2026-10-28T13:05"`` as an aware UTC datetime."""
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


def _session(client):
    return client.app.state.testing_session_local()


def _company(client, name="Apple Inc.", ticker="AAPL"):
    session = _session(client)
    try:
        row = CompanyDB(name=name, ticker=ticker, currency="USD")
        session.add(row)
        session.commit()
        return row.id
    finally:
        session.close()


def _note(client, company_id, body, created, edited=None):
    """Store a note, edit it when ``edited`` is set, then pin the times.

    A note that was not edited keeps ``updated_at == created_at``, as
    the insert leaves it.
    """
    session = _session(client)
    try:
        notes = NoteRepository(session)
        note_id = notes.create(company_id, NoteCreate(body=body)).id
        if edited is not None:
            notes.update(company_id, note_id, NoteUpdate(body=body))
        row = session.get(NoteDB, note_id)
        row.created_at = _utc(created)
        row.updated_at = _utc(edited or created)
        session.commit()
        return note_id
    finally:
        session.close()


def _thesis(
    client,
    company_id,
    title,
    created,
    *,
    body="Powód zakupu.",
    breakers="",
    closed=None,
    updated=None,
):
    """Store a thesis, close it at ``closed`` if set, then pin the times.

    ``updated`` defaults to the last change: the closing, else the
    creation.
    """
    session = _session(client)
    try:
        theses = ThesisRepository(session)
        thesis = ThesisCreate(title=title, body=body, thesis_breakers=breakers)
        thesis_id = theses.create(company_id, thesis).id
        if closed is not None:
            theses.set_status(company_id, thesis_id, ThesisStatus.CLOSED)
        row = session.get(ThesisDB, thesis_id)
        row.created_at = _utc(created)
        row.updated_at = _utc(updated or closed or created)
        if closed is not None:
            row.closed_at = _utc(closed)
        session.commit()
        return thesis_id
    finally:
        session.close()


class _Tags(HTMLParser):
    """Every start tag in document order, with its attributes."""

    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class _Texts(HTMLParser):
    """The text inside each element that has an id, children included."""

    def __init__(self):
        super().__init__()
        self.open = []
        self.texts = {}

    def handle_starttag(self, tag, attrs):
        if tag in _VOID:
            return
        element_id = dict(attrs).get("id")
        self.open.append((tag, element_id))
        if element_id is not None:
            self.texts.setdefault(element_id, "")

    def handle_endtag(self, tag):
        if tag not in [open_tag for open_tag, _ in self.open]:
            return
        while self.open.pop()[0] != tag:
            pass

    def handle_data(self, data):
        for _, element_id in self.open:
            if element_id is not None:
                self.texts[element_id] += data


def _tags(html):
    parser = _Tags()
    parser.feed(html)
    return parser.tags


def _attrs(html, element_id):
    """The attributes of the one element with this id."""
    found = [
        attrs for _, attrs in _tags(html) if attrs.get("id") == element_id
    ]
    assert len(found) == 1, (element_id, len(found))
    return found[0]


def _text(html, element_id):
    parser = _Texts()
    parser.feed(html)
    return parser.texts[element_id]


def _next_state(html):
    """The hidden ``research`` value: what the next click asks for."""
    values = [
        attrs["value"]
        for tag, attrs in _tags(html)
        if tag == "input" and attrs.get("name") == "research"
    ]
    assert len(values) == 1
    return values[0]


def _oob_ids(html):
    """Ids of the elements that HTMX swaps out of band."""
    return {
        attrs.get("id") for _, attrs in _tags(html) if "hx-swap-oob" in attrs
    }


def _between(html, start_marker, end_marker):
    """From ``start_marker`` up to the next ``end_marker``."""
    start = html.index(start_marker)
    end = html.index(end_marker, start)
    return html[start:end]


def _panel(html):
    """The open panel, from its start tag to its end tag."""
    return _between(html, '<section id="research"', "</section>")


def _closed_list(html):
    return _between(html, "<details", "</details>")


def _assert_toggle(html, company_id, *, expanded, next_state, label):
    """The sticky-note form and its button, every pinned attribute."""
    form = _attrs(html, "research-toggle")
    assert form["method"] == "get"
    assert form["action"] == f"/ui/instruments/{company_id}#research"
    assert form["hx-get"] == f"/ui/companies/{company_id}/research"
    assert form["hx-target"] == "#research"
    assert form["hx-swap"] == "outerHTML"
    assert form["hx-sync"] == "#research:drop"
    assert "data-plain-fallback" in form
    assert _next_state(html) == next_state
    button = _attrs(html, "research-toggle-button")
    assert button["type"] == "submit"
    assert button["aria-expanded"] == expanded
    assert button["aria-controls"] == "research"
    assert button["aria-label"] == label


def _assert_ui_headers(response):
    assert response.headers["content-security-policy"] == (
        "default-src 'self'; base-uri 'self'; "
        "form-action 'self'; frame-ancestors 'none'"
    )
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "same-origin"
    assert response.headers["vary"] == "HX-Request"
    assert response.headers["cache-control"] == "no-store"


def _css_declarations(selector):
    """``(property, value)`` pairs of every ui.css rule naming ``selector``.

    A rule counts when ``selector`` is one of its comma-separated
    selectors. Comments are dropped first, because a comment above a
    rule would otherwise be read as part of its selector.
    """
    css = UI_CSS.read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    found = set()
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if selector not in {part.strip() for part in selectors.split(",")}:
            continue
        for declaration in body.split(";"):
            name, _, value = declaration.partition(":")
            if value.strip():
                found.add((name.strip(), " ".join(value.split())))
    return found


async def _post(client, path, data=None, *, origin=_ORIGIN, htmx=False):
    """POST a panel form the way the browser does: same origin, form data."""
    headers = {}
    if origin is not None:
        headers["origin"] = origin
    if htmx:
        headers.update(_HTMX)
    return await client.post(path, data=data or {}, headers=headers)


def _stored_notes(client, company_id):
    """``{id: body}`` of the company's notes, read from the table."""
    session = _session(client)
    try:
        rows = session.query(NoteDB).filter(NoteDB.company_id == company_id)
        return {row.id: row.body for row in rows}
    finally:
        session.close()


def _stored_theses(client, company_id):
    """``{id: Thesis}`` of the company's theses, read from the table.

    ``Thesis`` models compare field by field, so two reads are equal
    exactly when nothing was stored in between.
    """
    session = _session(client)
    try:
        theses = ThesisRepository(session).list_for_company(company_id)
        return {thesis.id: thesis for thesis in theses}
    finally:
        session.close()


def _updated_at(client, note_id):
    session = _session(client)
    try:
        return session.get(NoteDB, note_id).updated_at
    finally:
        session.close()


def _autofocus_ids(html):
    """Ids of the elements that carry ``autofocus``, in page order."""
    return [
        attrs.get("id") for _, attrs in _tags(html) if "autofocus" in attrs
    ]


def _focus(response):
    """The id of the one element that takes the focus in this answer."""
    focused = _autofocus_ids(response.text)
    assert response.text.count("autofocus") == 1, focused
    [element_id] = focused
    return element_id


def _panel_actions(html):
    """Every form and every HTMX link inside the open panel."""
    return [
        (tag, attrs)
        for tag, attrs in _tags(_panel(html))
        if tag == "form" or (tag == "a" and "hx-get" in attrs)
    ]


def _without_fragment(href):
    """``href`` up to its ``#``: the request a panel link sends.

    A browser never sends the fragment, so a link's ``hx-get`` is its
    ``href`` without it. HTMX would keep a fragment in ``hx-get`` and
    scroll to it after the swap.
    """
    return href.partition("#")[0]


def _link(html, href):
    """The attributes of the one link to ``href`` inside the panel."""
    found = [
        attrs
        for tag, attrs in _tags(_panel(html))
        if tag == "a" and attrs.get("href") == href
    ]
    assert len(found) == 1, (href, len(found))
    return found[0]


def _fail_storage(*args, **kwargs):
    """Stands in for a repository write whose commit failed."""
    raise ResearchStorageError()


@pytest.mark.asyncio
async def test_toggle_sits_beside_the_heart(client):
    company_id = _company(client)
    _note(client, company_id, "Pierwsza notatka", "2026-10-20T08:00")
    _note(client, company_id, "Druga notatka", "2026-10-21T08:00")
    _thesis(client, company_id, "Teza", "2026-10-22T08:00")
    response = await client.get(f"/ui/instruments/{company_id}")
    assert response.status_code == 200
    html = response.text

    name = _between(html, '<div class="instrument-name">', "</div>")
    heart_at = name.index('class="watchlist-heart"')
    assert heart_at < name.index('id="research-toggle"')
    _assert_toggle(
        html,
        company_id,
        expanded="false",
        next_state="open",
        label="Notatki i tezy (3)",
    )
    assert _text(html, "research-toggle-button").strip() == "3"
    assert '<div id="research"></div>' in html
    assert "hx-swap-oob" not in html

    empty_id = _company(client, name="Empty Co", ticker="EMPTY")
    empty = (await client.get(f"/ui/instruments/{empty_id}")).text
    _assert_toggle(
        empty,
        empty_id,
        expanded="false",
        next_state="open",
        label="Notatki i tezy",
    )
    assert _text(empty, "research-toggle-button").strip() == ""


@pytest.mark.asyncio
async def test_open_panel_lists_theses_then_notes(client):
    company_id = _company(client)
    # Each pair is stored so that the repository order (last edit
    # first) and the panel order disagree. The panel sorts on its own.
    older = _thesis(
        client,
        company_id,
        "Starsza teza",
        "2026-10-21T08:00",
        updated="2026-10-28T08:00",
    )
    newer = _thesis(
        client,
        company_id,
        "Nowsza teza",
        "2026-10-26T08:00",
        breakers="Spadek marży",
    )
    closed_late = _thesis(
        client,
        company_id,
        "Zamknięta później",
        "2026-10-01T08:00",
        closed="2026-10-27T08:00",
    )
    closed_early = _thesis(
        client,
        company_id,
        "Zamknięta wcześniej",
        "2026-10-05T08:00",
        closed="2026-10-22T08:00",
        updated="2026-10-28T09:00",
    )
    old_note = _note(
        client,
        company_id,
        "Stara notatka",
        "2026-10-20T08:00",
        edited="2026-10-29T09:00",
    )
    new_note = _note(client, company_id, "Nowa notatka", "2026-10-25T08:00")
    research = f"/ui/companies/{company_id}/research"
    answers = (
        await client.get(f"/ui/instruments/{company_id}?research=open"),
        await client.get(research),
        await client.get(research, headers=_HTMX),
    )
    for response in answers:
        assert response.status_code == 200
        html = response.text
        _assert_toggle(
            html,
            company_id,
            expanded="true",
            next_state="closed",
            label="Notatki i tezy (6)",
        )
        panel = _panel(html)
        assert panel.index("<h3>Tezy</h3>") < panel.index("<h3>Notatki</h3>")
        assert panel.index(f'id="thesis-{newer}"') < panel.index(
            f'id="thesis-{older}"'
        )
        closed = _closed_list(panel)
        assert "<summary>Zamknięte tezy (2)</summary>" in closed
        assert closed.index(f'id="thesis-{closed_late}"') < closed.index(
            f'id="thesis-{closed_early}"'
        )
        assert f'id="thesis-{newer}"' not in closed
        assert f'id="thesis-{older}"' not in closed
        assert panel.index(f'id="note-{new_note}"') < panel.index(
            f'id="note-{old_note}"'
        )
        assert html.count("edytowano 29.10.2026, 10:00") == 1
        assert "edytowano 29.10.2026, 10:00" in _text(html, f"note-{old_note}")
        assert "edytowano" not in _text(html, f"note-{new_note}")
        assert "Spadek marży" in _text(html, f"thesis-{newer}")
        assert "brak danych" in _text(html, f"thesis-{older}")
        for empty_state in (
            "Brak tez.",
            "Brak aktywnych tez.",
            "Brak notatek.",
        ):
            assert empty_state not in html
    assert "<html" in answers[1].text
    assert "<html" not in answers[2].text

    only_closed = _company(client, name="Only Closed", ticker="CLSD")
    _thesis(
        client,
        only_closed,
        "Stara teza",
        "2026-10-01T08:00",
        closed="2026-10-02T08:00",
    )
    html = (
        await client.get(f"/ui/instruments/{only_closed}?research=open")
    ).text
    assert "Brak aktywnych tez." in _panel(html)
    assert "Brak tez." not in html
    assert "Brak notatek." in _panel(html)

    notes_only = _company(client, name="Notes Only", ticker="NOTES")
    _note(client, notes_only, "Tylko notatka", "2026-10-01T08:00")
    html = (
        await client.get(f"/ui/instruments/{notes_only}?research=open")
    ).text
    assert "Brak tez." in _panel(html)
    assert "<details" not in html
    assert "Brak aktywnych tez." not in html
    assert "Brak notatek." not in html


@pytest.mark.asyncio
async def test_closed_thesis_without_a_date_is_listed_last(client):
    """A closed thesis written past the repository can lack ``closed_at``.

    It comes after the closed theses that have a date, and its card
    has no closing date.
    """
    company_id = _company(client)
    undated = _thesis(
        client,
        company_id,
        "Bez daty",
        "2026-10-10T08:00",
        closed="2026-10-28T08:00",
    )
    dated = _thesis(
        client,
        company_id,
        "Z datą",
        "2026-10-01T08:00",
        closed="2026-10-02T08:00",
    )
    session = _session(client)
    try:
        session.get(ThesisDB, undated).closed_at = None
        session.commit()
    finally:
        session.close()
    html = (
        await client.get(f"/ui/instruments/{company_id}?research=open")
    ).text
    closed = _closed_list(html)
    assert "<summary>Zamknięte tezy (2)</summary>" in closed
    assert closed.index(f'id="thesis-{dated}"') < closed.index(
        f'id="thesis-{undated}"'
    )
    assert "zamknięta 02.10.2026" in _text(html, f"thesis-{dated}")
    assert "od 10.10.2026" in _text(html, f"thesis-{undated}")
    assert re.search(r"zamknięta \d", _text(html, f"thesis-{undated}")) is None


@pytest.mark.asyncio
async def test_dates_use_polish_time(client):
    company_id = _company(client)
    note_id = _note(client, company_id, "Notatka", "2026-10-28T13:05")
    thesis_id = _thesis(
        client,
        company_id,
        "Teza",
        "2026-10-28T23:30",
        closed="2026-10-28T23:30",
    )
    html = (
        await client.get(f"/ui/instruments/{company_id}?research=open")
    ).text
    assert "28.10.2026, 14:05" in _text(html, f"note-{note_id}")
    card = _text(html, f"thesis-{thesis_id}")
    assert "od 29.10.2026" in card
    assert "zamknięta 29.10.2026" in card
    assert "28.10.2026" not in card


@pytest.mark.asyncio
async def test_panel_fragment_and_closing(client):
    """The second click must close the panel.

    The fragment carries the whole sticky-note form out of band, so
    its hidden ``research`` value flips with every answer. The
    language switch's return path follows the panel the same way.
    """
    company_id = _company(client)
    _note(client, company_id, "Notatka", "2026-10-28T13:05")
    research = f"/ui/companies/{company_id}/research"

    opened = await client.get(research, headers=_HTMX)
    assert opened.status_code == 200
    html = opened.text
    assert "<html" not in html.casefold()
    assert _attrs(html, "research")["hx-sync"] == "this:drop"
    assert html.count('<section id="research"') == 1
    assert _oob_ids(html) == {
        "research-toggle",
        "language-next-pl",
        "language-next-en",
    }
    assert _attrs(html, "research-toggle")["hx-swap-oob"] == "true"
    _assert_toggle(
        html,
        company_id,
        expanded="true",
        next_state="closed",
        label="Notatki i tezy (1)",
    )
    for code in ("pl", "en"):
        language_next = _attrs(html, f"language-next-{code}")
        assert language_next["hx-swap-oob"] == "outerHTML"
        assert language_next["value"] == (
            f"/ui/instruments/{company_id}?research=open"
        )
    assert "autofocus" not in html
    _assert_ui_headers(opened)

    closed = await client.get(
        research, params={"research": "closed"}, headers=_HTMX
    )
    assert closed.status_code == 200
    html = closed.text
    assert '<div id="research"></div>' in html
    assert "<section" not in html
    assert _oob_ids(html) == {
        "research-toggle",
        "language-next-pl",
        "language-next-en",
    }
    _assert_toggle(
        html,
        company_id,
        expanded="false",
        next_state="open",
        label="Notatki i tezy (1)",
    )
    for code in ("pl", "en"):
        language_next = _attrs(html, f"language-next-{code}")
        assert language_next["value"] == f"/ui/instruments/{company_id}"
    assert "autofocus" not in html
    _assert_ui_headers(closed)


@pytest.mark.asyncio
async def test_script_payload_is_escaped_in_the_panel(client):
    company_id = _company(client)
    _note(client, company_id, _SCRIPT, "2026-10-28T13:05")
    _thesis(
        client,
        company_id,
        _SCRIPT,
        "2026-10-28T13:05",
        body=_SCRIPT,
        breakers=_SCRIPT,
    )
    page = await client.get(f"/ui/instruments/{company_id}?research=open")
    fragment = await client.get(
        f"/ui/companies/{company_id}/research", headers=_HTMX
    )
    for html in (page.text, fragment.text):
        assert "<script>alert" not in html
        assert f'class="thesis-title">{_ESCAPED}</h4>' in html
        assert html.count(f'class="research-text">{_ESCAPED}</p>') == 3


@pytest.mark.asyncio
async def test_research_text_keeps_breaks_and_wraps(client):
    """Text shows as typed: line breaks kept, no added indentation.

    ``white-space: pre-wrap`` shows every space and newline, so the
    value must touch its tags. A long word wraps instead of widening
    the page.
    """
    company_id = _company(client)
    _note(client, company_id, "line1\nline2", "2026-10-28T13:05")
    title = "a" * 200
    _thesis(
        client,
        company_id,
        title,
        "2026-10-28T13:05",
        body="line1\nline2",
        breakers="line1\nline2",
    )
    html = (
        await client.get(f"/ui/instruments/{company_id}?research=open")
    ).text
    assert html.count('class="research-text">line1\nline2</p>') == 3
    assert f'class="thesis-title">{title}</h4>' in html
    text_rules = _css_declarations(".research-text")
    assert ("white-space", "pre-wrap") in text_rules
    assert ("overflow-wrap", "anywhere") in text_rules
    assert ("overflow-wrap", "anywhere") in _css_declarations(".thesis-title")


def test_thesis_actions_are_spaced_like_note_actions():
    """A thesis card's actions row is a form; a note's is a ``<p>``.

    The browser gives a ``<p>`` ``margin: 1em 0``, and ui.css sets no
    paragraph margin. The form rule repeats that margin, so both rows
    sit the same distance under their text.
    """
    assert ("margin", "1em 0") in _css_declarations(
        ".research-item form.form-actions"
    )
    assert not any(
        name.startswith("margin") for name, _ in _css_declarations("p")
    )


@pytest.mark.asyncio
async def test_panel_in_english(client):
    company_id = _company(client)
    _note(client, company_id, "A note", "2026-10-28T13:05")
    _thesis(client, company_id, "A thesis", "2026-10-28T13:05")
    client.cookies.set("ui_lang", "en")
    html = (
        await client.get(f"/ui/instruments/{company_id}?research=open")
    ).text
    assert _attrs(html, "research-toggle-button")["aria-label"] == (
        "Notes and theses (2)"
    )
    panel = _panel(html)
    assert "Notes and theses" in panel
    assert "<h3>Theses</h3>" in panel
    assert "Why I bought" in panel
    assert "Oct 28, 2026, 14:05" in panel


@pytest.mark.asyncio
@pytest.mark.parametrize("raw_id", ["abc", "01", "999999"])
@pytest.mark.parametrize("htmx", [False, True])
async def test_unknown_company_panel_is_the_instrument_404(
    client, raw_id, htmx
):
    # Company 1 exists, so a lenient parse of ``01`` would find it.
    assert _company(client) == 1
    headers = _HTMX if htmx else {}
    for path in (
        f"/ui/companies/{raw_id}/research",
        f"/ui/instruments/{raw_id}?research=open",
    ):
        response = await client.get(path, headers=headers)
        assert response.status_code == 404, path
        assert "text/html" in response.headers["content-type"]
        assert "Nie znaleziono instrumentu" in response.text
        _assert_ui_headers(response)


@pytest.mark.asyncio
async def test_open_panel_keeps_the_page_layout(client):
    company_id = _company(client)
    _note(client, company_id, "Notatka", "2026-10-28T13:05")
    _thesis(client, company_id, "Teza", "2026-10-28T13:05")
    _thesis(
        client,
        company_id,
        "Zamknięta",
        "2026-10-01T08:00",
        closed="2026-10-02T08:00",
    )
    html = (
        await client.get(f"/ui/instruments/{company_id}?research=open")
    ).text
    assert html.count('id="watchlist-heart-button"') == 1
    assert html.count('id="research-toggle-button"') == 1
    parser = FormInParagraph()
    parser.feed(html)
    assert parser.nested is False
    assert "style=" not in html


@pytest.mark.asyncio
async def test_focus_names_one_item_or_nothing(client):
    """``focus`` puts ``autofocus`` on that note or thesis, and only there.

    Only ``note-<digits>`` and ``thesis-<digits>`` are accepted. Any
    other value is ignored and never written into the page. A
    well-formed id that names no item in this panel, such as a note
    deleted in another tab or another company's thesis, gives the
    focus to the panel heading, so it never drops to the top of the
    page.
    """
    company_id = _company(client)
    note_id = _note(client, company_id, "Notatka", "2026-10-28T13:05")
    thesis_id = _thesis(client, company_id, "Teza", "2026-10-28T13:05")
    other_id = _company(client, name="Microsoft Corp.", ticker="MSFT")
    other_thesis = _thesis(client, other_id, "Cudza", "2026-10-28T13:05")
    research = f"/ui/companies/{company_id}/research"
    for element_id in (f"note-{note_id}", f"thesis-{thesis_id}"):
        for headers in ({}, _HTMX):
            response = await client.get(
                research, params={"focus": element_id}, headers=headers
            )
            assert response.status_code == 200
            assert response.text.count("autofocus") == 1
            assert "autofocus" in _attrs(response.text, element_id)
    for missing in (f"note-{note_id + 100}", f"thesis-{other_thesis}"):
        for headers in ({}, _HTMX):
            response = await client.get(
                research, params={"focus": missing}, headers=headers
            )
            assert response.status_code == 200, missing
            assert response.text.count("autofocus") == 1, missing
            assert "autofocus" in _attrs(response.text, "research-title")
    for ignored in (
        "research-title",
        f"note-{note_id}\n",
        "note-١",
        f'note-{note_id}" onfocus="x',
        f"Note-{note_id}",
        "note-",
    ):
        response = await client.get(
            research, params={"focus": ignored}, headers=_HTMX
        )
        assert response.status_code == 200
        assert "autofocus" not in response.text
        assert "onfocus" not in response.text


def _render_panel(**fields):
    """Render the partial for a panel no route builds yet.

    ``fields`` override an empty open panel of company 1.
    """
    values = {
        "company_id": 1,
        "notes": [],
        "active_theses": [],
        "closed_theses": [],
        "form": None,
        "new_note": NewNote(),
        "show_closed": False,
        "focus": None,
        "state_path": "/ui/instruments/1?research=open",
    }
    values.update(fields)
    return templates.get_template("partials/research_panel.html").render(
        t=MessageCatalog("pl"),
        language="pl",
        format_local_date=format_local_date,
        format_local_datetime=format_local_datetime,
        research_panel=ResearchPanel(**values),
    )


def test_panel_focus_can_name_the_heading():
    """The panel heading is a focus target too (``tabindex="-1"``).

    The ``focus`` parameter itself never names the heading. The
    heading takes the focus when that parameter names an item the
    panel does not list, and after a delete that leaves no neighbour.
    """
    html = _render_panel(focus="research-title")
    assert html.count("autofocus") == 1
    assert "autofocus" in _attrs(html, "research-title")


def test_a_thesis_form_does_not_open_a_note_form():
    """Notes and theses have separate ids, so thesis 3 and note 3 exist.

    An inline form opens on a note only when its kind is a note kind.
    """
    note = Note(
        id=3,
        company_id=1,
        body="Notatka",
        created_at=_utc("2026-10-28T13:05"),
        updated_at=_utc("2026-10-28T13:05"),
    )
    for kind in ("thesis_edit", "thesis_delete", "thesis_status"):
        html = _render_panel(
            notes=[note],
            form=PanelForm(kind=kind, item_id=3, form_error="error.storage"),
        )
        assert 'id="note-3-body"' not in html
        assert 'id="note-3-delete-question"' not in html
        assert 'id="note-3-errors"' not in html
        assert 'href="/ui/companies/1/notes/3/edit"' in html
        assert 'href="/ui/companies/1/notes/3/delete"' in html


def test_a_note_form_does_not_open_a_thesis_form():
    """The other way round: a note form leaves thesis 3 as it is."""
    thesis = Thesis(
        id=3,
        company_id=1,
        title="Teza",
        body="Powód zakupu.",
        thesis_breakers="",
        status=ThesisStatus.ACTIVE,
        created_at=_utc("2026-10-28T13:05"),
        updated_at=_utc("2026-10-28T13:05"),
    )
    for kind in ("note_edit", "note_delete"):
        html = _render_panel(
            active_theses=[thesis],
            form=PanelForm(kind=kind, item_id=3, form_error="error.storage"),
        )
        assert 'id="thesis-3-title"' not in html
        assert 'id="thesis-3-delete-question"' not in html
        assert 'id="thesis-3-errors"' not in html
        assert 'id="thesis-3-status"' in html
        assert 'href="/ui/companies/1/theses/3/edit"' in html
        assert 'href="/ui/companies/1/theses/3/delete"' in html


def test_show_closed_unfolds_the_closed_theses():
    closed = Thesis(
        id=4,
        company_id=1,
        title="Stara teza",
        body="Powód zakupu.",
        thesis_breakers="",
        status=ThesisStatus.CLOSED,
        created_at=_utc("2026-10-01T08:00"),
        updated_at=_utc("2026-10-02T08:00"),
        closed_at=_utc("2026-10-02T08:00"),
    )
    folded = _render_panel(closed_theses=[closed])
    assert '<details class="research-closed">' in folded
    unfolded = _render_panel(closed_theses=[closed], show_closed=True)
    assert '<details class="research-closed" open>' in unfolded


@pytest.mark.asyncio
async def test_blank_breakers_show_no_data(client):
    """Breakers made only of whitespace count as empty.

    The write models strip, so only a row written past them can hold
    such a value.
    """
    company_id = _company(client)
    thesis_id = _thesis(client, company_id, "Teza", "2026-10-28T13:05")
    session = _session(client)
    try:
        session.get(ThesisDB, thesis_id).thesis_breakers = "  \n "
        session.commit()
    finally:
        session.close()
    html = (
        await client.get(f"/ui/instruments/{company_id}?research=open")
    ).text
    card = _between(html, f'id="thesis-{thesis_id}"', "</li>")
    assert "brak danych" in card
    assert card.count('class="research-text"') == 1


@pytest.mark.asyncio
async def test_add_note_plain_and_htmx(client):
    company_id = _company(client)
    path = f"/ui/companies/{company_id}/notes"

    fragment = await _post(
        client, path, {"body": " Pierwsza notatka "}, htmx=True
    )
    assert fragment.status_code == 200
    html = fragment.text
    assert "<html" not in html
    [note_id] = _stored_notes(client, company_id)
    assert _stored_notes(client, company_id) == {note_id: "Pierwsza notatka"}
    assert "Pierwsza notatka" in _text(html, f"note-{note_id}")
    # Its own success clears the field: the answer's copy replaces the
    # browser's, because the wrapper has no hx-preserve.
    assert _text(html, "note-new-body") == ""
    assert "hx-preserve" not in _attrs(html, "note-new-field")
    assert 'id="note-new-body"' in _between(
        html, 'id="note-new-field"', "</div>"
    )
    assert _focus(fragment) == "note-new-body"
    _assert_toggle(
        html,
        company_id,
        expanded="true",
        next_state="closed",
        label="Notatki i tezy (1)",
    )
    assert _text(html, "research-toggle-button").strip() == "1"
    _assert_ui_headers(fragment)

    plain = await _post(client, path, {"body": "Druga notatka"})
    assert plain.status_code == 303
    assert plain.headers["location"] == (
        f"/ui/instruments/{company_id}?research=open#research"
    )
    _assert_ui_headers(plain)
    assert sorted(_stored_notes(client, company_id).values()) == [
        "Druga notatka",
        "Pierwsza notatka",
    ]


@pytest.mark.asyncio
async def test_crlf_note_at_the_limit_is_saved(client):
    """A Windows newline counts as one character (Review Focus 2)."""
    company_id = _company(client)
    path = f"/ui/companies/{company_id}/notes"
    at_limit = "a" * 4999 + "\r\n" + "a" * 5000
    assert len(at_limit) == 10001
    saved = await _post(client, path, {"body": at_limit})
    assert saved.status_code == 303
    [body] = _stored_notes(client, company_id).values()
    assert len(body) == 10000
    assert body.count("\n") == 1
    assert "\r" not in body

    over = "a" * 5000 + "\r\n" + "a" * 5000
    for htmx in (False, True):
        response = await _post(client, path, {"body": over}, htmx=htmx)
        assert response.status_code == 422
        html = response.text
        # U+00A0, a no-break space: the app's Polish thousands
        # separator, so "10 000" never wraps between its two parts.
        assert "Najwyżej 10\u00a0000 znaków." in _text(
            html, "note-new-body-error"
        )
        assert "Najwyżej 10\u00a0000 znaków." in _text(html, "note-new-errors")
        assert _text(html, "note-new-body") == over
    assert len(_stored_notes(client, company_id)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("htmx", [False, True])
async def test_invalid_note_is_422_and_keeps_the_text(client, htmx):
    company_id = _company(client)
    path = f"/ui/companies/{company_id}/notes"
    blank = " \r\n\t "
    response = await _post(client, path, {"body": blank}, htmx=htmx)
    assert response.status_code == 422
    html = response.text
    assert _text(html, "note-new-body-error") == "To pole jest wymagane."
    textarea = _attrs(html, "note-new-body")
    assert textarea["aria-invalid"] == "true"
    assert textarea["aria-describedby"] == "note-new-body-error"
    assert_labeled(html)
    summary = _between(html, 'id="note-new-errors"', "</div>")
    # The link reads like the field's own label.
    assert '<a href="#note-new-body">Nowa notatka</a>' in summary
    assert "To pole jest wymagane." in summary
    assert _attrs(html, "note-new-errors")["tabindex"] == "-1"
    # It takes the focus, so it is no alert as well: a screen reader
    # would read it twice.
    assert "role" not in _attrs(html, "note-new-errors")
    assert _focus(response) == "note-new-errors"
    assert _text(html, "note-new-body") == blank
    # Its own 422 shows the field as the server rendered it.
    assert "hx-preserve" not in _attrs(html, "note-new-field")
    if htmx:
        assert "<html" not in html
    else:
        assert "<html" in html
        assert _attrs(html, "research-toggle-button")["aria-expanded"] == (
            "true"
        )
    assert html.count('<section id="research"') == 1

    payload = "</textarea>" + _SCRIPT + "a" * 10000
    response = await _post(client, path, {"body": payload}, htmx=htmx)
    assert response.status_code == 422
    html = response.text
    assert "</textarea><script>" not in html
    assert _SCRIPT not in html
    assert "&lt;/textarea&gt;&lt;script&gt;" in html
    assert _text(html, "note-new-body") == payload
    assert _stored_notes(client, company_id) == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("htmx", [False, True])
async def test_invalid_note_edit_keeps_the_text(client, htmx):
    company_id = _company(client)
    note_id = _note(client, company_id, "Stara treść", "2026-10-28T13:05")
    path = f"/ui/companies/{company_id}/notes/{note_id}/edit"
    typed = "a" * 10001
    response = await _post(client, path, {"body": typed}, htmx=htmx)
    assert response.status_code == 422
    html = response.text
    field = f"note-{note_id}-body"
    assert _text(html, field) == typed
    assert _attrs(html, field)["aria-invalid"] == "true"
    assert _attrs(html, field)["aria-describedby"] == f"{field}-error"
    assert _text(html, f"{field}-error") == "Najwyżej 10\u00a0000 znaków."
    assert_labeled(html)
    summary = _between(html, f'id="note-{note_id}-errors"', "</div>")
    assert f'<a href="#{field}">Treść notatki</a>' in summary
    assert "Najwyżej 10\u00a0000 znaków." in summary
    assert _focus(response) == f"note-{note_id}-errors"
    # The form sits in the note's own item.
    item = _between(html, f'<li id="note-{note_id}"', "</li>")
    assert f'action="{path}"' in item
    assert _stored_notes(client, company_id) == {note_id: "Stara treść"}


@pytest.mark.asyncio
async def test_draft_survives_other_actions(client):
    """Text typed in "Nowa notatka" outlives the other panel actions.

    HTMX keeps the browser's copy of an element when the answer's copy
    has ``hx-preserve``. The wrapper holds the field and its error.
    """
    company_id = _company(client)
    note_id = _note(client, company_id, "Notatka", "2026-10-28T13:05")
    research = f"/ui/companies/{company_id}/research"
    note = f"/ui/companies/{company_id}/notes/{note_id}"
    answers = (
        await client.get(research, headers=_HTMX),
        await client.get(f"{note}/edit", headers=_HTMX),
        await client.get(f"{note}/delete", headers=_HTMX),
        await client.get(
            research, params={"focus": f"note-{note_id}"}, headers=_HTMX
        ),
        await _post(client, f"{note}/edit", {"body": ""}, htmx=True),
        await _post(client, f"{note}/edit", {"body": "Zmiana"}, htmx=True),
        await _post(client, f"{note}/delete", htmx=True),
    )
    for response in answers:
        assert response.status_code in (200, 422)
        html = response.text
        assert '<div id="note-new-field" hx-preserve="true">' in html
        wrapper = _between(html, 'id="note-new-field"', "</div>")
        assert 'id="note-new-body"' in wrapper
        assert "autofocus" not in wrapper


@pytest.mark.asyncio
async def test_full_pages_put_no_autofocus_in_the_draft(client, monkeypatch):
    """A full page never focuses inside the preserved wrapper.

    ``ui.js`` removes a stale ``autofocus`` only after an HTMX swap.
    A full page that focused inside the wrapper would carry that
    attribute into the next HTMX answer, which keeps the wrapper.
    """
    company_id = _company(client)
    note_id = _note(client, company_id, "Notatka", "2026-10-28T13:05")
    note = f"/ui/companies/{company_id}/notes/{note_id}"
    pages = [
        await client.get(f"/ui/instruments/{company_id}?research=open"),
        await client.get(f"{note}/edit"),
        await client.get(f"{note}/delete"),
        await client.get(
            f"/ui/companies/{company_id}/research",
            params={"focus": f"note-{note_id}"},
        ),
        await _post(client, f"/ui/companies/{company_id}/notes"),
        await _post(client, f"{note}/edit"),
    ]
    monkeypatch.setattr(NoteRepository, "create", _fail_storage)
    pages.append(
        await _post(
            client, f"/ui/companies/{company_id}/notes", {"body": "Nowa"}
        )
    )
    for page in pages:
        assert "<html" in page.text
        wrapper = _between(page.text, 'id="note-new-field"', "</div>")
        assert "autofocus" not in wrapper


@pytest.mark.asyncio
async def test_edit_note_inline(client):
    company_id = _company(client)
    first = _note(client, company_id, "Pierwsza", "2026-10-28T13:05")
    second = _note(client, company_id, "Druga", "2026-10-28T14:05")
    edit = f"/ui/companies/{company_id}/notes/{first}/edit"
    field = f"note-{first}-body"

    fragment = await client.get(edit, headers=_HTMX)
    assert fragment.status_code == 200
    html = fragment.text
    assert "<html" not in html
    assert _text(html, field) == "Pierwsza"
    assert _focus(fragment) == field
    item = _between(html, f'<li id="note-{first}"', "</li>")
    assert f'action="{edit}"' in item
    assert "Zapisz" in item
    assert_labeled(html)

    page = await client.get(edit)
    assert page.status_code == 200
    assert "<html" in page.text
    assert _attrs(page.text, "research-toggle-button")["aria-expanded"] == (
        "true"
    )
    assert _text(page.text, field) == "Pierwsza"
    assert _focus(page) == field

    # Only one inline form is open at a time.
    other = await client.get(
        f"/ui/companies/{company_id}/notes/{second}/edit", headers=_HTMX
    )
    assert f'id="note-{second}-body"' in other.text
    assert f'id="{field}"' not in other.text
    assert other.text.count("<textarea") == 2

    saved = await _post(client, edit, {"body": "Poprawiona"})
    assert saved.status_code == 303
    assert saved.headers["location"] == (
        f"/ui/instruments/{company_id}?research=open#research"
    )
    assert _stored_notes(client, company_id)[first] == "Poprawiona"

    saved = await _post(client, edit, {"body": "Jeszcze raz"}, htmx=True)
    assert saved.status_code == 200
    assert "Jeszcze raz" in _text(saved.text, f"note-{first}")
    assert "edytowano" in _text(saved.text, f"note-{first}")
    assert f'id="{field}"' not in saved.text

    # The same text, padded, stores nothing, so no "edytowano".
    before = _updated_at(client, second)
    unchanged = await _post(
        client,
        f"/ui/companies/{company_id}/notes/{second}/edit",
        {"body": "  Druga \r\n"},
        htmx=True,
    )
    assert unchanged.status_code == 200
    assert "edytowano" not in _text(unchanged.text, f"note-{second}")
    assert _updated_at(client, second) == before
    assert _stored_notes(client, company_id)[second] == "Druga"


@pytest.mark.asyncio
async def test_delete_note_asks_inline_then_deletes(client):
    company_id = _company(client)
    note_id = _note(client, company_id, "Do usunięcia", "2026-10-28T13:05")
    delete = f"/ui/companies/{company_id}/notes/{note_id}/delete"
    question = f"note-{note_id}-delete-question"
    for headers in (_HTMX, {}):
        response = await client.get(delete, headers=headers)
        assert response.status_code == 200
        html = response.text
        assert _text(html, question) == "Usunąć tę notatkę?"
        assert _attrs(html, question)["tabindex"] == "-1"
        assert _focus(response) == question
        item = _between(html, f'<li id="note-{note_id}"', "</li>")
        assert f'id="{question}"' in item
        form = _between(item, f'action="{delete}"', "</form>")
        assert "Usuń" in form
        buttons = [attrs for tag, attrs in _tags(item) if tag == "button"]
        assert len(buttons) == 1
        assert "autofocus" not in buttons[0]
    assert _stored_notes(client, company_id) == {note_id: "Do usunięcia"}

    plain = await _post(client, delete)
    assert plain.status_code == 303
    assert plain.headers["location"] == (
        f"/ui/instruments/{company_id}?research=open#research"
    )
    assert _stored_notes(client, company_id) == {}

    other = _note(client, company_id, "Druga", "2026-10-28T14:05")
    fragment = await _post(
        client, f"/ui/companies/{company_id}/notes/{other}/delete", htmx=True
    )
    assert fragment.status_code == 200
    assert f'id="note-{other}"' not in fragment.text
    assert "Brak notatek." in _panel(fragment.text)
    assert _attrs(fragment.text, "research-toggle-button")["aria-label"] == (
        "Notatki i tezy"
    )
    assert _stored_notes(client, company_id) == {}


@pytest.mark.asyncio
async def test_note_focus_rules(client):
    """Keyboard focus never drops to the top of the page (Review Focus 3).

    The panel shows the three notes newest first: ``newest``,
    ``middle``, ``oldest``.
    """
    company_id = _company(client)
    oldest = _note(client, company_id, "Najstarsza", "2026-10-26T08:00")
    middle = _note(client, company_id, "Środkowa", "2026-10-27T08:00")
    newest = _note(client, company_id, "Najnowsza", "2026-10-28T08:00")
    base = f"/ui/companies/{company_id}"
    note = f"{base}/notes/{middle}"

    added_blank = await _post(client, f"{base}/notes", htmx=True)
    assert added_blank.status_code == 422
    assert _focus(added_blank) == "note-new-errors"

    opened = await client.get(f"{note}/edit", headers=_HTMX)
    assert _focus(opened) == f"note-{middle}-body"
    cancel = f"{base}/research?focus=note-{middle}"
    assert _link(opened.text, cancel)["hx-get"] == cancel

    invalid = await _post(client, f"{note}/edit", htmx=True)
    assert invalid.status_code == 422
    assert _focus(invalid) == f"note-{middle}-errors"
    assert _attrs(invalid.text, f"note-{middle}-errors")["tabindex"] == "-1"

    cancelled = await client.get(cancel, headers=_HTMX)
    assert _focus(cancelled) == f"note-{middle}"

    saved = await _post(client, f"{note}/edit", {"body": "Inna"}, htmx=True)
    assert saved.status_code == 200
    assert _focus(saved) == f"note-{middle}"

    asked = await client.get(f"{note}/delete", headers=_HTMX)
    assert _focus(asked) == f"note-{middle}-delete-question"
    assert _link(asked.text, cancel)["hx-get"] == cancel
    assert _focus(await client.get(cancel, headers=_HTMX)) == f"note-{middle}"

    # Delete: the next note, else the previous one, else the heading.
    deleted = await _post(client, f"{note}/delete", htmx=True)
    assert _focus(deleted) == f"note-{oldest}"
    deleted = await _post(client, f"{base}/notes/{oldest}/delete", htmx=True)
    assert _focus(deleted) == f"note-{newest}"
    deleted = await _post(client, f"{base}/notes/{newest}/delete", htmx=True)
    assert _focus(deleted) == "research-title"
    assert _stored_notes(client, company_id) == {}

    added = await _post(client, f"{base}/notes", {"body": "Nowa"}, htmx=True)
    assert added.status_code == 200
    assert _focus(added) == "note-new-body"


@pytest.mark.asyncio
async def test_note_actions_fall_back_and_are_named(client):
    """Every panel action works without HTMX and names its note.

    A failed HTMX request is repeated without HTMX (``ui.js``), so a
    form posts to its own ``action`` and a link opens its own ``href``.
    """
    company_id = _company(client)
    note_id = _note(client, company_id, "Notatka", "2026-10-28T13:05")
    base = f"/ui/companies/{company_id}"
    note = f"{base}/notes/{note_id}"
    states = (
        await client.get(f"/ui/instruments/{company_id}?research=open"),
        await client.get(f"{base}/research", headers=_HTMX),
        await client.get(f"{note}/edit", headers=_HTMX),
        await client.get(f"{note}/delete", headers=_HTMX),
    )
    actions, links = set(), set()
    for response in states:
        for tag, attrs in _panel_actions(response.text):
            assert "data-plain-fallback" in attrs, attrs
            assert attrs["hx-target"] == "#research"
            assert attrs["hx-swap"] == "outerHTML"
            if tag == "form":
                assert attrs["method"] == "post"
                assert attrs["hx-post"] == attrs["action"]
                actions.add(attrs["action"])
            else:
                assert attrs["hx-get"] == _without_fragment(attrs["href"])
                links.add(attrs["href"])
    assert actions == {f"{base}/notes", f"{note}/edit", f"{note}/delete"}
    # "+ Nowa teza" is in every open panel.
    assert links == {
        f"{base}/theses/new",
        f"{note}/edit",
        f"{note}/delete",
        f"{base}/research?focus=note-{note_id}",
    }

    html = states[0].text
    edit = _link(html, f"{note}/edit")
    assert edit["aria-label"] == "Edytuj notatkę z 28.10.2026, 14:05"
    assert _between(html, f'href="{note}/edit"', "</a>").endswith(">Edytuj")
    remove = _link(html, f"{note}/delete")
    assert remove["aria-label"] == "Usuń notatkę z 28.10.2026, 14:05"
    assert _between(html, f'href="{note}/delete"', "</a>").endswith(">Usuń")

    client.cookies.set("ui_lang", "en")
    english = (await client.get(f"{base}/research", headers=_HTMX)).text
    assert _link(english, f"{note}/edit")["aria-label"] == (
        "Edit the note from Oct 28, 2026, 14:05"
    )
    assert _link(english, f"{note}/delete")["aria-label"] == (
        "Delete the note from Oct 28, 2026, 14:05"
    )


@pytest.mark.asyncio
async def test_saving_a_deleted_note_is_the_research_404(client):
    """A stale tab gets the research 404 (Review Focus 5)."""
    company_id = _company(client)
    note_id = _note(client, company_id, "Notatka", "2026-10-28T13:05")
    session = _session(client)
    try:
        assert NoteRepository(session).delete(company_id, note_id) is True
    finally:
        session.close()
    path = f"/ui/companies/{company_id}/notes/{note_id}/edit"
    for htmx in (False, True):
        response = await _post(client, path, {"body": "Zmiana"}, htmx=htmx)
        assert response.status_code == 404
        assert "text/html" in response.headers["content-type"]
        html = response.text
        assert "<html" in html
        assert "Nie znaleziono notatki ani tezy" in html
        back = f"/ui/instruments/{company_id}?research=open#research"
        hrefs = [attrs.get("href") for tag, attrs in _tags(html) if tag == "a"]
        assert back in hrefs
        assert _between(html, f'href="{back}"', "</a>").endswith(
            ">Wróć do notatek i tez"
        )
        _assert_ui_headers(response)
    assert _stored_notes(client, company_id) == {}


@pytest.mark.asyncio
async def test_note_deleted_during_the_request_is_the_research_404(
    client, monkeypatch
):
    """Another tab can delete the note after the route looked it up.

    The repository then finds no row to change: ``update`` returns
    None and ``delete`` returns False.
    """
    company_id = _company(client)
    note_id = _note(client, company_id, "Notatka", "2026-10-28T13:05")
    monkeypatch.setattr(NoteRepository, "update", lambda *args: None)
    monkeypatch.setattr(NoteRepository, "delete", lambda *args: False)
    note = f"/ui/companies/{company_id}/notes/{note_id}"
    for path in (f"{note}/edit", f"{note}/delete"):
        response = await _post(client, path, {"body": "Zmiana"}, htmx=True)
        assert response.status_code == 404, path
        assert "Nie znaleziono notatki ani tezy" in response.text


async def _request(client, method, path, *, htmx):
    if method == "GET":
        return await client.get(path, headers=_HTMX if htmx else {})
    return await _post(client, path, {"body": "Zmiana"}, htmx=htmx)


@pytest.mark.asyncio
async def test_note_404s(client, monkeypatch):
    company_id = _company(client)
    other_company = _company(client, name="Other Co", ticker="OTHER")
    foreign = _note(client, other_company, "Cudza notatka", "2026-10-28T13:05")
    base = f"/ui/companies/{company_id}/notes"
    routes = (
        ("GET", "edit"),
        ("POST", "edit"),
        ("GET", "delete"),
        ("POST", "delete"),
    )
    # Another company's note, and ids that are no note: the research 404.
    for raw_id in (str(foreign), "abc", "01", "9" * 20):
        for method, action in routes:
            for htmx in (False, True):
                path = f"{base}/{raw_id}/{action}"
                response = await _request(client, method, path, htmx=htmx)
                assert response.status_code == 404, (method, path)
                assert "text/html" in response.headers["content-type"]
                assert "Nie znaleziono notatki ani tezy" in response.text
                _assert_ui_headers(response)
    assert _stored_notes(client, other_company) == {foreign: "Cudza notatka"}

    # An unknown company is the instrument 404, checked first.
    for raw_company in ("999999", "abc"):
        unknown = f"/ui/companies/{raw_company}/notes"
        paths = [("POST", unknown)] + [
            (method, f"{unknown}/{foreign}/{action}")
            for method, action in routes
        ]
        for method, path in paths:
            for htmx in (False, True):
                response = await _request(client, method, path, htmx=htmx)
                assert response.status_code == 404, (method, path)
                assert "text/html" in response.headers["content-type"]
                assert "Nie znaleziono instrumentu" in response.text

    # The company was deleted between the check and the insert.
    def gone(self, company, note):
        raise CompanyNotFoundError(company)

    monkeypatch.setattr(NoteRepository, "create", gone)
    response = await _post(client, base, {"body": "Nowa"}, htmx=True)
    assert response.status_code == 404
    assert "Nie znaleziono instrumentu" in response.text


@pytest.mark.asyncio
async def test_cross_origin_note_post_is_403(client):
    company_id = _company(client)
    note_id = _note(client, company_id, "Notatka", "2026-10-28T13:05")
    base = f"/ui/companies/{company_id}/notes"
    for path in (base, f"{base}/{note_id}/edit", f"{base}/{note_id}/delete"):
        for htmx in (False, True):
            response = await _post(
                client,
                path,
                {"body": "Obca"},
                origin="http://evil.example",
                htmx=htmx,
            )
            assert response.status_code == 403, path
    assert _stored_notes(client, company_id) == {note_id: "Notatka"}


@pytest.mark.asyncio
async def test_storage_failure_keeps_the_text(client, monkeypatch):
    """A write that fails to commit is a 500 with the typed text kept."""
    company_id = _company(client)
    note_id = _note(client, company_id, "Stara treść", "2026-10-28T13:05")

    monkeypatch.setattr(NoteRepository, "create", _fail_storage)
    path = f"/ui/companies/{company_id}/notes"
    plain = await _post(client, path, {"body": "Nowa treść"})
    assert plain.status_code == 500
    html = plain.text
    assert "<html" in html
    assert _text(html, "note-new-errors").strip() == _NOT_STORED
    assert _text(html, "note-new-body") == "Nowa treść"
    assert "aria-invalid" not in _attrs(html, "note-new-body")
    # Its own failed save shows the field as the server rendered it.
    assert "hx-preserve" not in _attrs(html, "note-new-field")
    assert _attrs(html, "note-new-errors")["tabindex"] == "-1"
    assert _focus(plain) == "note-new-errors"
    _assert_ui_headers(plain)
    fragment = await _post(client, path, {"body": "Nowa treść"}, htmx=True)
    assert fragment.status_code == 500
    assert "<html" not in fragment.text
    assert _text(fragment.text, "note-new-body") == "Nowa treść"
    assert _focus(fragment) == "note-new-errors"

    monkeypatch.setattr(NoteRepository, "update", _fail_storage)
    path = f"/ui/companies/{company_id}/notes/{note_id}/edit"
    errors = f"note-{note_id}-errors"
    for htmx in (False, True):
        response = await _post(client, path, {"body": "Zmieniona"}, htmx=htmx)
        assert response.status_code == 500
        assert _NOT_STORED in _text(response.text, errors)
        assert _text(response.text, f"note-{note_id}-body") == "Zmieniona"
        assert _focus(response) == errors
    assert _stored_notes(client, company_id) == {note_id: "Stara treść"}


@pytest.mark.asyncio
async def test_failed_delete_keeps_the_question(client, monkeypatch):
    """Ruling P3: the question stays open, with the error focused."""
    company_id = _company(client)
    note_id = _note(client, company_id, "Notatka", "2026-10-28T13:05")
    monkeypatch.setattr(NoteRepository, "delete", _fail_storage)
    delete = f"/ui/companies/{company_id}/notes/{note_id}/delete"
    for htmx in (False, True):
        response = await _post(client, delete, htmx=htmx)
        assert response.status_code == 500
        html = response.text
        item = _between(html, f'<li id="note-{note_id}"', "</li>")
        assert "Usunąć tę notatkę?" in item
        assert _NOT_STORED in _text(html, f"note-{note_id}-errors")
        assert _focus(response) == f"note-{note_id}-errors"
    assert _stored_notes(client, company_id) == {note_id: "Notatka"}


@pytest.mark.asyncio
async def test_language_path_follows_the_panel_state(client):
    """PL/EN reopens what the panel shows.

    An inline form or question has a GET of its own. Every other
    answer returns to the company page with the panel open.
    """
    company_id = _company(client)
    note_id = _note(client, company_id, "Notatka", "2026-10-28T13:05")
    base = f"/ui/companies/{company_id}"
    note = f"{base}/notes/{note_id}"
    opened = f"/ui/instruments/{company_id}?research=open"
    answers = (
        (await client.get(f"{note}/edit", headers=_HTMX), f"{note}/edit"),
        (await _post(client, f"{note}/edit", htmx=True), f"{note}/edit"),
        (await client.get(f"{note}/delete", headers=_HTMX), f"{note}/delete"),
        (
            await client.get(
                f"{base}/research",
                params={"focus": f"note-{note_id}"},
                headers=_HTMX,
            ),
            opened,
        ),
        (await _post(client, f"{base}/notes", htmx=True), opened),
        (
            await _post(client, f"{note}/edit", {"body": "Inna"}, htmx=True),
            opened,
        ),
        (
            await _post(client, f"{base}/notes", {"body": "Nowa"}, htmx=True),
            opened,
        ),
        (await _post(client, f"{note}/delete", htmx=True), opened),
    )
    for response, expected in answers:
        for code in ("pl", "en"):
            language_next = _attrs(response.text, f"language-next-{code}")
            assert language_next["value"] == expected
            assert language_next["hx-swap-oob"] == "outerHTML"
    # A plain 422 is a full page built at the POST path. The switch
    # opens the panel's GET instead.
    page = await _post(client, f"{base}/notes")
    assert page.status_code == 422
    assert _attrs(page.text, "language-next-pl")["value"] == (
        f"{base}/research"
    )


def test_research_error_key_names_the_limit():
    from app.ui.research_forms import research_error_key
    from app.validation.text import TextValidationError

    def too_long(limit):
        return {"type": "string_too_long", "ctx": {"max_length": limit}}

    def value_error(error):
        return {"type": "value_error", "ctx": {"error": error}}

    assert research_error_key({"type": "missing"}) == "error.required"
    assert research_error_key(too_long(200)) == "error.max_200"
    assert research_error_key(too_long(5000)) == "error.max_5000"
    assert research_error_key(too_long(10000)) == "error.max_10000"
    assert research_error_key(too_long(20)) == "error.too_long"
    blank = TextValidationError("blank", "body")
    assert research_error_key(value_error(blank)) == "error.required"
    control = TextValidationError("control_char", "body")
    assert research_error_key(value_error(control)) == "error.invalid"
    plain = ValueError("body cannot be null")
    assert research_error_key(value_error(plain)) == "error.invalid"
    assert research_error_key({"type": "string_type"}) == "error.invalid"
    for key in ("error.max_200", "error.max_5000", "error.max_10000"):
        assert CATALOGS["pl"][key].startswith("Najwyżej ")
        assert CATALOGS["en"][key].startswith("At most ")


@pytest.mark.asyncio
async def test_add_thesis_plain_and_htmx(client):
    company_id = _company(client)
    _note(client, company_id, "Notatka", "2026-10-28T13:05")
    base = f"/ui/companies/{company_id}"

    opened = await client.get(f"{base}/theses/new", headers=_HTMX)
    assert opened.status_code == 200
    html = opened.text
    assert "<html" not in html
    assert _focus(opened) == "thesis-new-title"
    assert_labeled(html)
    form = _between(html, f'action="{base}/theses"', "</form>")
    for field, label in (
        ("title", "Tytuł"),
        ("body", "Dlaczego kupiłem"),
        ("thesis_breakers", "Kiedy sprzedam / co złamie tezę"),
    ):
        assert f'<label for="thesis-new-{field}">{label}</label>' in form
        assert _attrs(html, f"thesis-new-{field}")["name"] == field
    title = _attrs(html, "thesis-new-title")
    assert (title["type"], title["value"]) == ("text", "")
    assert _text(html, "thesis-new-body") == ""
    assert _text(html, "thesis-new-thesis_breakers") == ""
    # There is no status field: a new thesis always starts active.
    assert 'name="status"' not in html
    # The form takes the place of the "+ Nowa teza" link.
    assert f'href="{base}/theses/new"' not in html

    page = await client.get(f"{base}/theses/new")
    assert page.status_code == 200
    assert "<html" in page.text
    assert _attrs(page.text, "research-toggle-button")["aria-expanded"] == (
        "true"
    )
    assert _focus(page) == "thesis-new-title"

    added = await _post(
        client,
        f"{base}/theses",
        {
            "title": " Teza AI ",
            "body": "Powód zakupu.",
            "thesis_breakers": "Spadek o 20%",
        },
        htmx=True,
    )
    assert added.status_code == 200
    [thesis] = _stored_theses(client, company_id).values()
    assert (thesis.title, thesis.body, thesis.thesis_breakers) == (
        "Teza AI",
        "Powód zakupu.",
        "Spadek o 20%",
    )
    assert thesis.status == ThesisStatus.ACTIVE
    assert thesis.closed_at is None
    html = added.text
    assert "<html" not in html
    assert _focus(added) == f"thesis-{thesis.id}"
    card = _between(html, f'<li id="thesis-{thesis.id}"', "</li>")
    assert '<h4 class="thesis-title">Teza AI</h4>' in card
    assert '<span class="badge badge-active">aktywna</span>' in card
    # The form is closed, and the link is back with its id.
    assert 'id="thesis-new-title"' not in html
    assert _link(html, f"{base}/theses/new")["id"] == "thesis-new-link"
    assert _between(html, f'href="{base}/theses/new"', "</a>").endswith(
        ">+ Nowa teza"
    )
    _assert_toggle(
        html,
        company_id,
        expanded="true",
        next_state="closed",
        label="Notatki i tezy (2)",
    )
    _assert_ui_headers(added)

    plain = await _post(
        client, f"{base}/theses", {"title": "Druga teza", "body": "Powód."}
    )
    assert plain.status_code == 303
    assert plain.headers["location"] == (
        f"/ui/instruments/{company_id}?research=open#research"
    )
    _assert_ui_headers(plain)
    stored = {
        item.title: item
        for item in _stored_theses(client, company_id).values()
    }
    assert sorted(stored) == ["Druga teza", "Teza AI"]
    # The breakers may stay empty.
    assert stored["Druga teza"].thesis_breakers == ""
    assert stored["Druga teza"].status == ThesisStatus.ACTIVE


@pytest.mark.asyncio
@pytest.mark.parametrize("htmx", [False, True])
async def test_invalid_thesis_is_422(client, htmx):
    company_id = _company(client)
    path = f"/ui/companies/{company_id}/theses"
    valid = {"title": "Teza", "body": "Powód zakupu.", "thesis_breakers": ""}
    for field, value, message in (
        ("title", "   ", "To pole jest wymagane."),
        ("title", "a\nb", "Ta wartość jest nieprawidłowa."),
        ("title", "a" * 201, "Najwyżej 200 znaków."),
        ("body", "a" * 10001, "Najwyżej 10\u00a0000 znaków."),
        ("thesis_breakers", "a" * 5001, "Najwyżej 5000 znaków."),
    ):
        typed = {**valid, field: value}
        response = await _post(client, path, typed, htmx=htmx)
        assert response.status_code == 422, (field, value[:3])
        html = response.text
        control = f"thesis-new-{field}"
        assert _text(html, f"{control}-error") == message
        assert _attrs(html, control)["aria-invalid"] == "true"
        assert _attrs(html, control)["aria-describedby"] == f"{control}-error"
        summary = _between(html, 'id="thesis-new-errors"', "</div>")
        assert f'href="#{control}"' in summary
        assert message in summary
        assert _attrs(html, "thesis-new-errors")["tabindex"] == "-1"
        assert "role" not in _attrs(html, "thesis-new-errors")
        assert _focus(response) == "thesis-new-errors"
        assert_labeled(html)
        # Every typed value is kept, the valid ones too.
        assert _attrs(html, "thesis-new-title")["value"] == typed["title"]
        assert _text(html, "thesis-new-body") == typed["body"]
        assert _text(html, "thesis-new-thesis_breakers") == (
            typed["thesis_breakers"]
        )
        assert ("<html" in html) is not htmx
        assert html.count('<section id="research"') == 1

    # The summary lists the fields in the form's order, by their labels.
    response = await _post(
        client,
        path,
        {"title": "", "body": "", "thesis_breakers": "a" * 5001},
        htmx=htmx,
    )
    summary = _between(response.text, 'id="thesis-new-errors"', "</div>")
    assert re.findall(r'<a href="#([^"]+)">([^<]+)</a>', summary) == [
        ("thesis-new-title", "Tytuł"),
        ("thesis-new-body", "Dlaczego kupiłem"),
        ("thesis-new-thesis_breakers", "Kiedy sprzedam / co złamie tezę"),
    ]

    payload = {
        "title": '"' + _SCRIPT,
        "body": "</textarea>" + _SCRIPT,
        "thesis_breakers": "</textarea>" + _SCRIPT + "a" * 5000,
    }
    response = await _post(client, path, payload, htmx=htmx)
    assert response.status_code == 422
    html = response.text
    assert _SCRIPT not in html
    assert "</textarea><script>" not in html
    # The quote cannot end the attribute: it is escaped too.
    assert f'value="&#34;{_ESCAPED}"' in html
    assert html.count(f"&lt;/textarea&gt;{_ESCAPED}") == 2
    assert _attrs(html, "thesis-new-title")["value"] == payload["title"]
    assert _text(html, "thesis-new-body") == payload["body"]
    assert _stored_theses(client, company_id) == {}

    at_limit = {
        "title": "a" * 200,
        "body": "b" * 10000,
        "thesis_breakers": "c" * 5000,
    }
    saved = await _post(client, path, at_limit, htmx=htmx)
    assert saved.status_code == (200 if htmx else 303)
    [thesis] = _stored_theses(client, company_id).values()
    assert (thesis.title, thesis.body, thesis.thesis_breakers) == (
        at_limit["title"],
        at_limit["body"],
        at_limit["thesis_breakers"],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("htmx", [False, True])
async def test_invalid_thesis_edit_keeps_the_values(client, htmx):
    company_id = _company(client)
    thesis_id = _thesis(
        client, company_id, "Stara teza", "2026-10-28T13:05", body="Stary."
    )
    path = f"/ui/companies/{company_id}/theses/{thesis_id}/edit"
    prefix = f"thesis-{thesis_id}"
    typed = {"title": "Nowa teza", "body": " ", "thesis_breakers": "Próg."}
    response = await _post(client, path, typed, htmx=htmx)
    assert response.status_code == 422
    html = response.text
    assert _text(html, f"{prefix}-body-error") == "To pole jest wymagane."
    assert _attrs(html, f"{prefix}-body")["aria-invalid"] == "true"
    summary = _between(html, f'id="{prefix}-errors"', "</div>")
    assert f'<a href="#{prefix}-body">Dlaczego kupiłem</a>' in summary
    assert _focus(response) == f"{prefix}-errors"
    assert _attrs(html, f"{prefix}-title")["value"] == "Nowa teza"
    assert _text(html, f"{prefix}-body") == " "
    assert _text(html, f"{prefix}-thesis_breakers") == "Próg."
    assert_labeled(html)
    # The form sits in the thesis's own card.
    card = _between(html, f'<li id="{prefix}"', "</li>")
    assert f'action="{path}"' in card
    assert _stored_theses(client, company_id)[thesis_id].title == "Stara teza"


@pytest.mark.asyncio
async def test_close_and_reopen(client):
    company_id = _company(client)
    thesis_id = _thesis(client, company_id, "Teza AI", "2026-10-28T13:05")
    # Another closed thesis keeps the closed list after the reopen.
    _thesis(
        client,
        company_id,
        "Inna",
        "2026-09-01T08:00",
        closed="2026-09-02T08:00",
    )
    base = f"/ui/companies/{company_id}/theses/{thesis_id}"
    status = f"thesis-{thesis_id}-status"

    page = await client.get(
        f"/ui/companies/{company_id}/research", headers=_HTMX
    )
    assert _text(page.text, status) == "Zamknij tezę"
    assert _attrs(page.text, status)["type"] == "submit"
    assert _attrs(page.text, status)["aria-label"] == "Zamknij tezę „Teza AI”"
    assert f'id="{status}"' in _between(
        page.text, f'action="{base}/close"', "</form>"
    )

    closed = await _post(client, f"{base}/close", htmx=True)
    assert closed.status_code == 200
    stored = _stored_theses(client, company_id)[thesis_id]
    assert stored.status == ThesisStatus.CLOSED
    assert stored.closed_at is not None
    html = closed.text
    assert '<details class="research-closed" open>' in html
    listed = _closed_list(html)
    assert f'id="thesis-{thesis_id}"' in listed
    # The same id, now with the other word: HTMX keeps the focus on it.
    assert _text(html, status) == "Otwórz ponownie"
    assert _attrs(html, status)["aria-label"] == (
        "Otwórz ponownie tezę „Teza AI”"
    )
    assert f'id="{status}"' in _between(
        listed, f'action="{base}/reopen"', "</form>"
    )
    assert "autofocus" not in html
    assert "Brak aktywnych tez." in _panel(html)
    # The closing date takes the place of the "aktywna" badge.
    card = _between(listed, f'<li id="thesis-{thesis_id}"', "</li>")
    closed_on = format_local_date(stored.closed_at, "pl")
    badge = f'<span class="badge badge-closed">zamknięta {closed_on}</span>'
    assert badge in card
    assert "aktywna" not in listed

    # A second click changes nothing.
    for htmx in (True, False):
        again = await _post(client, f"{base}/close", htmx=htmx)
        assert again.status_code == (200 if htmx else 303)
        assert _stored_theses(client, company_id)[thesis_id] == stored

    reopened = await _post(client, f"{base}/reopen", htmx=True)
    assert reopened.status_code == 200
    stored = _stored_theses(client, company_id)[thesis_id]
    assert stored.status == ThesisStatus.ACTIVE
    assert stored.closed_at is None
    html = reopened.text
    # The action concerned a closed thesis, so the list stays unfolded.
    assert '<details class="research-closed" open>' in html
    assert f'id="thesis-{thesis_id}"' not in _closed_list(html)
    assert _text(html, status) == "Zamknij tezę"
    assert "autofocus" not in html
    card = _between(html, f'<li id="thesis-{thesis_id}"', "</li>")
    assert '<span class="badge badge-active">aktywna</span>' in card

    for action, expected in (
        ("close", ThesisStatus.CLOSED),
        ("reopen", ThesisStatus.ACTIVE),
    ):
        plain = await _post(client, f"{base}/{action}")
        assert plain.status_code == 303
        assert plain.headers["location"] == (
            f"/ui/instruments/{company_id}?research=open#research"
        )
        assert _stored_theses(client, company_id)[thesis_id].status == (
            expected
        )


@pytest.mark.asyncio
async def test_edit_thesis_keeps_status(client):
    company_id = _company(client)
    thesis_id = _thesis(
        client,
        company_id,
        "Stara teza",
        "2026-10-01T08:00",
        body="Stary powód.",
        breakers="Stary próg.",
        closed="2026-10-20T08:00",
    )
    edit = f"/ui/companies/{company_id}/theses/{thesis_id}/edit"
    before = _stored_theses(client, company_id)[thesis_id]

    for headers in (_HTMX, {}):
        opened = await client.get(edit, headers=headers)
        assert opened.status_code == 200
        html = opened.text
        assert _focus(opened) == f"thesis-{thesis_id}-title"
        # The card is in the closed list, unfolded so the form shows.
        assert '<details class="research-closed" open>' in html
        assert f'action="{edit}"' in _closed_list(html)
        assert _attrs(html, f"thesis-{thesis_id}-title")["value"] == (
            "Stara teza"
        )
        assert _text(html, f"thesis-{thesis_id}-body") == "Stary powód."
        assert _text(html, f"thesis-{thesis_id}-thesis_breakers") == (
            "Stary próg."
        )
        assert 'name="status"' not in html
        assert_labeled(html)
        # The title field takes the place of the heading.
        card = _between(html, f'<li id="thesis-{thesis_id}"', "</li>")
        assert 'class="thesis-title"' not in card
    assert "<html" in opened.text

    # A 422 keeps the closed list unfolded too, so its summary shows.
    invalid = await _post(client, edit, {"title": " "}, htmx=True)
    assert invalid.status_code == 422
    assert '<details class="research-closed" open>' in invalid.text
    assert _focus(invalid) == f"thesis-{thesis_id}-errors"
    assert _stored_theses(client, company_id)[thesis_id] == before

    saved = await _post(
        client,
        edit,
        {"title": "Nowa teza", "body": "Nowy powód.", "thesis_breakers": ""},
        htmx=True,
    )
    assert saved.status_code == 200
    after = _stored_theses(client, company_id)[thesis_id]
    assert (after.title, after.body, after.thesis_breakers) == (
        "Nowa teza",
        "Nowy powód.",
        "",
    )
    assert after.status == ThesisStatus.CLOSED
    assert after.closed_at == before.closed_at
    html = saved.text
    assert _focus(saved) == f"thesis-{thesis_id}"
    assert '<details class="research-closed" open>' in html
    assert f'id="thesis-{thesis_id}-title"' not in html
    assert '<h4 class="thesis-title">Nowa teza</h4>' in _closed_list(html)

    # The same values, padded, store nothing: updated_at stays.
    unchanged = await _post(
        client,
        edit,
        {
            "title": " Nowa teza ",
            "body": "Nowy powód.\r\n",
            "thesis_breakers": " ",
        },
        htmx=True,
    )
    assert unchanged.status_code == 200
    assert _stored_theses(client, company_id)[thesis_id] == after

    plain = await _post(client, edit, _NEW_THESIS)
    assert plain.status_code == 303
    assert plain.headers["location"] == (
        f"/ui/instruments/{company_id}?research=open#research"
    )
    final = _stored_theses(client, company_id)[thesis_id]
    assert final.title == "Nowa teza"
    assert final.thesis_breakers == "Nowy próg."
    assert (final.status, final.closed_at) == (after.status, after.closed_at)


@pytest.mark.asyncio
async def test_focus_on_a_closed_thesis_unfolds_the_list(client):
    """ "Anuluj" on a closed thesis must find its card visible.

    It returns with ``focus=thesis-{id}``. When that names a closed
    thesis of this company, the closed list is unfolded. Any other
    focus leaves it folded.
    """
    company_id = _company(client)
    active = _thesis(client, company_id, "Aktywna", "2026-10-28T13:05")
    closed = _thesis(
        client,
        company_id,
        "Zamknięta",
        "2026-10-01T08:00",
        closed="2026-10-02T08:00",
    )
    note_id = _note(client, company_id, "Notatka", "2026-10-28T13:05")
    other_company = _company(client, name="Other Co", ticker="OTHER")
    foreign = _thesis(
        client,
        other_company,
        "Cudza",
        "2026-10-01T08:00",
        closed="2026-10-02T08:00",
    )
    research = f"/ui/companies/{company_id}/research"
    edit = await client.get(
        f"/ui/companies/{company_id}/theses/{closed}/edit", headers=_HTMX
    )
    cancel = f"{research}?focus=thesis-{closed}"
    assert _link(edit.text, cancel)["hx-get"] == cancel
    for headers in (_HTMX, {}):
        response = await client.get(cancel, headers=headers)
        assert response.status_code == 200
        assert '<details class="research-closed" open>' in response.text
        assert f'id="thesis-{closed}"' in _closed_list(response.text)
        assert _focus(response) == f"thesis-{closed}"
    for focus in (
        f"thesis-{active}",
        f"thesis-{foreign}",
        f"note-{note_id}",
        "thesis-0",
        "thesis-" + "9" * 20,
    ):
        response = await client.get(
            research, params={"focus": focus}, headers=_HTMX
        )
        assert response.status_code == 200, focus
        assert '<details class="research-closed">' in response.text, focus


@pytest.mark.asyncio
async def test_delete_thesis_asks_inline(client):
    company_id = _company(client)
    thesis_id = _thesis(client, company_id, "Teza AI", "2026-10-28T13:05")
    delete = f"/ui/companies/{company_id}/theses/{thesis_id}/delete"
    question = f"thesis-{thesis_id}-delete-question"
    for headers in (_HTMX, {}):
        response = await client.get(delete, headers=headers)
        assert response.status_code == 200
        html = response.text
        assert _text(html, question) == "Usunąć tę tezę?"
        assert _attrs(html, question)["tabindex"] == "-1"
        assert _focus(response) == question
        card = _between(html, f'<li id="thesis-{thesis_id}"', "</li>")
        assert f'id="{question}"' in _between(
            card, f'action="{delete}"', "</form>"
        )
        buttons = [attrs for tag, attrs in _tags(card) if tag == "button"]
        assert len(buttons) == 1
        assert "autofocus" not in buttons[0]
        assert buttons[0]["aria-label"] == "Usuń tezę „Teza AI”"
        assert _between(card, "<button", "</button>").endswith(">Usuń")
        # The question takes the place of the card's actions.
        assert f'id="thesis-{thesis_id}-status"' not in card
        assert "Powód zakupu." in card
    assert set(_stored_theses(client, company_id)) == {thesis_id}

    plain = await _post(client, delete)
    assert plain.status_code == 303
    assert plain.headers["location"] == (
        f"/ui/instruments/{company_id}?research=open#research"
    )
    assert _stored_theses(client, company_id) == {}

    other = _thesis(client, company_id, "Druga", "2026-10-28T14:05")
    fragment = await _post(
        client,
        f"/ui/companies/{company_id}/theses/{other}/delete",
        htmx=True,
    )
    assert fragment.status_code == 200
    assert f'id="thesis-{other}"' not in fragment.text
    assert "Brak tez." in _panel(fragment.text)
    assert _focus(fragment) == "research-title"
    assert _attrs(fragment.text, "research-toggle-button")["aria-label"] == (
        "Notatki i tezy"
    )
    assert _stored_theses(client, company_id) == {}


@pytest.mark.asyncio
async def test_thesis_focus_rules(client):
    """Keyboard focus never drops to the top of the page (Review Focus 3).

    The panel shows the three active theses newest first: ``newest``,
    ``middle``, ``oldest``.
    """
    company_id = _company(client)
    oldest = _thesis(client, company_id, "Najstarsza", "2026-10-26T08:00")
    middle = _thesis(client, company_id, "Środkowa", "2026-10-27T08:00")
    newest = _thesis(client, company_id, "Najnowsza", "2026-10-28T08:00")
    base = f"/ui/companies/{company_id}"
    thesis = f"{base}/theses/{middle}"

    opened = await client.get(f"{base}/theses/new", headers=_HTMX)
    assert _focus(opened) == "thesis-new-title"
    # "Anuluj" carries the id of the "+ Nowa teza" link whose place it
    # takes, so HTMX puts the focus back on that link (Ruling P2).
    # Without HTMX the link opens the page at the panel, not at the
    # top: the fragment never reaches the server. hx-get has no
    # fragment, because HTMX would scroll to it after the swap.
    cancel_new = _attrs(opened.text, "thesis-new-link")
    assert cancel_new["href"] == f"{base}/research#research"
    assert cancel_new["hx-get"] == f"{base}/research"
    assert _text(opened.text, "thesis-new-link") == "Anuluj"
    back = await client.get(cancel_new["href"], headers=_HTMX)
    assert "autofocus" not in back.text
    assert _attrs(back.text, "thesis-new-link")["href"] == (
        f"{base}/theses/new"
    )
    assert _text(back.text, "thesis-new-link") == "+ Nowa teza"

    added_blank = await _post(client, f"{base}/theses", htmx=True)
    assert added_blank.status_code == 422
    assert _focus(added_blank) == "thesis-new-errors"

    edit = await client.get(f"{thesis}/edit", headers=_HTMX)
    assert _focus(edit) == f"thesis-{middle}-title"
    cancel = f"{base}/research?focus=thesis-{middle}"
    assert _link(edit.text, cancel)["hx-get"] == cancel

    invalid = await _post(client, f"{thesis}/edit", htmx=True)
    assert invalid.status_code == 422
    assert _focus(invalid) == f"thesis-{middle}-errors"
    assert _attrs(invalid.text, f"thesis-{middle}-errors")["tabindex"] == "-1"

    cancelled = await client.get(cancel, headers=_HTMX)
    assert _focus(cancelled) == f"thesis-{middle}"

    saved = await _post(client, f"{thesis}/edit", _NEW_THESIS, htmx=True)
    assert saved.status_code == 200
    assert _focus(saved) == f"thesis-{middle}"

    asked = await client.get(f"{thesis}/delete", headers=_HTMX)
    assert _focus(asked) == f"thesis-{middle}-delete-question"
    assert _link(asked.text, cancel)["hx-get"] == cancel
    assert _focus(await client.get(cancel, headers=_HTMX)) == (
        f"thesis-{middle}"
    )

    # The two buttons share one id, so they need no autofocus.
    for action in ("close", "reopen"):
        answer = await _post(client, f"{thesis}/{action}", htmx=True)
        assert "autofocus" not in answer.text, action
        assert _attrs(answer.text, f"thesis-{middle}-status")["type"] == (
            "submit"
        )

    # Delete: the next thesis, else the previous one, else the heading.
    deleted = await _post(client, f"{thesis}/delete", htmx=True)
    assert _focus(deleted) == f"thesis-{oldest}"
    deleted = await _post(client, f"{base}/theses/{oldest}/delete", htmx=True)
    assert _focus(deleted) == f"thesis-{newest}"
    deleted = await _post(client, f"{base}/theses/{newest}/delete", htmx=True)
    assert _focus(deleted) == "research-title"
    assert _stored_theses(client, company_id) == {}

    added = await _post(client, f"{base}/theses", _NEW_THESIS, htmx=True)
    assert added.status_code == 200
    [new_id] = _stored_theses(client, company_id)
    assert _focus(added) == f"thesis-{new_id}"


@pytest.mark.asyncio
async def test_deleting_a_closed_thesis_stays_in_its_list(client):
    """The neighbour that takes the focus comes from the same list.

    The closed list shows the newest closing first: ``newer``, then
    ``older``. It stays unfolded, so that neighbour is visible.
    """
    company_id = _company(client)
    active = _thesis(client, company_id, "Aktywna", "2026-10-28T13:05")
    older = _thesis(
        client,
        company_id,
        "Starsza",
        "2026-10-01T08:00",
        closed="2026-10-02T08:00",
    )
    newer = _thesis(
        client,
        company_id,
        "Nowsza",
        "2026-10-03T08:00",
        closed="2026-10-04T08:00",
    )
    base = f"/ui/companies/{company_id}/theses"
    asked = await client.get(f"{base}/{newer}/delete", headers=_HTMX)
    assert '<details class="research-closed" open>' in asked.text
    assert _focus(asked) == f"thesis-{newer}-delete-question"

    deleted = await _post(client, f"{base}/{newer}/delete", htmx=True)
    assert _focus(deleted) == f"thesis-{older}"
    assert '<details class="research-closed" open>' in deleted.text
    deleted = await _post(client, f"{base}/{older}/delete", htmx=True)
    assert _focus(deleted) == "research-title"
    assert "<details" not in deleted.text
    assert set(_stored_theses(client, company_id)) == {active}


@pytest.mark.asyncio
async def test_thesis_draft_and_fallback(client):
    """Thesis actions keep the note draft, fall back, and name the thesis.

    The "Nowa notatka" wrapper keeps ``hx-preserve`` in every thesis
    answer. A failed HTMX request is repeated without HTMX
    (``ui.js``), so a form posts to its own ``action`` and a link
    opens its own ``href``.
    """
    company_id = _company(client)
    active = _thesis(client, company_id, "Teza AI", "2026-10-28T13:05")
    closed = _thesis(
        client,
        company_id,
        "Stara teza",
        "2026-10-01T08:00",
        closed="2026-10-02T08:00",
    )
    base = f"/ui/companies/{company_id}"
    first = f"{base}/theses/{active}"
    second = f"{base}/theses/{closed}"
    states = (
        await client.get(f"{base}/research", headers=_HTMX),
        await client.get(f"{base}/theses/new", headers=_HTMX),
        await _post(client, f"{base}/theses", htmx=True),
        await client.get(f"{first}/edit", headers=_HTMX),
        await _post(client, f"{first}/edit", htmx=True),
        await client.get(f"{first}/delete", headers=_HTMX),
        await _post(client, f"{first}/close", htmx=True),
        await _post(client, f"{first}/reopen", htmx=True),
        await client.get(f"{second}/edit", headers=_HTMX),
        # The stored values again: a save that changes nothing.
        await _post(
            client,
            f"{second}/edit",
            {"title": "Stara teza", "body": "Powód zakupu."},
            htmx=True,
        ),
    )
    actions, links = set(), set()
    for response in states:
        assert response.status_code in (200, 422)
        html = response.text
        assert '<div id="note-new-field" hx-preserve="true">' in html
        wrapper = _between(html, 'id="note-new-field"', "</div>")
        assert 'id="note-new-body"' in wrapper
        assert "autofocus" not in wrapper
        for tag, attrs in _panel_actions(html):
            assert "data-plain-fallback" in attrs, attrs
            assert attrs["hx-target"] == "#research"
            assert attrs["hx-swap"] == "outerHTML"
            if tag == "form":
                assert attrs["method"] == "post"
                assert attrs["hx-post"] == attrs["action"]
                actions.add(attrs["action"])
            else:
                assert attrs["hx-get"] == _without_fragment(attrs["href"])
                links.add(attrs["href"])
    assert actions == {
        f"{base}/notes",
        f"{base}/theses",
        f"{first}/edit",
        f"{first}/delete",
        f"{first}/close",
        f"{first}/reopen",
        f"{second}/edit",
        f"{second}/reopen",
    }
    assert links == {
        f"{base}/theses/new",
        f"{base}/research#research",
        f"{base}/research?focus=thesis-{active}",
        f"{base}/research?focus=thesis-{closed}",
        f"{first}/edit",
        f"{first}/delete",
        f"{second}/edit",
        f"{second}/delete",
    }

    html = states[0].text
    for href, label, text in (
        (f"{first}/edit", "Edytuj tezę „Teza AI”", "Edytuj"),
        (f"{first}/delete", "Usuń tezę „Teza AI”", "Usuń"),
        (f"{second}/edit", "Edytuj tezę „Stara teza”", "Edytuj"),
        (f"{second}/delete", "Usuń tezę „Stara teza”", "Usuń"),
    ):
        assert _link(html, href)["aria-label"] == label
        assert _between(html, f'href="{href}"', "</a>").endswith(f">{text}")
    for thesis_id, label, text in (
        (active, "Zamknij tezę „Teza AI”", "Zamknij tezę"),
        (closed, "Otwórz ponownie tezę „Stara teza”", "Otwórz ponownie"),
    ):
        assert _attrs(html, f"thesis-{thesis_id}-status")["aria-label"] == (
            label
        )
        assert _text(html, f"thesis-{thesis_id}-status") == text
    assert "aria-label" not in _attrs(html, "thesis-new-link")
    for card in (active, closed):
        fields = _text(html, f"thesis-{card}")
        assert "Dlaczego kupiłem" in fields
        assert "Kiedy sprzedam / co złamie tezę" in fields

    client.cookies.set("ui_lang", "en")
    english = (await client.get(f"{base}/research", headers=_HTMX)).text
    assert _link(english, f"{first}/edit")["aria-label"] == (
        'Edit the thesis "Teza AI"'
    )
    assert _link(english, f"{first}/delete")["aria-label"] == (
        'Delete the thesis "Teza AI"'
    )
    # The name starts with the visible "Close thesis" (WCAG 2.5.3), as
    # the Polish "Zamknij tezę „…”" does.
    assert _attrs(english, f"thesis-{active}-status")["aria-label"] == (
        'Close thesis "Teza AI"'
    )
    assert _text(english, f"thesis-{active}-status") == "Close thesis"
    assert _attrs(english, f"thesis-{closed}-status")["aria-label"] == (
        'Reopen the thesis "Stara teza"'
    )
    assert _text(english, f"thesis-{closed}-status") == "Reopen"
    assert _text(english, "thesis-new-link") == "+ New thesis"
    card = _text(english, f"thesis-{active}")
    assert "Why I bought" in card
    assert "When I sell / what breaks the thesis" in card
    assert '<span class="badge badge-active">active</span>' in english
    new_form = (await client.get(f"{base}/theses/new", headers=_HTMX)).text
    assert '<label for="thesis-new-title">Title</label>' in new_form


@pytest.mark.asyncio
async def test_thesis_storage_failure(client, monkeypatch):
    """A write that fails to commit is a 500 that keeps what was typed.

    Ruling P3: the form stays open, and its error summary takes the
    focus. A failed close or reopen shows its error in the card.
    """
    company_id = _company(client)
    thesis_id = _thesis(client, company_id, "Teza AI", "2026-10-28T13:05")
    closed_id = _thesis(
        client,
        company_id,
        "Stara teza",
        "2026-10-01T08:00",
        closed="2026-10-02T08:00",
    )
    base = f"/ui/companies/{company_id}"
    before = _stored_theses(client, company_id)

    monkeypatch.setattr(ThesisRepository, "create", _fail_storage)
    plain = await _post(client, f"{base}/theses", _NEW_THESIS)
    assert plain.status_code == 500
    html = plain.text
    assert "<html" in html
    assert _text(html, "thesis-new-errors").strip() == _NOT_STORED
    assert _attrs(html, "thesis-new-title")["value"] == "Nowa teza"
    assert _text(html, "thesis-new-body") == "Nowy powód."
    assert _text(html, "thesis-new-thesis_breakers") == "Nowy próg."
    assert "aria-invalid" not in html
    assert _attrs(html, "thesis-new-errors")["tabindex"] == "-1"
    assert _focus(plain) == "thesis-new-errors"
    _assert_ui_headers(plain)
    fragment = await _post(client, f"{base}/theses", _NEW_THESIS, htmx=True)
    assert fragment.status_code == 500
    assert "<html" not in fragment.text
    assert _attrs(fragment.text, "thesis-new-title")["value"] == "Nowa teza"
    assert _focus(fragment) == "thesis-new-errors"

    monkeypatch.setattr(ThesisRepository, "update", _fail_storage)
    errors = f"thesis-{thesis_id}-errors"
    for htmx in (False, True):
        response = await _post(
            client, f"{base}/theses/{thesis_id}/edit", _NEW_THESIS, htmx=htmx
        )
        assert response.status_code == 500
        html = response.text
        assert _text(html, errors).strip() == _NOT_STORED
        assert _attrs(html, f"thesis-{thesis_id}-title")["value"] == (
            "Nowa teza"
        )
        assert _text(html, f"thesis-{thesis_id}-body") == "Nowy powód."
        assert _focus(response) == errors

    monkeypatch.setattr(ThesisRepository, "set_status", _fail_storage)
    for failed, action in ((thesis_id, "close"), (closed_id, "reopen")):
        errors = f"thesis-{failed}-errors"
        for htmx in (False, True):
            response = await _post(
                client, f"{base}/theses/{failed}/{action}", htmx=htmx
            )
            assert response.status_code == 500, (action, htmx)
            html = response.text
            assert _text(html, errors).strip() == _NOT_STORED
            assert _attrs(html, errors)["tabindex"] == "-1"
            assert _focus(response) == errors
            # The error sits in the card, which keeps its button.
            card = _between(html, f'<li id="thesis-{failed}"', "</li>")
            assert f'id="{errors}"' in card
            assert f'id="thesis-{failed}-status"' in card
            assert ("<html" in html) is not htmx
    # The thesis that failed to reopen is still closed: its list is open.
    assert '<details class="research-closed" open>' in html

    monkeypatch.setattr(ThesisRepository, "delete", _fail_storage)
    question = f"thesis-{thesis_id}-delete-question"
    for htmx in (False, True):
        response = await _post(
            client, f"{base}/theses/{thesis_id}/delete", htmx=htmx
        )
        assert response.status_code == 500
        html = response.text
        assert _text(html, question) == "Usunąć tę tezę?"
        assert _NOT_STORED in _text(html, f"thesis-{thesis_id}-errors")
        assert _focus(response) == f"thesis-{thesis_id}-errors"
    assert _stored_theses(client, company_id) == before


@pytest.mark.asyncio
async def test_thesis_404s(client, monkeypatch):
    company_id = _company(client)
    other_company = _company(client, name="Other Co", ticker="OTHER")
    foreign = _thesis(client, other_company, "Cudza teza", "2026-10-28T13:05")
    deleted = _thesis(client, company_id, "Usunięta", "2026-10-28T13:05")
    session = _session(client)
    try:
        assert ThesisRepository(session).delete(company_id, deleted) is True
    finally:
        session.close()
    foreign_before = _stored_theses(client, other_company)
    base = f"/ui/companies/{company_id}/theses"
    routes = (
        ("GET", "edit"),
        ("POST", "edit"),
        ("POST", "close"),
        ("POST", "reopen"),
        ("GET", "delete"),
        ("POST", "delete"),
    )
    back = f"/ui/instruments/{company_id}?research=open#research"
    # Another company's thesis, a deleted one, and ids that are no
    # thesis: the research 404, in HTML.
    for raw_id in (str(foreign), str(deleted), "abc", "01", "9" * 20):
        for method, action in routes:
            for htmx in (False, True):
                path = f"{base}/{raw_id}/{action}"
                response = await _request(client, method, path, htmx=htmx)
                assert response.status_code == 404, (method, path)
                assert "text/html" in response.headers["content-type"]
                assert "Nie znaleziono notatki ani tezy" in response.text
                assert f'href="{back}"' in response.text
                _assert_ui_headers(response)
    assert _stored_theses(client, other_company) == foreign_before

    # An unknown company is the instrument 404, checked first.
    for raw_company in ("999999", "abc"):
        unknown = f"/ui/companies/{raw_company}/theses"
        paths = [("GET", f"{unknown}/new"), ("POST", unknown)] + [
            (method, f"{unknown}/{foreign}/{action}")
            for method, action in routes
        ]
        for method, path in paths:
            for htmx in (False, True):
                response = await _request(client, method, path, htmx=htmx)
                assert response.status_code == 404, (method, path)
                assert "text/html" in response.headers["content-type"]
                assert "Nie znaleziono instrumentu" in response.text

    # The company was deleted between the check and the insert.
    def gone(self, company, thesis):
        raise CompanyNotFoundError(company)

    monkeypatch.setattr(ThesisRepository, "create", gone)
    response = await _post(client, base, _NEW_THESIS, htmx=True)
    assert response.status_code == 404
    assert "Nie znaleziono instrumentu" in response.text


@pytest.mark.asyncio
async def test_thesis_deleted_during_the_request_is_the_research_404(
    client, monkeypatch
):
    """Another tab can delete the thesis after the route looked it up.

    The repository then finds no row: ``update`` and ``set_status``
    return None, and ``delete`` returns False.
    """
    company_id = _company(client)
    thesis_id = _thesis(client, company_id, "Teza", "2026-10-28T13:05")
    monkeypatch.setattr(ThesisRepository, "update", lambda *args: None)
    monkeypatch.setattr(ThesisRepository, "set_status", lambda *args: None)
    monkeypatch.setattr(ThesisRepository, "delete", lambda *args: False)
    thesis = f"/ui/companies/{company_id}/theses/{thesis_id}"
    for action in ("edit", "close", "reopen", "delete"):
        response = await _post(
            client, f"{thesis}/{action}", _NEW_THESIS, htmx=True
        )
        assert response.status_code == 404, action
        assert "Nie znaleziono notatki ani tezy" in response.text


@pytest.mark.asyncio
async def test_cross_origin_thesis_post_is_403(client):
    company_id = _company(client)
    thesis_id = _thesis(client, company_id, "Teza", "2026-10-28T13:05")
    before = _stored_theses(client, company_id)
    base = f"/ui/companies/{company_id}/theses"
    paths = [base] + [
        f"{base}/{thesis_id}/{action}"
        for action in ("edit", "close", "reopen", "delete")
    ]
    for path in paths:
        for htmx in (False, True):
            response = await _post(
                client,
                path,
                _NEW_THESIS,
                origin="http://evil.example",
                htmx=htmx,
            )
            assert response.status_code == 403, path
    assert _stored_theses(client, company_id) == before


@pytest.mark.asyncio
async def test_language_path_follows_the_thesis_state(client, monkeypatch):
    """PL/EN reopens what the panel shows, as for notes.

    The new-thesis form, an edit form, and a delete question have a
    GET of their own. Close and reopen have none, so they return to
    the company page with the panel open, as every other answer does.
    """
    company_id = _company(client)
    thesis_id = _thesis(client, company_id, "Teza", "2026-10-28T13:05")
    base = f"/ui/companies/{company_id}"
    thesis = f"{base}/theses/{thesis_id}"
    opened = f"/ui/instruments/{company_id}?research=open"
    answers = [
        (
            await client.get(f"{base}/theses/new", headers=_HTMX),
            f"{base}/theses/new",
        ),
        (
            await _post(client, f"{base}/theses", htmx=True),
            f"{base}/theses/new",
        ),
        (await client.get(f"{thesis}/edit", headers=_HTMX), f"{thesis}/edit"),
        (await _post(client, f"{thesis}/edit", htmx=True), f"{thesis}/edit"),
        (
            await client.get(f"{thesis}/delete", headers=_HTMX),
            f"{thesis}/delete",
        ),
        (await _post(client, f"{thesis}/close", htmx=True), opened),
        (await _post(client, f"{thesis}/reopen", htmx=True), opened),
        (
            await _post(client, f"{thesis}/edit", _NEW_THESIS, htmx=True),
            opened,
        ),
        (
            await _post(client, f"{base}/theses", _NEW_THESIS, htmx=True),
            opened,
        ),
    ]
    with monkeypatch.context() as patched:
        patched.setattr(ThesisRepository, "set_status", _fail_storage)
        answers.append(
            (await _post(client, f"{thesis}/close", htmx=True), opened)
        )
    answers.append(
        (await _post(client, f"{thesis}/delete", htmx=True), opened)
    )
    for response, expected in answers:
        for code in ("pl", "en"):
            language_next = _attrs(response.text, f"language-next-{code}")
            assert language_next["value"] == expected
            assert language_next["hx-swap-oob"] == "outerHTML"
    # A plain 422 is a full page built at the POST path. The switch
    # opens the new-thesis form's GET instead.
    page = await _post(client, f"{base}/theses")
    assert page.status_code == 422
    assert _attrs(page.text, "language-next-pl")["value"] == (
        f"{base}/theses/new"
    )


@pytest.mark.asyncio
async def test_company_delete_warns_about_notes_and_theses(client):
    """The company delete page names the notes and theses it removes.

    The warning is true: ``notes`` and ``theses`` reference
    ``companies.id`` with ON DELETE CASCADE, so the delete that
    follows leaves no row of either behind.
    """
    company_id = _company(client)
    _note(client, company_id, "Notatka", "2026-10-28T13:05")
    _thesis(client, company_id, "Teza", "2026-10-28T13:05")
    path = f"/ui/companies/{company_id}/delete"

    polish = await client.get(path)
    assert polish.status_code == 200
    assert (
        '<p class="warning">Usunięcie tej spółki usuwa także jej '
        "wskaźniki finansowe, notatki i tezy.</p>"
    ) in polish.text
    client.cookies.set("ui_lang", "en")
    english = await client.get(path)
    assert (
        '<p class="warning">Deleting this company also deletes its '
        "financial metrics, notes, and theses.</p>"
    ) in english.text

    deleted = await _post(client, path)
    assert deleted.status_code == 303
    assert _stored_notes(client, company_id) == {}
    assert _stored_theses(client, company_id) == {}
