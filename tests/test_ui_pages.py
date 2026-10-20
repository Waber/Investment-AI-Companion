"""Rendered /ui pages: languages, filters, missing values, escaping."""

import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

import pytest
import pytest_asyncio
from starlette.requests import Request

from app.models.database_models import CompanyDB, FinancialMetricsDB
from scripts.seed_demo import SqliteSeedClient, load_fixture, seed_demo
from tests.ui_html import assert_no_dangerous_href, parse_page, plain

_CDN = (
    "cdn.jsdelivr.net",
    "unpkg.com",
    "cdnjs.cloudflare.com",
    "ajax.googleapis.com",
    "htmx.org",
)


def test_safe_next_rejects_a_parent_segment():
    """``/ui/../api/...`` starts with /ui and still leaves /ui."""
    from app.ui.router import (
        _fully_unquoted_path,
        _is_language_switch,
        _path_escapes_ui,
        safe_next,
    )

    assert safe_next("/ui/../api/v1/companies/") == "/ui"
    assert safe_next("/ui/%2e%2e/api/v1/companies/") == "/ui"
    assert safe_next("/ui/%252e%252e/api/v1/companies/") == "/ui"
    assert safe_next("/ui/%5cevil") == "/ui"
    assert safe_next("/ui/instruments/1") == "/ui/instruments/1"
    # The language route must not be the return path. The list and
    # a filtered list stay allowed.
    assert safe_next("/ui/language/pl") == "/ui"
    assert safe_next("/ui/language/en") == "/ui"
    assert safe_next("/ui/language/en?next=/ui") == "/ui"
    assert safe_next("/ui/language/pl?next=/ui/instruments/1") == "/ui"
    assert safe_next("/ui/language") == "/ui"
    assert safe_next("/ui/language/") == "/ui"
    assert safe_next("/ui?exchange=DEMO-WSE") == "/ui?exchange=DEMO-WSE"
    # ``.`` is the current directory. ``%2e`` is that dot, and
    # ``%252e`` is an encoded ``%2e``. One unquote is not enough.
    dot_paths = (
        "/ui/./language/pl",
        "/ui/./language/en",
        "/ui/%2e/language/pl",
        "/ui/%2E/language/pl",
        "/ui/%252e/language/pl",
        "/ui/%25252e/language/en",
        "/ui/language/./pl",
        "/ui/language/%2e/en",
        "/ui/foo/../language/pl",
    )
    for value in dot_paths:
        assert _path_escapes_ui(value) is True, value
        assert _is_language_switch(value) is True, value
        assert safe_next(value) == "/ui", value
    # A dot in front of a normal page is also not a second URL.
    assert _path_escapes_ui("/ui/./instruments/1") is True
    assert _is_language_switch("/ui/./instruments/1") is False
    assert safe_next("/ui/./instruments/1") == "/ui"
    # Nine encodings of ``.``. Eight unquotes still leave ``%2e``.
    unsettled = "/ui/%25252525252525252e/language/pl"
    assert _fully_unquoted_path(unsettled) is None
    assert _path_escapes_ui(unsettled) is True
    assert _is_language_switch(unsettled) is True
    assert safe_next(unsettled) == "/ui"


def _page_request(method, path, query=""):
    """A request with just enough scope to read method, path, and query."""
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": query.encode("ascii"),
        "headers": [(b"host", b"127.0.0.1")],
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 80),
    }
    return Request(scope)


