"""The sticky note beside the heart, and the research panel it opens.

Notes and theses are stored through ``NoteRepository`` and
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
    NoteCreate,
    NoteUpdate,
    Thesis,
    ThesisCreate,
    ThesisStatus,
)
from app.repositories.note_repository import NoteRepository
from app.repositories.thesis_repository import ThesisRepository
from app.ui.formatting import format_local_date, format_local_datetime
from app.ui.research_view import NewNote, ResearchPanel
from app.ui.templating import MessageCatalog, templates
from tests.ui_html import FormInParagraph

UI_CSS = Path(__file__).resolve().parents[1] / "static" / "ui.css"
_SCRIPT = "<script>alert(1)</script>"
_ESCAPED = "&lt;script&gt;alert(1)&lt;/script&gt;"
_HTMX = {"hx-request": "true"}
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
    other value is ignored and never written into the page.
    """
    company_id = _company(client)
    note_id = _note(client, company_id, "Notatka", "2026-10-28T13:05")
    thesis_id = _thesis(client, company_id, "Teza", "2026-10-28T13:05")
    research = f"/ui/companies/{company_id}/research"
    for element_id in (f"note-{note_id}", f"thesis-{thesis_id}"):
        for headers in ({}, _HTMX):
            response = await client.get(
                research, params={"focus": element_id}, headers=headers
            )
            assert response.status_code == 200
            assert response.text.count("autofocus") == 1
            assert "autofocus" in _attrs(response.text, element_id)
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

    The ``focus`` parameter names only notes and theses, so no GET can
    focus the heading.
    """
    html = _render_panel(focus="research-title")
    assert html.count("autofocus") == 1
    assert "autofocus" in _attrs(html, "research-title")


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
