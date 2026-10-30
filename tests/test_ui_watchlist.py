"""The /ui watchlist page and the heart toggle on the detail page.

Rows, companies, and bars are written straight into the test SQLite
database. No market-data provider is called. ``utc_today`` is frozen
so the stale marker does not depend on the day the suite runs.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from html.parser import HTMLParser

import pytest
from sqlalchemy import event

from app.models.database_models import CompanyDB, PriceBarDB
from app.repositories.price_bar_repository import PriceBarRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.ui import watchlist_view

TODAY = date(2026, 10, 27)
RETRIEVED = datetime(2026, 10, 27, 6, 0, tzinfo=timezone.utc)
_ORIGIN = "http://127.0.0.1"


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr(watchlist_view, "utc_today", lambda: TODAY)


def _session(client):
    return client.app.state.testing_session_local()


def _company(client, ticker="AAPL", name="Apple Inc.", description=None):
    session = _session(client)
    try:
        row = CompanyDB(
            name=name, ticker=ticker, currency="USD", description=description
        )
        session.add(row)
        session.commit()
        return row.id
    finally:
        session.close()


def _watch(client, company_id, label=None):
    session = _session(client)
    try:
        WatchlistRepository(session).add(company_id, label)
    finally:
        session.close()


def _bars(client, company_id, closes, source="fake"):
    session = _session(client)
    try:
        for day, close in closes:
            session.add(
                PriceBarDB(
                    instrument_id=company_id,
                    bar_date=day,
                    close_price=Decimal(close),
                    currency="USD",
                    source=source,
                    retrieved_at=RETRIEVED,
                )
            )
        session.commit()
    finally:
        session.close()


def _assert_ui_headers(response):
    policy = response.headers["content-security-policy"]
    assert policy == (
        "default-src 'self'; base-uri 'self'; "
        "form-action 'self'; frame-ancestors 'none'"
    )
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_watchlist_lists_price_change_trend_and_date(client):
    company_id = _company(client)
    _watch(client, company_id, label="long term")
    _bars(
        client,
        company_id,
        [(date(2026, 10, 19), "100"), (date(2026, 10, 26), "101.24")],
    )
    response = await client.get("/ui/watchlist")
    assert response.status_code == 200
    html = response.text
    assert "101,24" in html
    assert "+1,24" in html
    assert "<polyline" in html
    assert "26.10.2026" in html
    assert f'href="/ui/instruments/{company_id}"' in html
    assert "long term" in html
    assert "AAPL" in html
    assert "nieaktualne" not in html


@pytest.mark.asyncio
async def test_watchlist_empty_state_links_to_instruments(client):
    response = await client.get("/ui/watchlist")
    assert response.status_code == 200
    assert "Watchlista jest pusta" in response.text
    assert 'href="/ui"' in response.text
    assert "<table" not in response.text


@pytest.mark.asyncio
async def test_watchlist_marks_a_stale_price(client):
    company_id = _company(client)
    _watch(client, company_id)
    _bars(client, company_id, [(date(2026, 9, 28), "10")])
    response = await client.get("/ui/watchlist")
    assert "nieaktualne" in response.text
    assert "Notowanie starsze niż 7 dni" in response.text


@pytest.mark.asyncio
async def test_watchlist_row_without_prices(client):
    company_id = _company(client)
    _watch(client, company_id)
    response = await client.get("/ui/watchlist")
    assert "brak notowań" in response.text
    assert "<polyline" not in response.text
    assert "nieaktualne" not in response.text


@pytest.mark.asyncio
async def test_watchlist_single_bar_has_no_change(client):
    company_id = _company(client)
    _watch(client, company_id)
    _bars(client, company_id, [(date(2026, 10, 26), "42.5")])
    html = (await client.get("/ui/watchlist")).text
    assert "42,50" in html
    change_cell = html.split('data-field="change"', 1)[1].split("</td>", 1)[0]
    assert "—" in change_cell
    assert "%" not in change_cell


@pytest.mark.asyncio
async def test_watchlist_english_strings(client):
    company_id = _company(client)
    _watch(client, company_id)
    _bars(
        client,
        company_id,
        [(date(2026, 9, 21), "10"), (date(2026, 9, 28), "9.5")],
    )
    client.cookies.set("ui_lang", "en")
    html = (await client.get("/ui/watchlist")).text
    assert "<h1>Watchlist</h1>" in html
    assert "Change" in html
    assert "stale" in html
    assert "Sep 28, 2026" in html
    assert "-5.00" in html
    assert "vs Sep 21, 2026" in html


@pytest.mark.asyncio
async def test_watchlist_shows_source_and_synthetic_badge(client):
    company_id = _company(
        client, description="[IAC-DEMO-V2] Synthetic company"
    )
    _watch(client, company_id)
    _bars(client, company_id, [(date(2026, 10, 26), "5")], "[IAC-DEMO-V2]")
    html = (await client.get("/ui/watchlist")).text
    assert "źródło: [IAC-DEMO-V2]" in html
    assert "dane syntetyczne" in html


@pytest.mark.asyncio
async def test_watchlist_headers_nav_and_no_inline_style(client):
    company_id = _company(client)
    _watch(client, company_id)
    _bars(
        client,
        company_id,
        [(date(2026, 10, 19), "1"), (date(2026, 10, 26), "2")],
    )
    response = await client.get("/ui/watchlist")
    _assert_ui_headers(response)
    assert 'href="/ui/watchlist"' in response.text
    assert "style=" not in response.text
    detail = await client.get(f"/ui/instruments/{company_id}")
    assert 'href="/ui/watchlist"' in detail.text


async def _post(client, path, data=None, *, origin=_ORIGIN, htmx=False):
    headers = {}
    if origin is not None:
        headers["origin"] = origin
    if htmx:
        headers["hx-request"] = "true"
    return await client.post(path, data=data or {}, headers=headers)


def _stored(client, company_id):
    session = _session(client)
    try:
        row = WatchlistRepository(session).get_by_company_id(company_id)
        return None if row is None else (row.company_id, row.label)
    finally:
        session.close()


@pytest.mark.asyncio
async def test_heart_adds_and_removes_with_plain_post(client):
    company_id = _company(client)
    detail = (await client.get(f"/ui/instruments/{company_id}")).text
    assert 'aria-pressed="false"' in detail
    assert "Dodaj do watchlisty" in detail
    assert "♡" in detail

    added = await _post(
        client, f"/ui/watchlist/{company_id}", {"from": "detail"}
    )
    assert added.status_code == 303
    assert added.headers["location"] == f"/ui/instruments/{company_id}"
    assert _stored(client, company_id) == (company_id, None)
    detail = (await client.get(f"/ui/instruments/{company_id}")).text
    assert 'aria-pressed="true"' in detail
    assert "Usuń z watchlisty" in detail
    assert "♥" in detail

    removed = await _post(
        client, f"/ui/watchlist/{company_id}/remove", {"from": "detail"}
    )
    assert removed.status_code == 303
    assert removed.headers["location"] == f"/ui/instruments/{company_id}"
    assert _stored(client, company_id) is None


@pytest.mark.asyncio
async def test_heart_htmx_returns_only_the_heart(client):
    company_id = _company(client)
    response = await _post(
        client, f"/ui/watchlist/{company_id}", {"from": "detail"}, htmx=True
    )
    assert response.status_code == 200
    assert "<html" not in response.text
    assert 'class="watchlist-heart"' in response.text
    assert 'aria-pressed="true"' in response.text
    assert f'hx-post="/ui/watchlist/{company_id}/remove"' in response.text
    _assert_ui_headers(response)


@pytest.mark.asyncio
async def test_repeat_add_keeps_the_label(client):
    company_id = _company(client)
    _watch(client, company_id, label="long term")
    response = await _post(
        client, f"/ui/watchlist/{company_id}", {"from": "detail"}
    )
    assert response.status_code == 303
    assert _stored(client, company_id) == (company_id, "long term")


@pytest.mark.asyncio
async def test_remove_from_the_watchlist_page(client):
    company_id = _company(client)
    _watch(client, company_id)
    plain = await _post(
        client, f"/ui/watchlist/{company_id}/remove", {"from": "watchlist"}
    )
    assert plain.status_code == 303
    assert plain.headers["location"] == "/ui/watchlist"

    _watch(client, company_id)
    fragment = await _post(
        client,
        f"/ui/watchlist/{company_id}/remove",
        {"from": "watchlist"},
        htmx=True,
    )
    assert fragment.status_code == 200
    assert "<html" not in fragment.text
    assert 'id="watchlist-table"' in fragment.text
    assert "Watchlista jest pusta" in fragment.text
    assert _stored(client, company_id) is None


@pytest.mark.asyncio
async def test_remove_of_a_company_that_is_not_listed_is_not_an_error(client):
    company_id = _company(client)
    plain = await _post(
        client, f"/ui/watchlist/{company_id}/remove", {"from": "detail"}
    )
    assert plain.status_code == 303
    fragment = await _post(
        client,
        f"/ui/watchlist/{company_id}/remove",
        {"from": "detail"},
        htmx=True,
    )
    assert fragment.status_code == 200
    assert 'aria-pressed="false"' in fragment.text


@pytest.mark.asyncio
@pytest.mark.parametrize("raw_id", ["999999", "abc", "01"])
@pytest.mark.parametrize("htmx", [False, True])
@pytest.mark.parametrize("action", ["", "/remove"])
async def test_unknown_company_is_the_html_404(client, raw_id, htmx, action):
    response = await _post(
        client,
        f"/ui/watchlist/{raw_id}{action}",
        {"from": "detail"},
        htmx=htmx,
    )
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_cross_origin_add_is_403(client):
    company_id = _company(client)
    response = await _post(
        client,
        f"/ui/watchlist/{company_id}",
        {"from": "detail"},
        origin="http://evil.example",
    )
    assert response.status_code == 403
    assert _stored(client, company_id) is None


@pytest.mark.asyncio
async def test_unknown_from_value_returns_to_the_detail_page(client):
    company_id = _company(client)
    response = await _post(
        client, f"/ui/watchlist/{company_id}", {"from": "https://evil.example"}
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/ui/instruments/{company_id}"


class _FormInParagraph(HTMLParser):
    """Records a <form> that starts while a <p> is still open.

    The HTML parser in a browser closes the <p> at that point, which
    pushes the heart onto its own line under the company name.
    """

    def __init__(self):
        super().__init__()
        self.open_paragraphs = 0
        self.nested = False

    def handle_starttag(self, tag, attrs):
        if tag == "p":
            self.open_paragraphs += 1
        if tag == "form" and self.open_paragraphs:
            self.nested = True

    def handle_endtag(self, tag):
        if tag == "p" and self.open_paragraphs:
            self.open_paragraphs -= 1


@pytest.mark.asyncio
async def test_heart_is_not_inside_a_paragraph(client):
    company_id = _company(client)
    html = (await client.get(f"/ui/instruments/{company_id}")).text
    parser = _FormInParagraph()
    parser.feed(html)
    assert 'class="watchlist-heart"' in html
    assert parser.nested is False


def _row(html, company_id):
    """The ``<tr>`` of one company in the watchlist table."""
    start = html.index(f'<tr data-company-id="{company_id}">')
    end = html.index("</tr>", start)
    return html[start:end]


@pytest.mark.asyncio
async def test_htmx_errors_fall_back_to_a_plain_post(client):
    """A failed HTMX request must not leave the click without effect.

    ``static/ui.js`` posts the form again without HTMX, so the browser
    shows what the server answered, for example the 404 page of a
    company deleted in another tab. Add and remove are both safe to
    repeat.
    """
    company_id = _company(client)
    _watch(client, company_id)
    detail = (await client.get(f"/ui/instruments/{company_id}")).text
    table = (await client.get("/ui/watchlist")).text
    htmx_at = detail.find('src="/static/vendor/htmx-2.0.10.min.js"')
    script_at = detail.find('<script src="/static/ui.js" defer></script>')
    assert htmx_at != -1
    assert script_at > htmx_at
    heart = detail.split('class="watchlist-heart"', 1)[1].split(">", 1)[0]
    assert "data-plain-fallback" in heart
    remove = _row(table, company_id).split("<form", 1)[1].split(">", 1)[0]
    assert "data-plain-fallback" in remove

    script = await client.get("/static/ui.js")
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]
    assert "htmx:responseError" in script.text
    assert "htmx:sendError" in script.text
    assert "data-plain-fallback" in script.text


@pytest.mark.asyncio
async def test_heart_button_keeps_its_id_for_focus(client):
    """HTMX moves focus back only to an element whose id survives."""
    company_id = _company(client)
    detail = (await client.get(f"/ui/instruments/{company_id}")).text
    assert detail.count('id="watchlist-heart-button"') == 1
    fragment = await _post(
        client, f"/ui/watchlist/{company_id}", {"from": "detail"}, htmx=True
    )
    assert fragment.text.count('id="watchlist-heart-button"') == 1


@pytest.mark.asyncio
async def test_remove_focuses_the_row_that_takes_its_place(client):
    """After ✕ the focus goes to the next row, or to the previous one
    when the last row went, or to the empty state link."""
    first = _company(client, ticker="AAA", name="First")
    second = _company(client, ticker="BBB", name="Second")
    third = _company(client, ticker="CCC", name="Third")
    for company_id in (first, second, third):
        _watch(client, company_id)
    page = (await client.get("/ui/watchlist")).text
    assert "autofocus" not in page

    async def remove(company_id):
        response = await _post(
            client,
            f"/ui/watchlist/{company_id}/remove",
            {"from": "watchlist"},
            htmx=True,
        )
        assert response.status_code == 200
        assert response.text.count("autofocus") == 1
        return response.text

    html = await remove(second)
    assert "autofocus" in _row(html, third)
    html = await remove(third)
    assert "autofocus" in _row(html, first)
    html = await remove(first)
    assert '<a href="/ui" autofocus>' in html


@pytest.mark.asyncio
async def test_remove_buttons_name_their_company(client):
    company_id = _company(client, name='Apple "Inc."')
    _watch(client, company_id)
    row = _row((await client.get("/ui/watchlist")).text, company_id)
    label = "Usuń Apple &#34;Inc.&#34; z watchlisty"
    assert f'aria-label="{label}"' in row
    assert f'title="{label}"' in row
    client.cookies.set("ui_lang", "en")
    row = _row((await client.get("/ui/watchlist")).text, company_id)
    assert 'aria-label="Remove Apple &#34;Inc.&#34; from watchlist"' in row


def _engine(client):
    """The test engine. Seeding and the page share it."""
    return client.app.state.testing_session_local.kw["bind"]


def _record_statements(engine):
    """Append SQL text until the caller stops the listener.

    The returned list and the stop function. The watchlist route is
    synchronous, and the test client runs it on a worker thread, so
    the listener has to stay installed across the ``await``.
    """
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(" ".join(statement.split()))

    event.listen(engine, "before_cursor_execute", record)

    def stop():
        event.remove(engine, "before_cursor_execute", record)

    return statements, stop


def _statements(engine, call):
    """SQL text executed while the synchronous ``call`` runs."""
    statements, stop = _record_statements(engine)
    try:
        call()
    finally:
        stop()
    return statements


def _seed_priced_watch_rows(client, count, start=0):
    """``count`` watchlist rows that each have two closes.

    Every row has the same shape, so a per-row query would add the
    same number of statements for each extra company. The latest
    close is ``110 + index`` and shows up in the Polish price cell.
    """
    seeded = []
    for index in range(start, start + count):
        ticker = f"W{index:02d}"
        company_id = _company(client, ticker=ticker, name=f"Name {index}")
        _watch(client, company_id)
        _bars(
            client,
            company_id,
            [
                (date(2026, 10, 19), str(100 + index)),
                (date(2026, 10, 26), str(110 + index)),
            ],
        )
        seeded.append((ticker, f"{110 + index},00"))
    return seeded


async def _watchlist_page(client):
    """HTML and the SQL statements of one GET /ui/watchlist."""
    engine = _engine(client)
    statements, stop = _record_statements(engine)
    try:
        response = await client.get("/ui/watchlist")
    finally:
        stop()
    assert response.status_code == 200
    return response.text, statements


def _assert_rendered(html, seeded):
    for ticker, price in seeded:
        assert ticker in html
        assert price in html


async def assert_watchlist_query_count_is_flat(client):
    """GET /ui/watchlist uses the same number of statements for 1 and 10 rows.

    Returns that number. Every seeded ticker and its latest close
    must still be on the page. One row and ten rows have the same
    price shape, so a per-row query would make the second count
    larger.
    """
    first = _seed_priced_watch_rows(client, 1)
    one_html, one_statements = await _watchlist_page(client)
    _assert_rendered(one_html, first)

    rest = _seed_priced_watch_rows(client, 9, start=1)
    ten_html, ten_statements = await _watchlist_page(client)
    _assert_rendered(ten_html, first + rest)

    assert len(one_statements) == len(ten_statements), (
        f"1 row ran {len(one_statements)} statements, "
        f"10 rows ran {len(ten_statements)}:\n"
        + "\n".join(statement[:120] for statement in ten_statements)
    )
    return len(one_statements)


@pytest.mark.asyncio
async def test_watchlist_query_count_does_not_grow_with_rows(client):
    """One row and ten rows hit the database the same number of times.

    Before the batch read, one row was 6 statements and ten rows were
    51 (one list, then five queries per row). The page now loads the
    companies with the list and the closes in a fixed handful of
    queries. SQLite is the database this test opens.
    """
    count = await assert_watchlist_query_count_is_flat(client)
    assert count == 4, count


def _add_bar(
    client,
    company_id,
    day,
    close,
    source="fake",
    retrieved_at=RETRIEVED,
):
    session = _session(client)
    try:
        session.add(
            PriceBarDB(
                instrument_id=company_id,
                bar_date=day,
                close_price=None if close is None else Decimal(close),
                currency="USD",
                source=source,
                retrieved_at=retrieved_at,
            )
        )
        session.commit()
    finally:
        session.close()


def _recent_signature(recent):
    """The fields the watchlist page reads, for one series or None."""
    if recent is None:
        return None
    previous = recent.previous
    return (
        recent.source,
        recent.latest.bar_date,
        recent.latest.close_price,
        (
            None
            if previous is None
            else (previous.bar_date, previous.close_price)
        ),
        [(bar.bar_date, bar.close_price) for bar in recent.window],
    )


@pytest.mark.asyncio
async def test_recent_closes_for_matches_one_query_per_company(client):
    """The batch read returns the same closes as ``recent_closes``.

    The cases are the ones the page can show: no bars, a bar with no
    close, one close, a previous close inside the window, a previous
    close older than 92 days, a null close between two real ones, and
    two sources (a later retrieval wins, and a tie uses code-point
    order). An empty id list does not query.
    """
    empty = _company(client, ticker="NONE", name="No Prices")
    null_only = _company(client, ticker="NULL", name="Null Close")
    _add_bar(client, null_only, date(2026, 9, 28), None)
    single = _company(client, ticker="ONE", name="One Close")
    _add_bar(client, single, date(2026, 10, 26), "5")
    inside = _company(client, ticker="IN", name="Inside Window")
    _add_bar(client, inside, date(2026, 10, 19), "10")
    _add_bar(client, inside, date(2026, 10, 26), "12")
    older = _company(client, ticker="OLD", name="Old Previous")
    _add_bar(client, older, date(2026, 1, 1), "1")
    _add_bar(client, older, date(2026, 10, 26), "2")
    skipped = _company(client, ticker="SKIP", name="Skipped Null")
    _add_bar(client, skipped, date(2026, 9, 21), "10")
    _add_bar(client, skipped, date(2026, 9, 28), None)
    _add_bar(client, skipped, date(2026, 10, 5), "11")
    later = _company(client, ticker="LATER", name="Later Source")
    _add_bar(
        client,
        later,
        date(2026, 9, 28),
        "10",
        source="[IAC-DEMO-V2]",
        retrieved_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    _add_bar(
        client,
        later,
        date(2026, 9, 21),
        "21",
        source="fake",
        retrieved_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
    )
    tied = _company(client, ticker="TIE", name="Tied Retrieval")
    same_time = datetime(2026, 10, 3, tzinfo=timezone.utc)
    _add_bar(
        client,
        tied,
        date(2026, 10, 26),
        "30",
        source="[IAC-DEMO-V2]",
        retrieved_at=same_time,
    )
    _add_bar(
        client,
        tied,
        date(2026, 10, 26),
        "31",
        source="fake",
        retrieved_at=same_time,
    )

    ids = [empty, null_only, single, inside, older, skipped, later, tied]
    session = _session(client)
    try:
        repo = PriceBarRepository(session)
        engine = _engine(client)
        quiet = _statements(engine, lambda: repo.recent_closes_for([]))
        assert quiet == []
        # No bars, and bars whose close is null, stop before the
        # window query. Both are absent from a mixed batch too.
        assert repo.recent_closes_for([empty]) == {}
        assert repo.recent_closes_for([null_only]) == {}
        batched = repo.recent_closes_for(ids + [inside])
        for instrument_id in ids:
            single_recent = repo.recent_closes(instrument_id)
            if single_recent is None:
                assert instrument_id not in batched
            else:
                assert _recent_signature(batched[instrument_id]) == (
                    _recent_signature(single_recent)
                )
        assert set(batched) == {
            instrument_id
            for instrument_id in ids
            if instrument_id not in (empty, null_only)
        }
    finally:
        session.close()


@pytest.mark.asyncio
async def test_batched_watchlist_still_shows_mixed_rows(client):
    """A row with no prices and a row on the later source both render.

    The batch path has to keep the em dash and the winning source.
    ``fake`` wins the tie because its name sorts after
    ``[IAC-DEMO-V2]``.
    """
    bare = _company(client, ticker="BARE", name="Bare Co")
    _watch(client, bare)
    priced = _company(client, ticker="PRICED", name="Priced Co")
    _watch(client, priced, label="core")
    same_time = datetime(2026, 10, 3, tzinfo=timezone.utc)
    _add_bar(
        client,
        priced,
        date(2026, 10, 19),
        "10",
        source="[IAC-DEMO-V2]",
        retrieved_at=same_time,
    )
    _add_bar(
        client,
        priced,
        date(2026, 10, 26),
        "11",
        source="[IAC-DEMO-V2]",
        retrieved_at=same_time,
    )
    _add_bar(
        client,
        priced,
        date(2026, 10, 19),
        "40",
        source="fake",
        retrieved_at=same_time,
    )
    _add_bar(
        client,
        priced,
        date(2026, 10, 26),
        "42",
        source="fake",
        retrieved_at=same_time,
    )
    html = (await client.get("/ui/watchlist")).text
    assert "brak notowań" in html
    assert "BARE" in html
    assert "42,00" in html
    assert "PRICED" in html
    assert "źródło: fake" in html
    assert "core" in html
    # 40 -> 42 is +5%. The other source must not leak into the row.
    assert "11,00" not in html