def test_language_next_path_uses_the_get_form_for_a_post():
    """A POST page must not send the language switch to a POST-only URL."""
    from app.ui.templating import language_next_path

    assert (
        language_next_path(_page_request("GET", "/ui", "q=Lodz"))
        == "/ui?q=Lodz"
    )
    assert (
        language_next_path(_page_request("GET", "/ui/companies/new"))
        == "/ui/companies/new"
    )
    assert (
        language_next_path(_page_request("POST", "/ui/companies", "from=1"))
        == "/ui/companies/new?from=1"
    )
    assert (
        language_next_path(_page_request("POST", "/ui/companies/7/metrics"))
        == "/ui/companies/7/metrics/new"
    )
    assert (
        language_next_path(_page_request("POST", "/ui/companies/7/edit"))
        == "/ui/companies/7/edit"
    )
    assert (
        language_next_path(
            _page_request("POST", "/ui/companies/7/delete", "x=1")
        )
        == "/ui/companies/7/delete?x=1"
    )
    assert (
        language_next_path(
            _page_request("POST", "/ui/companies/7/metrics/3/edit")
        )
        == "/ui/companies/7/metrics/3/edit"
    )
    assert (
        language_next_path(
            _page_request("POST", "/ui/companies/7/metrics/3/delete")
        )
        == "/ui/companies/7/metrics/3/delete"
    )
    assert language_next_path(_page_request("POST", "/ui")) == "/ui"
    assert (
        language_next_path(_page_request("POST", "/ui/instruments/1")) == "/ui"
    )


def test_safe_next_drops_a_path_that_parses_as_absolute(monkeypatch):
    """The scheme check stays even when the prefix check already passed."""
    from types import SimpleNamespace

    from app.ui import router as ui_router

    def fake_split(_value):
        return SimpleNamespace(scheme="http", netloc="evil.example")

    monkeypatch.setattr(ui_router, "urlsplit", fake_split)
    assert ui_router.safe_next("/ui/instruments/1") == "/ui"


# A same-origin form POST sends Origin. This client uses port 80.
_LANGUAGE_ORIGIN = {"origin": "http://127.0.0.1"}


async def _switch_language(client, code, *, next="/ui", headers=None):
    """POST the language route the way the PL/EN button does.

    Pass ``headers`` to replace Origin, including ``{}`` for a request
    that carries neither Origin nor Referer.
    """
    sent = dict(_LANGUAGE_ORIGIN)
    if headers is not None:
        sent = headers
    return await client.post(
        f"/ui/language/{code}", data={"next": next}, headers=sent
    )


def _language_next(html, code):
    """Return the hidden ``next`` value on the PL or EN form."""
    match = re.search(
        rf'<form method="post" action="/ui/language/{code}">\s*'
        rf'<input type="hidden" name="next" value="([^"]*)"',
        html,
    )
    assert match is not None
    return match.group(1).replace("&amp;", "&")


def _location(response):
    location = response.headers["location"]
    parts = urlsplit(location)
    if parts.scheme:
        query = f"?{parts.query}" if parts.query else ""
        return f"{parts.path}{query}"
    return location


def _add_company(client, **overrides):
    values = {
        "name": "Plain Name",
        "ticker": "WEBCO",
        "currency": "USD",
        "exchange": "XNAS",
        "description": "Stored by hand",
    }
    values.update(overrides)
    session = client.app.state.testing_session_local()
    try:
        row = CompanyDB(**values)
        session.add(row)
        session.commit()
        return row.id
    finally:
        session.close()


def _href_for(html, ticker):
    match = re.search(
        rf'href="(/ui/instruments/\d+)">{re.escape(ticker)}</a>',
        html,
    )
    assert match is not None, ticker
    return match.group(1)


@pytest_asyncio.fixture
async def seeded(client):
    session = client.app.state.testing_session_local()
    try:
        summary = seed_demo(
            load_fixture(), SqliteSeedClient(session), apply=True
        )
    finally:
        session.close()
    assert summary["companies"]["created"] == 6
    assert summary["metrics"]["created"] == 20
    return client


@pytest.mark.asyncio
async def test_pages_render_in_polish_by_default(seeded):
    page = await seeded.get("/ui")
    assert page.status_code == 200
    assert "Nie jest poradą inwestycyjną" in page.text
    assert "dane syntetyczne" in page.text
    assert "not financial advice" not in page.text.casefold()
    assert "DEMO_PL_TECH" in page.text
    assert "demo-v1" in page.text
    script_at = page.text.find('src="/static/vendor/htmx-2.0.10.min.js"')
    config_at = page.text.find('name="htmx-config"')
    assert script_at != -1
    assert config_at != -1
    assert "includeIndicatorStyles" in page.text
    assert '"allowEval":false' in page.text
    assert '"allowScriptTags":false' in page.text
    assert config_at < script_at
    assert 'href="/static/ui.css"' in page.text
    assert_no_dangerous_href(page.text)
    lowered = page.text.casefold()
    assert 'src="http' not in lowered
    assert "src='http" not in lowered
    for host in _CDN:
        assert host not in lowered

    detail = await seeded.get(_href_for(page.text, "DEMO_PL_TECH"))
    assert detail.status_code == 200
    assert "Nie jest poradą inwestycyjną" in detail.text
    assert "dane syntetyczne" in detail.text
    assert "akcja" in detail.text
    assert "demo-v1" in detail.text
    assert_no_dangerous_href(detail.text)


@pytest.mark.asyncio
async def test_english_cookie_persists_across_pages(seeded):
    switched = await _switch_language(seeded, "en")
    assert switched.status_code == 303
    assert _location(switched) == "/ui"
    cookie = switched.headers["set-cookie"]
    folded = cookie.casefold()
    assert "ui_lang=en" in folded
    assert "httponly" in folded
    assert "samesite=lax" in folded
    assert "path=/" in folded
    assert "max-age=31536000" in folded

    page = await seeded.get("/ui")
    assert "not financial advice" in page.text.casefold()
    assert "synthetic data" in page.text
    assert "dane syntetyczne" not in page.text
    detail = await seeded.get(_href_for(page.text, "DEMO_PL_EMPTY"))
    assert "not financial advice" in detail.text.casefold()
    assert "synthetic data" in detail.text
    assert "stock" in detail.text
    assert "No reports" in detail.text

    seeded.cookies.clear()
    seeded.cookies.set("ui_lang", "en")
    restarted = await seeded.get("/ui")
    assert "synthetic data" in restarted.text
    seeded.cookies.set("ui_lang", "fr")
    invalid = await seeded.get("/ui")
    assert "Nie jest poradą inwestycyjną" in invalid.text


@pytest.mark.asyncio
async def test_language_switch_rejects_open_redirects(client):
    targets = [
        "https://evil.example/ui",
        "//evil.example",
        "/other",
        "/ui/\\evil",
        "/ui/%0d%0aSet-Cookie:x",
        "/ui\r\nX: 1",
        "/ui/../api/v1/companies/",
    ]
    for target in targets:
        response = await _switch_language(client, "en", next=target)
        assert response.status_code == 303
        assert _location(response) == "/ui"
    # A POST with no ``next`` field falls back to /ui.
    plain = await client.post(
        "/ui/language/pl", headers={"origin": "http://127.0.0.1"}
    )
    assert plain.status_code == 303
    assert _location(plain) == "/ui"
    # An unknown code does not set a cookie. GET stays 404. A
    # same-origin POST stays 404. A cross-site POST is 403 because
    # the origin dependency runs before the route sees the code.
    missing = await client.get("/ui/language/de")
    assert missing.status_code == 404
    assert "Nie znaleziono instrumentu" in missing.text
    assert "set-cookie" not in missing.headers
    foreign_code = await client.get(
        "/ui/language/de", headers={"origin": "http://evil.example"}
    )
    assert foreign_code.status_code == 404
    assert "set-cookie" not in foreign_code.headers
    posted_missing = await _switch_language(client, "de")
    assert posted_missing.status_code == 404
    assert "set-cookie" not in posted_missing.headers
    foreign_post = await client.post(
        "/ui/language/de",
        data={"next": "/ui"},
        headers={"origin": "http://evil.example"},
    )
    assert foreign_post.status_code == 403
    assert "set-cookie" not in foreign_post.headers
    unknown = await client.get("/ui/instruments/999999")
    assert unknown.status_code == 404
    assert "Nie jest poradą inwestycyjną" in unknown.text


def _assert_ui_headers(response):
    policy = response.headers["content-security-policy"]
    assert "default-src 'self'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "http://" not in policy
    assert "https://" not in policy
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "same-origin"
    assert response.headers["vary"] == "HX-Request"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_history_restore_returns_the_full_page(seeded):
    restored = await seeded.get(
        "/ui",
        headers={
            "HX-Request": "true",
            "HX-History-Restore-Request": "true",
        },
    )
    assert restored.status_code == 200
    assert "<html" in restored.text.casefold()
    assert "Nie jest poradą inwestycyjną" in restored.text
    _assert_ui_headers(restored)

    fragment = await seeded.get("/ui", headers={"HX-Request": "true"})
    assert "<html" not in fragment.text.casefold()
    assert "Nie jest poradą inwestycyjną" not in fragment.text
    assert 'action="/ui/language/pl"' in restored.text
    assert 'action="/ui/language/en"' in restored.text
    assert 'method="post"' in restored.text
    assert "hx-post" not in restored.text
    assert 'hx-swap-oob="outerHTML"' not in restored.text
    # The fragment carries the return path out of band. It still has
    # no language form, header, or disclaimer.
    assert 'action="/ui/language/' not in fragment.text
    assert 'hx-swap-oob="outerHTML"' in fragment.text
    assert 'id="language-next-pl"' in fragment.text
    assert 'value="/ui"' in fragment.text
    _assert_ui_headers(fragment)


@pytest.mark.asyncio
async def test_non_integer_instrument_id_is_html_not_json(client):
    page = await client.get("/ui/instruments/abc")
    assert page.status_code == 404
    assert "text/html" in page.headers["content-type"]
    assert "Nie znaleziono instrumentu" in page.text
    assert "Nie jest poradą inwestycyjną" in page.text
    assert not page.text.lstrip().startswith("{")
    _assert_ui_headers(page)

    api = await client.get("/api/v1/companies/abc")
    assert api.status_code == 422
    assert "application/json" in api.headers["content-type"]


@pytest.mark.asyncio
async def test_instrument_id_rejects_unicode_digits_and_overflow(seeded):
    listing = await seeded.get("/ui")
    detail = await seeded.get(_href_for(listing.text, "DEMO_PL_TECH"))
    assert detail.status_code == 200
    assert "DEMO_PL_TECH" in detail.text
    assert "Nie jest poradą inwestycyjną" in detail.text

    rejected = (
        "/ui/instruments/\u00b2",
        "/ui/instruments/\u0661",
        "/ui/instruments/" + ("1" * 23),
        "/ui/instruments/" + ("1" * 5000),
        "/ui/instruments/" + str(2**63),
    )
    for path in rejected:
        page = await seeded.get(path)
        assert page.status_code == 404, path
        assert "text/html" in page.headers["content-type"]
        assert "Nie znaleziono instrumentu" in page.text
        assert "DEMO_PL_TECH" not in page.text
        assert not page.text.lstrip().startswith("{")

    at_limit = await seeded.get("/ui/instruments/" + str(2**63 - 1))
    assert at_limit.status_code == 404
    assert "Nie znaleziono instrumentu" in at_limit.text


@pytest.mark.asyncio
async def test_leading_zero_is_not_a_second_url(seeded):
    listing = await seeded.get("/ui")
    href = _href_for(listing.text, "DEMO_PL_TECH")
    real = await seeded.get(href)
    assert real.status_code == 200
    assert "DEMO_PL_TECH" in real.text
    padded = await seeded.get("/ui/instruments/0" + href.rsplit("/", 1)[-1])
    assert padded.status_code == 404
    assert "DEMO_PL_TECH" not in padded.text

    created = _add_company(seeded, name="Padded Seven", ticker="PAD7")
    assert created == 7
    plain = await seeded.get("/ui/instruments/7")
    assert plain.status_code == 200
    assert "PAD7" in plain.text
    zero = await seeded.get("/ui/instruments/007")
    assert zero.status_code == 404
    assert "PAD7" not in zero.text
    lone = await seeded.get("/ui/instruments/0")
    assert lone.status_code == 404
    assert "Nie znaleziono instrumentu" in lone.text


@pytest.mark.asyncio
async def test_language_redirect_sends_the_ui_headers(client):
    response = await _switch_language(client, "pl")
    assert response.status_code == 303
    _assert_ui_headers(response)
    bookmark = await client.get("/ui/language/en", params={"next": "/ui"})
    assert bookmark.status_code == 303
    assert "set-cookie" not in bookmark.headers
    _assert_ui_headers(bookmark)


@pytest.mark.asyncio
async def test_language_link_returns_to_the_filtered_list(seeded):
    page = await seeded.get("/ui", params={"exchange": "DEMO-WSE"})
    target = _language_next(page.text, "en")
    assert target == "/ui?exchange=DEMO-WSE"
    assert "hx-post" not in page.text
    assert 'href="/ui/language/' not in page.text
    assert 'aria-current="true"' in page.text
    response = await _switch_language(seeded, "en", next=target)
    assert response.status_code == 303
    assert _location(response) == "/ui?exchange=DEMO-WSE"
    assert "ui_lang=en" in response.headers["set-cookie"].casefold()


@pytest.mark.asyncio
async def test_language_switch_requires_same_origin(client):
    """The cookie POST uses the same endpoint check as the other forms.

    A same-origin form sends ``Origin``. A cross-site ``Origin`` or
    ``Referer`` is an HTML 403 and does not set the cookie. A bad
    ``Origin`` is not rescued by a good ``Referer``. A POST with
    neither header is the same 403. The 403 page links back to /ui.
    """
    switched = await _switch_language(client, "en")
    assert switched.status_code == 303
    assert _location(switched) == "/ui"
    cookie = switched.headers["set-cookie"]
    assert "ui_lang=en" in cookie.casefold()
    page = await client.get("/ui")
    assert 'lang="en"' in page.text
    assert "Language" in page.text
    assert 'action="/ui/language/en"' in page.text
    assert (
        'action="/ui/language/en">\n'
        '          <input type="hidden" name="next" value="/ui" '
        'id="language-next-en">\n'
        '          <button type="submit" aria-current="true">'
    ) in page.text
    client.cookies.clear()

    cross_origin = await client.post(
        "/ui/language/en",
        data={"next": "/ui"},
        headers={"origin": "http://evil.example"},
    )
    assert cross_origin.status_code == 403
    assert "set-cookie" not in cross_origin.headers
    assert "text/html" in cross_origin.headers["content-type"]
    assert "Żądanie zostało odrzucone" in cross_origin.text
    assert 'href="/ui"' in cross_origin.text
    assert not cross_origin.text.lstrip().startswith("{")
    _assert_ui_headers(cross_origin)

    cross_referer = await client.post(
        "/ui/language/pl",
        data={"next": "/ui"},
        headers={"referer": "http://evil.example/trap"},
    )
    assert cross_referer.status_code == 403
    assert "set-cookie" not in cross_referer.headers

    rescued = await client.post(
        "/ui/language/en",
        data={"next": "/ui"},
        headers={
            "origin": "http://evil.example",
            "referer": "http://127.0.0.1/ui",
        },
    )
    assert rescued.status_code == 403
    assert "set-cookie" not in rescued.headers

    direct = await _switch_language(client, "en", headers={})
    assert direct.status_code == 403
    assert "set-cookie" not in direct.headers
    assert "Żądanie zostało odrzucone" in direct.text
    assert 'href="/ui"' in direct.text
    _assert_ui_headers(direct)

    listing = await client.get(
        "/ui", headers={"origin": "http://evil.example"}
    )
    assert listing.status_code == 200


@pytest.mark.asyncio
async def test_language_bookmark_does_not_set_the_cookie(client):
    """GET /ui/language/{code} redirects and leaves the cookie alone.

    An old bookmark has no Origin and no Referer. It must not 403
    and must not change the language. A cross-site GET is the same
    redirect, because that GET does not change state.
    """
    client.cookies.set("ui_lang", "en")
    bookmark = await client.get("/ui/language/pl", params={"next": "/ui"})
    assert bookmark.status_code == 303
    assert _location(bookmark) == "/ui"
    assert "set-cookie" not in bookmark.headers
    unchanged = await client.get("/ui")
    assert 'lang="en"' in unchanged.text

    detailed = await client.get(
        "/ui/language/pl", params={"next": "/ui/instruments/1"}
    )
    assert detailed.status_code == 303
    assert _location(detailed) == "/ui/instruments/1"
    assert "set-cookie" not in detailed.headers

    foreign = await client.get(
        "/ui/language/en",
        params={"next": "/ui"},
        headers={"origin": "http://evil.example"},
    )
    assert foreign.status_code == 303
    assert "set-cookie" not in foreign.headers
    still = await client.get("/ui")
    assert 'lang="en"' in still.text


@pytest.mark.asyncio
async def test_language_switch_does_not_return_to_itself(client):
    """A posted ``next`` that names the language route lands on /ui.

    The cookie is the language that was posted. A dotted or encoded
    path is the same route and is also replaced with ``/ui``.
    """
    targets = (
        "/ui/language/pl",
        "/ui/./language/pl",
        "/ui/%2e/language/pl",
        "/ui/%252e/language/en",
        "/ui/foo/../language/pl",
    )
    for target in targets:
        chosen = await _switch_language(client, "en", next=target)
        assert chosen.status_code == 303, target
        assert "ui_lang=en" in chosen.headers["set-cookie"].casefold()
        landed = _location(chosen)
        assert "/language/" not in landed
        assert landed.split("?", 1)[0] == "/ui"
        followed = await client.get(landed)
        assert followed.status_code == 200
        assert "set-cookie" not in followed.headers
        assert 'lang="en"' in followed.text


@pytest.mark.asyncio
async def test_filters_limit_the_list_and_htmx_returns_a_fragment(seeded):
    full = await seeded.get(
        "/ui",
        params={
            "q": "pAcIfIc",
            "exchange": "DEMO-NASDAQ",
            "currency": "USD",
        },
    )
    assert full.status_code == 200
    assert "<html" in full.text.casefold()
    assert "DEMO_US_GROWTH" in full.text
    assert "DEMO_PL_TECH" not in full.text
    assert 'value="pAcIfIc"' in full.text

    fragment = await seeded.get(
        "/ui",
        params={"exchange": "DEMO-WSE", "currency": "PLN"},
        headers={"HX-Request": "true"},
    )
    assert fragment.status_code == 200
    assert "<html" not in fragment.text.casefold()
    assert "Nie jest poradą" not in fragment.text
    assert "DEMO_PL_TECH" in fragment.text
    assert "DEMO_PL_EMPTY" in fragment.text
    assert "DEMO_US_GROWTH" not in fragment.text
    assert "dane syntetyczne" in fragment.text

    seeded.cookies.set("ui_lang", "en")
    english = await seeded.get(
        "/ui",
        params={"q": "no-such-name"},
        headers={"HX-Request": "true"},
    )
    assert "No instruments" in english.text
    assert "Brak instrumentów" not in english.text

    seeded.cookies.clear()
    by_type = await seeded.get("/ui", params={"type": "stock"})
    assert by_type.status_code == 200
    assert 'name="type"' in by_type.text
    assert '<option value="stock" selected>akcja</option>' in by_type.text
    assert ">wszystkie</option>" in by_type.text
    assert "DEMO_PL_TECH" in by_type.text
    assert "DEMO_US_GROWTH" in by_type.text
    assert by_type.text.count("<th ") == by_type.text.count('scope="col"')
    assert 'href="#main"' in by_type.text
    assert 'id="main"' in by_type.text
    assert "Przejdź do treści" in by_type.text

    unknown = await seeded.get(
        "/ui",
        params={"type": "etf"},
        headers={"HX-Request": "true"},
    )
    assert unknown.status_code == 200
    assert "<html" not in unknown.text.casefold()
    assert "Brak instrumentów" in unknown.text
    assert "DEMO_PL_TECH" not in unknown.text

    seeded.cookies.set("ui_lang", "en")
    english_type = await seeded.get("/ui", params={"type": "not-a-type"})
    assert english_type.status_code == 200
    assert '<option value="stock">stock</option>' in english_type.text
    assert ">any</option>" in english_type.text
    assert "No instruments" in english_type.text
    assert "Skip to main content" in english_type.text
    assert "DEMO_US_GROWTH" not in english_type.text

    seeded.cookies.clear()
    mismatch = await seeded.get(
        "/ui",
        params={"exchange": "DEMO-WSE", "currency": "USD"},
        headers={"HX-Request": "true"},
    )
    assert "Brak instrumentów" in mismatch.text
    assert "DEMO_PL_TECH" not in mismatch.text
    assert "DEMO_US_GROWTH" not in mismatch.text


def _oob_language_next(html, code):
    """Return the out-of-band ``next`` value for one language button."""
    match = re.search(
        rf'<input type="hidden" name="next" value="([^"]*)" '
        rf'id="language-next-{code}" hx-swap-oob="outerHTML">',
        html,
    )
    assert match is not None
    return match.group(1).replace("&amp;", "&")


@pytest.mark.asyncio
async def test_htmx_filter_updates_the_language_return_path(seeded):
    """A pushed filter URL must replace the hidden language next.

    The list starts at ``q=Lodz``. HTMX then swaps the results for
    ``q=Nope`` and pushes that URL. The header forms are outside the
    swap, so the fragment sends the new ``next`` out of band.
    """
    first = await seeded.get("/ui", params={"q": "Lodz"})
    assert _language_next(first.text, "pl") == "/ui?q=Lodz"
    assert "hx-swap-oob" not in first.text

    fragment = await seeded.get(
        "/ui", params={"q": "Nope"}, headers={"HX-Request": "true"}
    )
    assert fragment.status_code == 200
    assert "<html" not in fragment.text.casefold()
    assert _oob_language_next(fragment.text, "pl") == "/ui?q=Nope"
    assert _oob_language_next(fragment.text, "en") == "/ui?q=Nope"
    assert "q=Lodz" not in fragment.text

    both = await seeded.get(
        "/ui",
        params={"q": "Nope", "exchange": "DEMO-WSE"},
        headers={"HX-Request": "true"},
    )
    assert (
        _oob_language_next(both.text, "en") == "/ui?q=Nope&exchange=DEMO-WSE"
    )


@pytest.mark.asyncio
async def test_missing_metrics_are_not_rendered_as_zero(seeded):
    listing = await seeded.get("/ui")
    detail = await seeded.get(_href_for(listing.text, "DEMO_SG_EARLY"))
    parsed = parse_page(detail.text)
    revenue = plain(parsed.cells[("annual", "revenue", "2023-12-31")])
    assets = plain(parsed.cells[("annual", "total_assets", "2023-12-31")])
    ratio = plain(parsed.cells[("annual", "pe_ratio", "2023-12-31")])
    quarterly_income = plain(
        parsed.cells[("quarterly", "net_income", "2026-03-31")]
    )
    quarterly_revenue = plain(
        parsed.cells[("quarterly", "revenue", "2026-03-31")]
    )
    assert revenue == "0 SGD"
    assert assets == "brak danych"
    assert ratio == "brak danych"
    assert quarterly_income == "brak danych"
    assert quarterly_revenue == "100 000 SGD"
    assert ("annual", "revenue", "2026-03-31") not in parsed.cells
    assert ("quarterly", "revenue", "2023-12-31") not in parsed.cells
    assert "31.12.2023" in detail.text
    assert "31.03.2026" in detail.text

    seeded.cookies.set("ui_lang", "en")
    english = await seeded.get(_href_for(listing.text, "DEMO_SG_EARLY"))
    english_cells = parse_page(english.text).cells
    assert (
        plain(english_cells[("quarterly", "revenue", "2026-03-31")])
        == "100,000 SGD"
    )
    assert (
        plain(english_cells[("annual", "total_assets", "2023-12-31")])
        == "no data"
    )
    assert "Dec 31, 2023" in english.text
    assert "Mar 31, 2026" in english.text
    assert "31.12.2023" not in english.text

    seeded.cookies.clear()
    empty = await seeded.get(_href_for(listing.text, "DEMO_PL_EMPTY"))
    empty_page = parse_page(empty.text)
    assert empty_page.cells == {}
    assert "Brak raportów" in empty.text
    assert "PLN" in empty.text
    assert "brak danych" in empty.text


@pytest.mark.asyncio
async def test_company_name_script_is_escaped(client):
    name = "<script>alert(1)</script>"
    company_id = _add_company(client, name=name, ticker="XSSCO")
    listing = await client.get("/ui", params={"q": name})
    assert listing.status_code == 200
    assert name not in listing.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in listing.text
    detail = await client.get(f"/ui/instruments/{company_id}")
    assert name not in detail.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in detail.text
    assert "dane syntetyczne" not in detail.text


@pytest.mark.parametrize(
    "raw,href",
    [
        ("javascript:alert(1)", None),
        ("JavaScript:alert(1)", None),
        (" javascript:alert(1)", None),
        ("data:text/html,<script>alert(1)</script>", None),
        ("https://example.com/demo", "https://example.com/demo"),
        ("http://example.com/demo", "http://example.com/demo"),
        ("HTTP://example.com/demo", "HTTP://example.com/demo"),
        ("  https://example.com/demo  ", "https://example.com/demo"),
    ],
)
@pytest.mark.asyncio
async def test_website_links_follow_the_view_model(client, raw, href):
    company_id = _add_company(client, website=raw)
    page = await client.get(f"/ui/instruments/{company_id}")
    assert page.status_code == 200
    assert_no_dangerous_href(page.text)
    parsed = parse_page(page.text)
    if href is None:
        assert parsed.website["hrefs"] == []
        assert raw.strip() in parsed.website["text"][0]
    else:
        assert parsed.website["hrefs"] == [href]
        assert parsed.website["rels"] == ["noopener noreferrer"]
    if "<script>" in raw:
        assert "<script>alert(1)</script>" not in page.text
        assert "&lt;script&gt;" in page.text


@pytest.mark.parametrize("raw", [None, "", "   "])
@pytest.mark.asyncio
async def test_empty_website_is_no_data(client, raw):
    company_id = _add_company(client, website=raw)
    page = await client.get(f"/ui/instruments/{company_id}")
    parsed = parse_page(page.text)
    assert parsed.website["hrefs"] == []
    assert parsed.website["text"] == ["brak danych"]
    client.cookies.set("ui_lang", "en")
    english = await client.get(f"/ui/instruments/{company_id}")
    assert parse_page(english.text).website["text"] == ["no data"]


@pytest.mark.asyncio
async def test_other_period_and_static_assets(client):
    session = client.app.state.testing_session_local()
    try:
        company = CompanyDB(
            name="Monthly Co",
            ticker="MONTHLY",
            currency="EUR",
            exchange="XETR",
        )
        session.add(company)
        session.commit()
        session.add(
            FinancialMetricsDB(
                company_id=company.id,
                period_end=datetime(2024, 6, 30, tzinfo=timezone.utc),
                period_type="monthly",
                revenue=12,
            )
        )
        session.commit()
        company_id = company.id
    finally:
        session.close()
    page = await client.get(f"/ui/instruments/{company_id}")
    assert "Inne okresy" in page.text
    parsed = parse_page(page.text)
    assert plain(parsed.cells[("other", "revenue", "2024-06-30")]) == "12 EUR"
    style = await client.get("/static/ui.css")
    script = await client.get("/static/vendor/htmx-2.0.10.min.js")
    assert style.status_code == 200
    assert script.status_code == 200
    assert "htmx" in script.text
    assert "cdn.jsdelivr.net" not in script.text
