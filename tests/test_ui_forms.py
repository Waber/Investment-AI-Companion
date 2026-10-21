"""Company and financial-metrics forms under /ui.

Posts use the same Pydantic models as the JSON API. A failed check
renders the form again with a 4xx status. Nothing here calls a
market-data provider.
"""

import re
import unicodedata
from html.parser import HTMLParser
from urllib.parse import urlsplit

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.company import normalize_name
from app.models.database_models import CompanyDB, FinancialMetricsDB
from app.repositories.company_errors import (
    DuplicateIsinError,
    DuplicateTickerError,
)
from app.repositories.company_repository import CompanyRepository
from app.repositories.financial_metrics_repository import (
    FinancialMetricsRepository,
)
from app.ui.catalog import CATALOGS
from app.ui.form_fields import (
    catalog_key_for,
    catalog_key_for_repository_error,
    company_payload,
    metrics_payload,
    normalized_company_name,
    validate_company,
)
from app.ui.origin import OriginRejected
from tests.ui_html import parse_page, plain

_ORIGIN = "http://127.0.0.1"
_SCRIPT = "<script>alert(1)</script>"
_NEW_KEY_PREFIXES = (
    "action.",
    "page.create_",
    "page.edit_",
    "page.delete_",
    "form.",
    "delete.",
    "hint.",
    "error.",
    "field.period_",
    "field.updated_at",
)


class _FormParser(HTMLParser):
    """Ids, labels, and inputs for the accessibility checks."""

    def __init__(self):
        super().__init__()
        self.ids = set()
        self.labels = []
        self.controls = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        element_id = attr.get("id")
        if element_id:
            self.ids.add(element_id)
        if tag == "label" and attr.get("for"):
            self.labels.append(attr["for"])
        if tag in {"input", "textarea", "select"}:
            self.controls.append(attr)


def _parse_form(html):
    parser = _FormParser()
    parser.feed(html)
    return parser


def _assert_labeled(html):
    """Every visible input has a label, and error ids point at real elements.

    A hidden field is not a control the user labels. The language
    switch posts ``next`` that way.
    """
    parsed = _parse_form(html)
    visible = [
        control
        for control in parsed.controls
        if control.get("type") != "hidden"
    ]
    assert visible
    for control in visible:
        element_id = control.get("id")
        assert element_id
        assert element_id in parsed.labels
        described = control.get("aria-describedby", "")
        if control.get("aria-invalid") == "true":
            assert described
        for token in described.split():
            assert token in parsed.ids


def _assert_ui_headers(response):
    policy = response.headers["content-security-policy"]
    assert "default-src 'self'" in policy
    assert "form-action 'self'" in policy
    assert "frame-ancestors 'none'" in policy
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "same-origin"
    assert response.headers["cache-control"] == "no-store"


def _location(response):
    return response.headers["location"].split("?", 1)[0]


def _counts(client):
    session = client.app.state.testing_session_local()
    try:
        return (
            session.query(CompanyDB).count(),
            session.query(FinancialMetricsDB).count(),
        )
    finally:
        session.close()


def _metrics_for(client, company_id):
    session = client.app.state.testing_session_local()
    try:
        rows = (
            session.query(FinancialMetricsDB)
            .filter(FinancialMetricsDB.company_id == company_id)
            .all()
        )
        return [(row.period_type, row.revenue, row.net_income) for row in rows]
    finally:
        session.close()


async def _post(client, path, data=None, *, origin=_ORIGIN, headers=None):
    sent = {}
    if origin is not None:
        sent["origin"] = origin
    if headers:
        sent.update(headers)
    return await client.post(path, data=data or {}, headers=sent)


async def _create(client, **overrides):
    data = {"name": "Form Company", "ticker": "FORMCO", "currency": "usd"}
    data.update(overrides)
    response = await _post(client, "/ui/companies", data)
    assert response.status_code == 303, response.text
    location = _location(response)
    assert location.startswith("/ui/instruments/")
    return int(location.rsplit("/", 1)[-1]), data


def test_new_catalog_strings_are_paired_and_not_signals():
    polish = CATALOGS["pl"]
    english = CATALOGS["en"]
    new_keys = [key for key in polish if key.startswith(_NEW_KEY_PREFIXES)]
    assert new_keys
    for key in new_keys:
        assert key in english
        for text in (polish[key], english[key]):
            folded = text.casefold()
            assert "kupuj" not in folded
            assert "sprzedaj" not in folded
            for word in ("buy", "sell", "hold"):
                assert re.search(rf"\b{word}\b", folded) is None


def test_payload_helpers_blank_optional_fields_and_keep_typed_text():
    payload = company_payload(
        {
            "name": "  Kept  ",
            "ticker": " abc ",
            "exchange": "  ",
            "currency": "",
            "country": "",
            "sector": "",
            "industry": "",
            "website": "",
            "description": "",
        }
    )
    assert payload["name"] == "Kept"
    assert payload["ticker"] == " abc "
    assert payload["exchange"] is None
    assert payload["currency"] is None
    assert payload["website"] is None
    metrics = metrics_payload(
        {"period_end": " 2024-12-31T00:00:00 ", "revenue": "  ", "roe": " 1 "},
        4,
        include_period_type=True,
    )
    assert metrics["company_id"] == 4
    assert metrics["period_end"] == "2024-12-31T00:00:00"
    assert metrics["period_type"] == ""
    assert metrics["revenue"] is None
    assert metrics["roe"] == "1"
    update = metrics_payload(
        {"period_type": "quarterly", "period_end": "2024-01-01T00:00:00"},
        4,
        include_period_type=False,
    )
    assert "period_type" not in update
    assert "company_id" not in update
    assert (
        catalog_key_for("revenue", "float_parsing", "nope") == "error.number"
    )
    assert catalog_key_for("name", "string_type", "nope") == "error.invalid"
    assert (
        catalog_key_for_repository_error(ValueError("no such rule"))
        == "error.constraint"
    )
    # The company sentences are not a lookup table. Both the current
    # repository text and the #75 text fall through to the generic key.
    for message in (
        "Company name or ticker already exists",
        "A company with this ticker already exists",
    ):
        assert (
            catalog_key_for_repository_error(ValueError(message))
            == "error.constraint"
        )
    # Accepted names are stored exactly as normalize_name stores
    # them. A format character beside a letter is kept, including
    # at an edge. A Cc character is rejected by normalize_name:
    # NUL and DEL survive strip(), and the form also rejects them
    # below.
    accepted_names = (
        "  Kept\n",
        "\u00a0Kept\u3000",
        "\u200bKept\u200b",
        "\u200b Kept",
        "A\u200bB",
        "e\u0301",
        "A\u093e",
        "A\u20dd",
        "  भारतीय स्टेट बैंक  ",
        "مصرف الراجحي",
        "همراه\u200cاول",
    )
    for accepted in accepted_names:
        assert normalized_company_name(accepted) == normalize_name(accepted)
    assert normalized_company_name("  Kept\n") == "Kept"
    assert normalized_company_name("\u200bKept\u200b") == "\u200bKept\u200b"
    assert unicodedata.category("\u0301") == "Mn"
    assert unicodedata.category("\u093e") == "Mc"
    assert unicodedata.category("\u20dd") == "Me"
    assert unicodedata.category("\u200c") == "Cf"
    assert normalized_company_name(None) is None
    with pytest.raises(ValueError, match="control"):
        normalize_name("\x00Kept\x7f")
    for invisible in (
        "",
        "   ",
        "\n\t",
        "\u00a0",
        "\u3000",
        "\u200b",
        "\u200b\u00a0",
        "\u200c\u200d\ufeff",
        "\u200b \u3000",
        "\x00",
        "\x00 \x01",
        "\u0301",
        "\u0301\u0308",
        "\u093e",
        "\u20dd",
        "\u093e\u20dd",
        "\u200b\u0301\u200b",
        "\u202a",
        "\u202eKept",
        "Ke\u202ept",
        "\u2066A\u2069",
        "A\u2067B",
        "Ke\x00pt",
        "Na\nme",
        "\x00Kept\x7f",
    ):
        assert normalized_company_name(invisible) is None
        for update in (False, True):
            rejected, field_errors, _key = validate_company(
                {"name": invisible, "ticker": "ABC"}, update=update
            )
            assert rejected is None
            assert field_errors["name"] == "error.required"
    kept = company_payload({"name": " \u200bKept\u200b "})
    assert kept["name"] == normalize_name(" \u200bKept\u200b ")
    assert kept["name"] == "\u200bKept\u200b"
    assert kept["isin"] is None


@pytest.mark.asyncio
async def test_create_edit_and_delete_company_round_trip(client):
    page = await client.get("/ui/companies/new")
    assert page.status_code == 200
    assert "Nowy instrument" in page.text
    assert 'method="post"' in page.text
    assert 'action="/ui/companies"' in page.text
    assert "hx-post" not in page.text
    _assert_labeled(page.text)
    _assert_ui_headers(page)
    listing = await client.get("/ui")
    assert 'href="/ui/companies/new"' in listing.text

    company_id, _data = await _create(
        client,
        name="Round Trip",
        ticker=" round ",
        currency="usd",
        website="https://example.com/demo",
        description="Stored by the form",
        exchange="XNAS",
    )
    detail = await client.get(f"/ui/instruments/{company_id}")
    assert detail.status_code == 200
    assert "ROUND" in detail.text
    assert "Round Trip" in detail.text
    assert "Stored by the form" in detail.text
    assert 'href="https://example.com/demo"' in detail.text
    assert 'rel="noopener noreferrer"' in detail.text
    assert 'href="/ui/companies/%s/edit"' % company_id in detail.text
    assert 'href="/ui/companies/%s/delete"' % company_id in detail.text
    assert 'href="/ui/companies/%s/metrics/new"' % company_id in detail.text

    edit = await client.get(f"/ui/companies/{company_id}/edit")
    assert edit.status_code == 200
    assert "Edycja instrumentu" in edit.text
    assert "Ostatnia zmiana" in edit.text
    assert 'value="ROUND"' in edit.text
    _assert_labeled(edit.text)
    _assert_ui_headers(edit)

    renamed = await _post(
        client,
        f"/ui/companies/{company_id}/edit",
        {
            "name": "Renamed Trip",
            "ticker": "ROUND",
            "currency": "GBp",
            "website": "https://example.com/demo",
            "description": "Stored by the form",
            "exchange": "XNAS",
        },
    )
    assert renamed.status_code == 303
    assert _location(renamed) == f"/ui/instruments/{company_id}"
    after = await client.get(f"/ui/instruments/{company_id}")
    assert "Renamed Trip" in after.text
    assert "GBp" in after.text

    confirm = await client.get(f"/ui/companies/{company_id}/delete")
    assert confirm.status_code == 200
    assert "usuwa także jej wskaźniki finansowe" in confirm.text
    assert "Renamed Trip" in confirm.text
    assert _counts(client) == (1, 0)
    _assert_ui_headers(confirm)

    deleted = await _post(client, f"/ui/companies/{company_id}/delete")
    assert deleted.status_code == 303
    assert _location(deleted) == "/ui"
    assert _counts(client) == (0, 0)
    gone = await client.get(f"/ui/instruments/{company_id}")
    assert gone.status_code == 404


@pytest.mark.asyncio
async def test_company_delete_removes_financial_metrics(client):
    company_id, _data = await _create(client, name="Cascade Co", ticker="CASC")
    created = await _post(
        client,
        f"/ui/companies/{company_id}/metrics",
        {
            "period_end": "2024-12-31T00:00:00",
            "period_type": "annual",
            "revenue": "10",
        },
    )
    assert created.status_code == 303
    assert _counts(client) == (1, 1)
    confirm = await client.get(f"/ui/companies/{company_id}/delete")
    assert "usuwa także jej wskaźniki finansowe" in confirm.text
    assert _counts(client) == (1, 1)
    deleted = await _post(client, f"/ui/companies/{company_id}/delete")
    assert deleted.status_code == 303
    assert _counts(client) == (0, 0)


def _language_next(html, code):
    """Hidden return path on the PL or EN form."""
    match = re.search(
        rf'action="/ui/language/{code}">\s*'
        rf'<input type="hidden" name="next" value="([^"]*)"',
        html,
    )
    assert match is not None
    return match.group(1).replace("&amp;", "&")


def _follow(client, response):
    """GET the redirect target, keeping a query string."""
    parts = urlsplit(response.headers["location"])
    target = parts.path
    if parts.query:
        target = f"{target}?{parts.query}"
    return client.get(target)


@pytest.mark.asyncio
async def test_language_switch_from_a_post_error_opens_the_get_form(client):
    """A 422 is rendered at the POST URL. next names the GET form.

    EN from ``POST /ui/companies`` used to GET that URL and answer
    405. The blank form is ``/ui/companies/new``. A metrics 422 is
    the same kind of miss: the form is ``.../metrics/new``. The GET
    form does not keep what was typed. A normal GET page returns to
    itself.
    """
    create_get = await client.get("/ui/companies/new")
    assert _language_next(create_get.text, "en") == "/ui/companies/new"
    switched = await _post(
        client, "/ui/language/en", {"next": "/ui/companies/new"}
    )
    assert switched.status_code == 303
    landed = await _follow(client, switched)
    assert landed.status_code == 200
    assert "New instrument" in landed.text

    rejected = await _post(
        client,
        "/ui/companies",
        {"name": "Kept Name", "ticker": "", "currency": "US"},
    )
    assert rejected.status_code == 422
    assert "Kept Name" in rejected.text
    target = _language_next(rejected.text, "en")
    assert target == "/ui/companies/new"
    switched = await _post(client, "/ui/language/en", {"next": target})
    assert switched.status_code == 303
    landed = await _follow(client, switched)
    assert landed.status_code == 200
    assert "New instrument" in landed.text
    assert 'action="/ui/companies"' in landed.text
    assert "Kept Name" not in landed.text

    company_id, _data = await _create(client, name="Metric Co", ticker="METNX")
    metrics = await _post(
        client,
        f"/ui/companies/{company_id}/metrics",
        {"period_end": "not-a-date", "period_type": "annual"},
    )
    assert metrics.status_code == 422
    target = _language_next(metrics.text, "pl")
    assert target == f"/ui/companies/{company_id}/metrics/new"
    switched = await _post(client, "/ui/language/pl", {"next": target})
    assert switched.status_code == 303
    landed = await _follow(client, switched)
    assert landed.status_code == 200
    assert "Nowe wskaźniki" in landed.text
    assert f'action="/ui/companies/{company_id}/metrics"' in landed.text


@pytest.mark.asyncio
async def test_validation_errors_rerender_in_both_languages(client):
    before = _counts(client)
    polish = await _post(
        client,
        "/ui/companies",
        {"name": "Kept Name", "ticker": "", "currency": "US"},
    )
    assert polish.status_code == 422
    assert "text/html" in polish.headers["content-type"]
    assert "Kept Name" in polish.text
    assert "Popraw zaznaczone pola." in polish.text
    assert "Ticker musi mieć od 1 do 20 znaków ASCII" in polish.text
    assert "Waluta musi mieć dokładnie trzy litery." in polish.text
    assert 'aria-invalid="true"' in polish.text
    assert 'role="alert"' in polish.text
    assert 'href="#field-ticker"' in polish.text
    _assert_labeled(polish.text)
    _assert_ui_headers(polish)
    assert _counts(client) == before

    client.cookies.set("ui_lang", "en")
    english = await _post(
        client,
        "/ui/companies",
        {
            "name": "Kept Name",
            "ticker": "BAD TICKER",
            "website": "javascript:alert(1)",
            "currency": "U$D",
        },
    )
    assert english.status_code == 422
    assert "Correct the highlighted fields." in english.text
    assert "Ticker must be 1 to 20 ASCII characters" in english.text
    assert "Enter an http:// or https:// address" in english.text
    assert "Currency must be exactly three letters." in english.text
    assert "javascript:alert(1)" in english.text
    assert 'value="BAD TICKER"' in english.text
    _assert_labeled(english.text)
    assert _counts(client) == before


@pytest.mark.asyncio
async def test_script_payload_is_escaped_in_values_and_errors(client):
    company_id, _data = await _create(
        client,
        name=_SCRIPT,
        ticker="XSSCO",
        description="</textarea>" + _SCRIPT,
    )
    detail = await client.get(f"/ui/instruments/{company_id}")
    assert _SCRIPT not in detail.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in detail.text
    assert "dane syntetyczne" not in detail.text

    rejected = await _post(
        client,
        "/ui/companies",
        {
            "name": _SCRIPT,
            "ticker": _SCRIPT,
            "description": "</textarea>" + _SCRIPT,
        },
    )
    assert rejected.status_code == 422
    assert _SCRIPT not in rejected.text
    assert "</textarea><script>" not in rejected.text
    assert "&lt;script&gt;" in rejected.text
    assert "Ticker musi mieć od 1 do 20 znaków ASCII" in rejected.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "N" * 256),
        ("description", "D" * 5001),
        ("ticker", "ĄBC"),
        ("ticker", "ABC\n"),
        ("ticker", "   "),
        ("website", "not a url"),
        ("currency", "USDD"),
    ],
)
async def test_invalid_company_text_is_4xx_not_500(client, field, value):
    data = {"name": "Ok Name", "ticker": "OKNAME", "currency": "USD"}
    data[field] = value
    response = await _post(client, "/ui/companies", data)
    assert response.status_code in {400, 422}
    assert "text/html" in response.headers["content-type"]
    assert not response.text.lstrip().startswith("{")
    assert _counts(client) == (0, 0)


@pytest.mark.asyncio
async def test_duplicate_name_or_ticker_is_an_inline_400(client):
    await _create(client, name="First Co", ticker="FIRST")
    same_ticker = await _post(
        client,
        "/ui/companies",
        {"name": "Other Co", "ticker": "FIRST"},
    )
    assert same_ticker.status_code == 400
    assert "Istnieje już spółka o tym tickerze." in same_ticker.text
    assert 'value="Other Co"' in same_ticker.text
    assert 'aria-invalid="true"' in same_ticker.text
    _assert_labeled(same_ticker.text)
    assert _counts(client) == (1, 0)

    same_name = await _post(
        client,
        "/ui/companies",
        {"name": "Second Co", "ticker": "SECOND"},
    )
    assert same_name.status_code == 303
    second_id = int(_location(same_name).rsplit("/", 1)[-1])
    shared_name = await _post(
        client,
        f"/ui/companies/{second_id}/edit",
        {"name": "First Co", "ticker": "SECOND"},
    )
    assert shared_name.status_code == 303
    assert _location(shared_name) == f"/ui/instruments/{second_id}"
    session = client.app.state.testing_session_local()
    try:
        stored = session.get(CompanyDB, second_id)
        assert stored.name == "First Co"
        assert stored.ticker == "SECOND"
    finally:
        session.close()
    ticker_conflict = await _post(
        client,
        f"/ui/companies/{second_id}/edit",
        {"name": "Second Co", "ticker": "first"},
    )
    assert ticker_conflict.status_code == 400
    assert "Istnieje już spółka o tym tickerze." in ticker_conflict.text
    assert _counts(client) == (2, 0)


_DUPLICATE_MESSAGES = (
    "Company name or ticker already exists",
    "A company with this ticker already exists",
)
_TICKER_PL = "Istnieje już spółka o tym tickerze."
_TICKER_EN = "A company with this ticker already exists."
_ISIN_PL = "Istnieje już spółka o tym numerze ISIN."
_ISIN_EN = "A company with this ISIN already exists."
_CONSTRAINT_PL = "naruszają regułę unikalności"
_APPLE_ISIN = "US0378331005"
_OTHER_ISIN = "DE0007164600"


def _stored_column(client, company_id, column):
    session = client.app.state.testing_session_local()
    try:
        return getattr(session.get(CompanyDB, company_id), column)
    finally:
        session.close()


def _assert_field_message(html, field, message):
    """The sentence is the field error, and that input is invalid."""
    assert message in html
    assert f'id="field-{field}-error"' in html
    assert f'href="#field-{field}"' in html
    parsed = _parse_form(html)
    invalid = [
        control.get("name")
        for control in parsed.controls
        if control.get("aria-invalid") == "true"
    ]
    assert invalid == [field]


def _dd_text(html, code):
    """Visible text of one ``<dd data-field>``, with nested tags removed.

    The detail page marks each value that way. A missing-data
    ``span`` would otherwise hide the sentence inside the markup.
    """
    match = re.search(
        rf'<dd data-field="{re.escape(code)}">(.*?)</dd>',
        html,
        flags=re.DOTALL,
    )
    assert match is not None, code
    return re.sub(r"<[^>]+>", "", match.group(1)).strip()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("language", "isin", "shown"),
    [
        ("pl", _APPLE_ISIN, _APPLE_ISIN),
        ("en", _APPLE_ISIN, _APPLE_ISIN),
        ("pl", None, CATALOGS["pl"]["missing"]),
        ("en", None, CATALOGS["en"]["missing"]),
    ],
)
async def test_instrument_detail_shows_the_company_isin(
    client, language, isin, shown
):
    """The detail page lists the ISIN after the ticker.

    The label is the catalog string for that language. A company
    with no ISIN uses the same missing-data sentence as the other
    empty fields.
    """
    client.cookies.set("ui_lang", language)
    fields = {"name": "Shown Co", "ticker": "SHOWN"}
    if isin is not None:
        fields["isin"] = isin
    company_id, _data = await _create(client, **fields)
    if isin is None:
        assert _stored_column(client, company_id, "isin") is None
    detail = await client.get(f"/ui/instruments/{company_id}")
    assert detail.status_code == 200
    html = detail.text
    ticker_at = html.index('data-field="ticker"')
    isin_at = html.index('data-field="isin"')
    type_at = html.index('data-field="type"')
    assert ticker_at < isin_at < type_at
    assert _dd_text(html, "isin") == shown
    label = CATALOGS[language]["field.isin"]
    assert f">{label}</dt>" in html
    isin_markup = re.search(
        r'data-field="isin">(.*?)</dd>',
        html,
        flags=re.DOTALL,
    ).group(1)
    if isin is None:
        assert 'class="missing"' in isin_markup
    else:
        assert CATALOGS[language]["missing"] not in isin_markup


@pytest.mark.asyncio
async def test_create_redirect_lands_on_a_detail_page_with_the_isin(client):
    """A successful create sends the browser to the detail page.

    That page is where the saved ISIN has to be visible. The test
    follows the 303 instead of trusting the form response.
    """
    response = await _post(
        client,
        "/ui/companies",
        {
            "name": "Apple",
            "ticker": "AAPL",
            "isin": _APPLE_ISIN,
            "currency": "usd",
        },
    )
    assert response.status_code == 303
    location = _location(response)
    assert location.startswith("/ui/instruments/")
    detail = await client.get(location)
    assert detail.status_code == 200
    assert _dd_text(detail.text, "isin") == _APPLE_ISIN
    assert f">{CATALOGS['pl']['field.isin']}</dt>" in detail.text


@pytest.mark.asyncio
@pytest.mark.parametrize("message", _DUPLICATE_MESSAGES)
async def test_plain_value_error_is_not_read_as_a_duplicate_code(
    client, monkeypatch, message
):
    """The sentence is not a code, even when the ticker row exists.

    Create and update used to look the ticker up. A plain
    ``ValueError`` now stays the generic constraint page. The
    repository text is not copied into the HTML.
    """
    await _create(client, name="First Co", ticker="FIRST")

    def reject_create(self, company):
        raise ValueError(message)

    monkeypatch.setattr(CompanyRepository, "create", reject_create)
    created = await _post(
        client,
        "/ui/companies",
        {"name": "Other Co", "ticker": " first "},
    )
    assert created.status_code == 400
    assert _TICKER_PL not in created.text
    assert message not in created.text
    assert _CONSTRAINT_PL in created.text
    assert _counts(client) == (1, 0)

    monkeypatch.undo()
    second_id, _data = await _create(client, name="Second Co", ticker="SECOND")

    def reject_update(self, company_id, company_update):
        raise ValueError(message)

    monkeypatch.setattr(CompanyRepository, "update", reject_update)
    updated = await _post(
        client,
        f"/ui/companies/{second_id}/edit",
        {"name": "Second Co", "ticker": "first"},
    )
    assert updated.status_code == 400
    assert _TICKER_PL not in updated.text
    assert message not in updated.text
    assert _CONSTRAINT_PL in updated.text
    assert _counts(client) == (2, 0)


@pytest.mark.asyncio
async def test_company_create_integrity_error_is_not_matched_by_text(
    client, monkeypatch
):
    """A raw IntegrityError is the generic page, not the ticker field.

    The repository turns a unique-index failure into
    ``DuplicateTickerError`` before the form sees it. A driver
    sentence that names the ticker column is not read, and the form
    does not look the ticker up.
    """
    await _create(client, name="First Co", ticker="FIRST")

    def reject(self, company):
        raise IntegrityError(
            "INSERT INTO companies",
            {"ticker": company.ticker},
            Exception("UNIQUE constraint failed: companies.ticker"),
        )

    monkeypatch.setattr(CompanyRepository, "create", reject)
    response = await _post(
        client,
        "/ui/companies",
        {"name": "Other Co", "ticker": "FIRST"},
    )
    assert response.status_code == 400
    assert _TICKER_PL not in response.text
    assert "UNIQUE constraint failed" not in response.text
    assert _CONSTRAINT_PL in response.text
    assert _counts(client) == (1, 0)


@pytest.mark.asyncio
async def test_same_message_without_a_stored_ticker_is_not_a_duplicate(
    client, monkeypatch
):
    """The duplicate sentence alone does not select the ticker error."""

    def reject_create(self, company):
        raise ValueError("A company with this ticker already exists")

    monkeypatch.setattr(CompanyRepository, "create", reject_create)
    response = await _post(
        client,
        "/ui/companies",
        {"name": "Lonely Co", "ticker": "LONE"},
    )
    assert response.status_code == 400
    assert _TICKER_PL not in response.text
    assert _CONSTRAINT_PL in response.text
    assert _counts(client) == (0, 0)


@pytest.mark.asyncio
async def test_duplicate_ticker_and_isin_field_errors_in_both_languages(
    client,
):
    """A real collision marks that field, in Polish and in English.

    The form posts the ISIN. The repository raises
    ``DuplicateTickerError`` or ``DuplicateIsinError``. The page
    uses ``code``, not the English sentence, and not a second query.
    """
    await _create(
        client,
        name="First Co",
        ticker="FIRST",
        isin=_APPLE_ISIN,
    )
    polish_ticker = await _post(
        client,
        "/ui/companies",
        {"name": "Other Co", "ticker": "first", "isin": _OTHER_ISIN},
    )
    assert polish_ticker.status_code == 400
    _assert_field_message(polish_ticker.text, "ticker", _TICKER_PL)
    assert _ISIN_PL not in polish_ticker.text
    assert _counts(client) == (1, 0)

    client.cookies.set("ui_lang", "en")
    english_ticker = await _post(
        client,
        "/ui/companies",
        {"name": "Other Co", "ticker": "FIRST", "isin": _OTHER_ISIN},
    )
    assert english_ticker.status_code == 400
    _assert_field_message(english_ticker.text, "ticker", _TICKER_EN)
    assert _TICKER_PL not in english_ticker.text
    client.cookies.clear()

    second_id, _data = await _create(
        client,
        name="Second Co",
        ticker="SECOND",
        isin=_OTHER_ISIN,
    )
    polish_isin = await _post(
        client,
        "/ui/companies",
        {"name": "Third Co", "ticker": "THIRD", "isin": "us0378331005"},
    )
    assert polish_isin.status_code == 400
    _assert_field_message(polish_isin.text, "isin", _ISIN_PL)
    assert _TICKER_PL not in polish_isin.text
    assert 'value="us0378331005"' in polish_isin.text
    assert _counts(client) == (2, 0)

    client.cookies.set("ui_lang", "en")
    english_isin = await _post(
        client,
        f"/ui/companies/{second_id}/edit",
        {
            "name": "Second Co",
            "ticker": "SECOND",
            "isin": _APPLE_ISIN,
        },
    )
    assert english_isin.status_code == 400
    _assert_field_message(english_isin.text, "isin", _ISIN_EN)
    assert _stored_column(client, second_id, "isin") == _OTHER_ISIN
    client.cookies.clear()


@pytest.mark.asyncio
async def test_duplicate_of_both_ticker_and_isin_marks_only_the_ticker(
    client,
):
    """Both collisions mark the ticker, and the ISIN input stays valid.

    The repository checks the ticker first and raises
    ``DuplicateTickerError``. It does not also raise
    ``DuplicateIsinError``, so the page has ``field-ticker-error``
    and ``aria-invalid`` on that input only.
    """
    await _create(
        client,
        name="First Co",
        ticker="FIRST",
        isin=_APPLE_ISIN,
    )
    response = await _post(
        client,
        "/ui/companies",
        {
            "name": "Other Co",
            "ticker": "first",
            "isin": _APPLE_ISIN,
        },
    )
    assert response.status_code == 400
    _assert_field_message(response.text, "ticker", _TICKER_PL)
    assert 'id="field-ticker-error"' in response.text
    assert 'id="field-isin-error"' not in response.text
    assert _ISIN_PL not in response.text
    parsed = _parse_form(response.text)
    isin_invalid = [
        control
        for control in parsed.controls
        if control.get("name") == "isin"
        and control.get("aria-invalid") == "true"
    ]
    assert isin_invalid == []
    assert _counts(client) == (1, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_type", "field", "message"),
    [
        (DuplicateTickerError, "ticker", _TICKER_PL),
        (DuplicateIsinError, "isin", _ISIN_PL),
    ],
)
async def test_duplicate_code_without_a_stored_row_is_that_field(
    client, monkeypatch, error_type, field, message
):
    """The code wins when the other row is not visible yet.

    A race can raise the duplicate exception after this session has
    looked and found nothing. The page still marks the field. The
    exception text is not shown.
    """

    def reject_create(self, company):
        raise error_type()

    monkeypatch.setattr(CompanyRepository, "create", reject_create)
    created = await _post(
        client,
        "/ui/companies",
        {"name": "Race Co", "ticker": "RACE", "isin": _APPLE_ISIN},
    )
    assert created.status_code == 400
    _assert_field_message(created.text, field, message)
    assert "already exists" not in created.text
    assert _counts(client) == (0, 0)

    monkeypatch.undo()
    company_id, _data = await _create(client, name="Kept Co", ticker="KEPTCO")

    def reject_update(self, company_id, company_update):
        raise error_type()

    monkeypatch.setattr(CompanyRepository, "update", reject_update)
    updated = await _post(
        client,
        f"/ui/companies/{company_id}/edit",
        {"name": "Kept Co", "ticker": "KEPTCO", "isin": _OTHER_ISIN},
    )
    assert updated.status_code == 400
    _assert_field_message(updated.text, field, message)
    assert "already exists" not in updated.text
    assert _counts(client) == (1, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "field", "message"),
    [
        ("duplicate_ticker", "ticker", _TICKER_PL),
        ("duplicate_isin", "isin", _ISIN_PL),
    ],
)
async def test_duplicate_code_attribute_maps_without_the_class(
    client, monkeypatch, code, field, message
):
    """``code`` selects the field. The class and the text do not."""

    class Coded(ValueError):
        def __init__(self):
            super().__init__("already exists in the driver text")
            self.code = code

    def reject_create(self, company):
        raise Coded()

    monkeypatch.setattr(CompanyRepository, "create", reject_create)
    response = await _post(
        client,
        "/ui/companies",
        {"name": "Coded Co", "ticker": "CODED", "isin": _APPLE_ISIN},
    )
    assert response.status_code == 400
    _assert_field_message(response.text, field, message)
    assert "driver text" not in response.text
    assert _counts(client) == (0, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name",
    [
        "",
        "   ",
        "\n\t",
        "\u00a0",
        "\u3000",
        "\u200b",
        "\u200c\u200d\ufeff",
        "\u00a0\u200b\u3000",
    ],
)
async def test_blank_company_name_is_422_in_both_languages(client, name):
    polish = await _post(
        client,
        "/ui/companies",
        {"name": name, "ticker": "BLANK", "currency": "USD"},
    )
    assert polish.status_code == 422
    assert "To pole jest wymagane." in polish.text
    assert 'id="field-name"' in polish.text
    assert 'aria-invalid="true"' in polish.text
    assert 'href="#field-name"' in polish.text
    assert 'value="BLANK"' in polish.text
    assert _counts(client) == (0, 0)
    client.cookies.set("ui_lang", "en")
    english = await _post(
        client,
        "/ui/companies",
        {"name": name, "ticker": "BLANK", "currency": "USD"},
    )
    assert english.status_code == 422
    assert "This field is required." in english.text
    client.cookies.clear()
    company_id, _data = await _create(client, name="Named Co", ticker="NAMED")
    cleared = await _post(
        client,
        f"/ui/companies/{company_id}/edit",
        {"name": name, "ticker": "NAMED"},
    )
    assert cleared.status_code == 422
    assert "To pole jest wymagane." in cleared.text
    detail = await client.get(f"/ui/instruments/{company_id}")
    assert "Named Co" in detail.text


@pytest.mark.asyncio
async def test_stored_name_matches_normalize_name(client):
    """Whitespace ends are stripped. A format character beside a letter stays.

    ``normalize_name`` does not peel Cf or Cc off the ends. The form
    stores that same string. A NUL between two letters is a 422,
    covered below.
    """
    raw = "\n  Kept Name\u3000"
    assert normalize_name(raw) == "Kept Name"
    company_id, _data = await _create(client, name=raw, ticker="KEPTNM")
    assert _stored_column(client, company_id, "name") == "Kept Name"
    detail = await client.get(f"/ui/instruments/{company_id}")
    assert "Kept Name" in detail.text
    edited = "\u200bEdited Name\u200b"
    assert normalize_name(edited) == edited
    updated = await _post(
        client,
        f"/ui/companies/{company_id}/edit",
        {"name": edited, "ticker": "KEPTNM"},
    )
    assert updated.status_code == 303
    assert _stored_column(client, company_id, "name") == edited


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw", "ticker"),
    [
        ("  भारतीय स्टेट बैंक  ", "HINDI"),
        ("مصرف الراجحي", "ARABIC"),
        ("  همراه\u200cاول  ", "PERSIAN"),
    ],
)
async def test_names_in_other_scripts_match_normalize_name(
    client, raw, ticker
):
    """Hindi, Arabic, and Persian with ZWNJ are stored like the model.

    ZWNJ (U+200C) is a format character. The form keeps it between
    the Persian letters instead of stripping it or rejecting the name.
    """
    expected = normalize_name(raw)
    assert normalized_company_name(raw) == expected
    assert expected
    company_id, _data = await _create(client, name=raw, ticker=ticker)
    assert _stored_column(client, company_id, "name") == expected
    detail = await client.get(f"/ui/instruments/{company_id}")
    assert expected in detail.text


@pytest.mark.asyncio
async def test_interior_control_or_only_combining_marks_is_422(client):
    """A control, a bidi mark, or only marks, is 422.

    Create and edit share ``normalized_company_name``. The row is
    not written. The message is the localized required-field sentence.
    A bidi override at the end is not stripped down to the letters.
    Mn, Mc, and Me with no base letter are rejected. A letter with
    one of those marks is stored.
    """
    for name in (
        "Ke\x00pt",
        "\x00Kept\x7f",
        "Na\nme",
        "\u0301",
        "\u0301\u0308",
        "\u093e",
        "\u20dd",
        "\u202eKept",
        "Ke\u202ept",
        "\u2066Name",
    ):
        response = await _post(
            client,
            "/ui/companies",
            {"name": name, "ticker": "BADNM", "currency": "USD"},
        )
        assert response.status_code == 422, repr(name)
        assert "To pole jest wymagane." in response.text
        assert _counts(client) == (0, 0)
    company_id, _data = await _create(
        client, name="A\u093e\u20dd", ticker="MARKA"
    )
    session = client.app.state.testing_session_local()
    try:
        stored = session.get(CompanyDB, company_id).name
    finally:
        session.close()
    assert stored == "A\u093e\u20dd"
    client.cookies.set("ui_lang", "en")
    edited = await _post(
        client,
        f"/ui/companies/{company_id}/edit",
        {"name": "Na\x01me", "ticker": "MARKA"},
    )
    assert edited.status_code == 422
    assert "This field is required." in edited.text
    detail = await client.get(f"/ui/instruments/{company_id}")
    assert "A\u093e\u20dd" in detail.text


@pytest.mark.asyncio
async def test_edge_controls_are_422_on_edit(client):
    """NUL or DEL at either end is 422 when the name is edited.

    ``normalize_name`` rejects those controls. ``strip`` removes
    whitespace only, so the characters would otherwise be stored.
    The stored name stays unchanged.
    """
    company_id, _data = await _create(
        client, name="Kept Name", ticker="EDGECC"
    )
    edited = await _post(
        client,
        f"/ui/companies/{company_id}/edit",
        {"name": "\x00Kept\x7f", "ticker": "EDGECC"},
    )
    assert edited.status_code == 422
    assert "To pole jest wymagane." in edited.text
    assert 'id="field-name-error"' in edited.text
    assert _stored_column(client, company_id, "name") == "Kept Name"
    assert _counts(client) == (1, 0)


@pytest.mark.asyncio
async def test_editing_the_description_drops_the_demo_badge(client):
    """The synthetic badge is the [IAC-DEMO- prefix, not a column.

    Saving a description that does not start with that prefix removes
    the badge. That is today's read model.
    """
    company_id, _data = await _create(
        client,
        name="Demo Co",
        ticker="DEMOCO",
        description="[IAC-DEMO-V1] seeded text",
    )
    detail = await client.get(f"/ui/instruments/{company_id}")
    assert detail.status_code == 200
    assert "dane syntetyczne" in detail.text
    assert "[IAC-DEMO-V1]" in detail.text
    updated = await _post(
        client,
        f"/ui/companies/{company_id}/edit",
        {
            "name": "Demo Co",
            "ticker": "DEMOCO",
            "description": "seeded text",
        },
    )
    assert updated.status_code == 303
    after = await client.get(f"/ui/instruments/{company_id}")
    assert "dane syntetyczne" not in after.text
    assert "[IAC-DEMO-V1]" not in after.text
    assert "seeded text" in after.text


@pytest.mark.asyncio
async def test_metrics_create_edit_and_delete(client):
    company_id, _data = await _create(client, name="Metric Co", ticker="METCO")
    form = await client.get(f"/ui/companies/{company_id}/metrics/new")
    assert form.status_code == 200
    assert "Nowe wskaźniki" in form.text
    assert "Czas bez strefy jest zapisywany jako UTC" in form.text
    assert 'name="period_type"' in form.text
    _assert_labeled(form.text)
    _assert_ui_headers(form)

    created = await _post(
        client,
        f"/ui/companies/{company_id}/metrics",
        {
            "period_end": "2024-12-31T00:00:00",
            "period_type": "annual",
            "revenue": "1000",
            "net_income": "0",
            "pe_ratio": "",
        },
    )
    assert created.status_code == 303
    detail = await client.get(f"/ui/instruments/{company_id}")
    revenue = plain(
        parse_page(detail.text).cells[("annual", "revenue", "2024-12-31")]
    )
    income = plain(
        parse_page(detail.text).cells[("annual", "net_income", "2024-12-31")]
    )
    assert revenue == "1 000 USD"
    assert income == "0 USD"
    assert 'data-period-type="annual"' in detail.text
    assert "/metrics/" in detail.text
    assert "Edytuj wskaźniki" in detail.text

    session = client.app.state.testing_session_local()
    try:
        metrics_id = (
            session.query(FinancialMetricsDB)
            .filter(FinancialMetricsDB.company_id == company_id)
            .one()
            .id
        )
    finally:
        session.close()

    edit = await client.get(
        f"/ui/companies/{company_id}/metrics/{metrics_id}/edit"
    )
    assert edit.status_code == 200
    assert "Ostatnia zmiana" in edit.text
    assert "annual" in edit.text
    assert 'name="period_type"' not in edit.text
    assert 'value="2024-12-31T00:00:00"' in edit.text
    assert 'value="1000"' in edit.text
    assert 'value="0"' in edit.text
    _assert_labeled(edit.text)

    client.cookies.set("ui_lang", "en")
    english_edit = await client.get(
        f"/ui/companies/{company_id}/metrics/{metrics_id}/edit"
    )
    assert "Last edit" in english_edit.text
    assert "The period type stays as it was" in english_edit.text
    client.cookies.clear()

    updated = await _post(
        client,
        f"/ui/companies/{company_id}/metrics/{metrics_id}/edit",
        {
            "period_end": "2024-12-31T00:00:00",
            "period_type": "quarterly",
            "revenue": "",
            "net_income": "5",
        },
    )
    assert updated.status_code == 303
    stored = _metrics_for(client, company_id)
    assert stored == [("annual", None, 5.0)]
    detail = await client.get(f"/ui/instruments/{company_id}")
    assert 'data-period-type="annual"' in detail.text
    assert "brak danych" in detail.text

    confirm = await client.get(
        f"/ui/companies/{company_id}/metrics/{metrics_id}/delete"
    )
    assert "nie usuwa spółki" in confirm.text
    assert "31.12.2024" in confirm.text
    assert _counts(client) == (1, 1)
    removed = await _post(
        client,
        f"/ui/companies/{company_id}/metrics/{metrics_id}/delete",
    )
    assert removed.status_code == 303
    assert _location(removed) == f"/ui/instruments/{company_id}"
    assert _counts(client) == (1, 0)
    still = await client.get(f"/ui/instruments/{company_id}")
    assert still.status_code == 200
    assert "Metric Co" in still.text


@pytest.mark.asyncio
async def test_duplicate_periods_follow_the_repository_rule(client):
    company_id, _data = await _create(client, name="Period Co", ticker="PERCO")
    first = {
        "period_end": "2024-12-31T00:00:00",
        "period_type": "annual",
        "revenue": "1",
    }
    created = await _post(client, f"/ui/companies/{company_id}/metrics", first)
    assert created.status_code == 303
    duplicate = await _post(
        client, f"/ui/companies/{company_id}/metrics", first
    )
    assert duplicate.status_code == 400
    assert "końca okresu i typu okresu już istnieją" in duplicate.text
    assert 'value="2024-12-31T00:00:00"' in duplicate.text
    assert _counts(client) == (1, 1)

    client.cookies.set("ui_lang", "en")
    english = await _post(
        client,
        f"/ui/companies/{company_id}/metrics",
        {
            "period_end": "2024-12-31T02:00:00+02:00",
            "period_type": "annual",
            "revenue": "2",
        },
    )
    assert english.status_code == 400
    assert "period end, and period type already exist" in english.text
    assert _counts(client) == (1, 1)
    client.cookies.clear()

    other = await _post(
        client,
        f"/ui/companies/{company_id}/metrics",
        {
            "period_end": "2023-12-31T00:00:00",
            "period_type": "annual",
            "revenue": "3",
        },
    )
    assert other.status_code == 303
    session = client.app.state.testing_session_local()
    try:
        older = (
            session.query(FinancialMetricsDB)
            .filter(FinancialMetricsDB.revenue == 3)
            .one()
        )
        older_id = older.id
    finally:
        session.close()
    moved = await _post(
        client,
        f"/ui/companies/{company_id}/metrics/{older_id}/edit",
        {"period_end": "2024-12-31T00:00:00Z", "revenue": "3"},
    )
    assert moved.status_code == 400
    assert "już istnieją" in moved.text
    assert _counts(client) == (1, 2)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "revenue",
    [
        "nan",
        "NaN",
        "inf",
        "+inf",
        "-inf",
        "Infinity",
        "-Infinity",
        "1e309",
        "abc",
        "1,000",
        "١",
        "²",
        "1.2.3",
        "9" * 5000,
    ],
)
async def test_bad_numbers_are_422_not_500(client, revenue):
    company_id, _data = await _create(client, name="Number Co", ticker="NUMCO")
    response = await _post(
        client,
        f"/ui/companies/{company_id}/metrics",
        {
            "period_end": "2024-06-30T00:00:00",
            "period_type": "quarterly",
            "revenue": revenue,
        },
    )
    assert response.status_code == 422
    assert "text/html" in response.headers["content-type"]
    assert "Podaj skończoną liczbę" in response.text
    assert not response.text.lstrip().startswith("{")
    assert _SCRIPT not in response.text
    assert _counts(client) == (1, 0)


@pytest.mark.asyncio
async def test_period_rules_match_the_models(client):
    company_id, _data = await _create(client, name="Rule Co", ticker="RULCO")
    empty_end = await _post(
        client,
        f"/ui/companies/{company_id}/metrics",
        {"period_end": "", "period_type": "annual", "revenue": "1"},
    )
    assert empty_end.status_code == 422
    assert "Podaj datę i czas" in empty_end.text

    too_long = await _post(
        client,
        f"/ui/companies/{company_id}/metrics",
        {
            "period_end": "2024-06-30T00:00:00",
            "period_type": "q" * 21,
            "revenue": "1",
        },
    )
    assert too_long.status_code == 422
    assert "Za długa wartość." in too_long.text

    digits = await _post(
        client,
        f"/ui/companies/{company_id}/metrics",
        {
            "period_end": "2024-06-30T00:00:0١",
            "period_type": "annual",
        },
    )
    assert digits.status_code == 422

    other = await _post(
        client,
        f"/ui/companies/{company_id}/metrics",
        {
            "period_end": "2024-06-30T00:00:00",
            "period_type": "m" * 20,
            "revenue": "4",
        },
    )
    assert other.status_code == 303
    detail = await client.get(f"/ui/instruments/{company_id}")
    assert "Inne okresy" in detail.text
    assert _counts(client) == (1, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/ui/companies/abc/edit",
        "/ui/companies/01/edit",
        "/ui/companies/\u0661/delete",
        "/ui/companies/" + ("1" * 23) + "/edit",
        "/ui/companies/" + str(2**63) + "/metrics/new",
        "/ui/companies/999999/edit",
        "/ui/companies/999999/metrics/new",
    ],
)
async def test_bad_company_ids_are_the_html_404(client, path):
    page = await client.get(path)
    assert page.status_code == 404
    assert "text/html" in page.headers["content-type"]
    assert "Nie znaleziono instrumentu" in page.text
    assert not page.text.lstrip().startswith("{")
    _assert_ui_headers(page)


@pytest.mark.asyncio
async def test_bad_metrics_ids_and_cross_company_links_are_404(client):
    first, _data = await _create(client, name="Owner Co", ticker="OWNER")
    second, _data = await _create(client, name="Other Co", ticker="OTHER")
    created = await _post(
        client,
        f"/ui/companies/{first}/metrics",
        {
            "period_end": "2024-12-31T00:00:00",
            "period_type": "annual",
            "revenue": "8",
        },
    )
    assert created.status_code == 303
    session = client.app.state.testing_session_local()
    try:
        metrics_id = session.query(FinancialMetricsDB).one().id
    finally:
        session.close()
    for path in (
        f"/ui/companies/{first}/metrics/abc/edit",
        f"/ui/companies/{first}/metrics/01/delete",
        f"/ui/companies/{first}/metrics/\u0661/edit",
        f"/ui/companies/{first}/metrics/{'1' * 23}/edit",
        f"/ui/companies/{first}/metrics/999999/edit",
        f"/ui/companies/{second}/metrics/{metrics_id}/edit",
        f"/ui/companies/{second}/metrics/{metrics_id}/delete",
    ):
        page = await client.get(path)
        assert page.status_code == 404, path
        assert "Nie znaleziono instrumentu" in page.text
    posted = await _post(
        client,
        f"/ui/companies/{second}/metrics/{metrics_id}/edit",
        {"period_end": "2020-01-01T00:00:00", "revenue": "1"},
    )
    assert posted.status_code == 404
    assert _metrics_for(client, first) == [("annual", 8.0, None)]


def _stored_instrument_type(client, company_id):
    session = client.app.state.testing_session_local()
    try:
        row = session.query(CompanyDB).filter(CompanyDB.id == company_id).one()
        return row.instrument_type
    finally:
        session.close()


def _type_text(html):
    """The detail page's type cell, without the surrounding tags."""
    match = re.search(r'data-field="type">\s*([^<]+)', html)
    assert match is not None
    return match.group(1).strip()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "language, code, label",
    [
        ("pl", "STOCK", "akcja"),
        ("en", "STOCK", "stock"),
        ("pl", "ETF", "ETF"),
        ("en", "ETF", "ETF"),
        ("pl", "ETC", "ETC"),
        ("en", "ETC", "ETC"),
    ],
)
async def test_instrument_type_round_trip_in_both_languages(
    client, language, code, label
):
    """Create and edit post the enum. The pages show the catalog word."""
    if language == "en":
        client.cookies.set("ui_lang", "en")
    type_label = "Typ" if language == "pl" else "Type"
    form = await client.get("/ui/companies/new")
    assert form.status_code == 200
    assert f'<label for="field-instrument_type">{type_label}</label>' in (
        form.text
    )
    assert '<option value="STOCK" selected>' in form.text
    if code == "STOCK":
        assert f'<option value="STOCK" selected>{label}</option>' in form.text
    else:
        assert f'<option value="{code}">{label}</option>' in form.text
    _assert_labeled(form.text)

    company_id, _data = await _create(
        client,
        name="Typed Co",
        ticker=f"TYP{code}",
        instrument_type=code,
    )
    assert _stored_instrument_type(client, company_id) == code
    detail = await client.get(f"/ui/instruments/{company_id}")
    assert detail.status_code == 200
    assert _type_text(detail.text) == label
    listing = await client.get("/ui")
    assert f'data-ticker="TYP{code}"' in listing.text
    assert label in listing.text
    assert f'<option value="{code.lower()}">{label}</option>' in listing.text

    edit = await client.get(f"/ui/companies/{company_id}/edit")
    assert edit.status_code == 200
    assert f'<option value="{code}" selected>{label}</option>' in edit.text
    assert f'<label for="field-instrument_type">{type_label}</label>' in (
        edit.text
    )
    _assert_labeled(edit.text)
    renamed = await _post(
        client,
        f"/ui/companies/{company_id}/edit",
        {
            "name": "Typed Co renamed",
            "ticker": f"TYP{code}",
            "instrument_type": code,
        },
    )
    assert renamed.status_code == 303
    after = await client.get(f"/ui/instruments/{company_id}")
    assert "Typed Co renamed" in after.text
    assert _type_text(after.text) == label
    assert _stored_instrument_type(client, company_id) == code


@pytest.mark.asyncio
async def test_create_without_a_type_stores_the_model_default(client):
    """A blank type is omitted, so CompanyCreate stores STOCK."""
    form = await client.get("/ui/companies/new")
    assert '<option value="STOCK" selected>akcja</option>' in form.text
    company_id, _data = await _create(
        client, name="Default Type", ticker="DEFTYP"
    )
    assert _stored_instrument_type(client, company_id) == "STOCK"
    detail = await client.get(f"/ui/instruments/{company_id}")
    assert _type_text(detail.text) == "akcja"
    client.cookies.set("ui_lang", "en")
    english = await client.get(f"/ui/instruments/{company_id}")
    assert _type_text(english.text) == "stock"


@pytest.mark.asyncio
async def test_edit_can_change_the_stored_type(client):
    company_id, _data = await _create(
        client, name="Switch Type", ticker="SWITCH", instrument_type="ETF"
    )
    edit = await client.get(f"/ui/companies/{company_id}/edit")
    assert '<option value="ETF" selected>ETF</option>' in edit.text
    saved = await _post(
        client,
        f"/ui/companies/{company_id}/edit",
        {
            "name": "Switch Type",
            "ticker": "SWITCH",
            "instrument_type": "ETC",
        },
    )
    assert saved.status_code == 303
    assert _stored_instrument_type(client, company_id) == "ETC"
    detail = await client.get(f"/ui/instruments/{company_id}")
    assert _type_text(detail.text) == "ETC"
    kept = await _post(
        client,
        f"/ui/companies/{company_id}/edit",
        {"name": "Switch Type kept", "ticker": "SWITCH"},
    )
    assert kept.status_code == 303
    assert _stored_instrument_type(client, company_id) == "ETC"


@pytest.mark.asyncio
async def test_edit_error_without_a_type_does_not_select_stock(client):
    """A failed edit that omits the type must not offer STOCK next.

    The select treats a blank value as the create default. Resubmitting
    that page would store STOCK over an ETF. The 422 page has to show
    the type already on the row, and the following save has to keep it.
    """
    company_id, _data = await _create(
        client, name="Kept ETF", ticker="KEPTETF", instrument_type="ETF"
    )
    failed = await _post(
        client,
        f"/ui/companies/{company_id}/edit",
        {"name": "Kept ETF", "ticker": ""},
    )
    assert failed.status_code == 422
    selected = re.findall(r'<option value="([^"]+)" selected>', failed.text)
    assert selected == ["ETF"]
    saved = await _post(
        client,
        f"/ui/companies/{company_id}/edit",
        {
            "name": "Kept ETF",
            "ticker": "KEPTETF",
            "instrument_type": selected[0],
        },
    )
    assert saved.status_code == 303
    assert _stored_instrument_type(client, company_id) == "ETF"


@pytest.mark.asyncio
async def test_edit_error_keeps_a_posted_type(client):
    """A failed edit that posted a type shows that type, not the stored one."""
    company_id, _data = await _create(
        client, name="Posted Type", ticker="POSTTYP", instrument_type="ETF"
    )
    failed = await _post(
        client,
        f"/ui/companies/{company_id}/edit",
        {
            "name": "Posted Type",
            "ticker": "",
            "instrument_type": "EQUITY",
        },
    )
    assert failed.status_code == 422
    assert 'value="EQUITY" selected' in failed.text
    assert '<option value="ETF" selected>' not in failed.text
    assert _stored_instrument_type(client, company_id) == "ETF"


@pytest.mark.asyncio
async def test_form_rejects_an_instrument_type_control_character(client):
    """A trailing newline is invalid, the same as on the write model.

    ``str.strip`` would hide it and store ETF. The form has to reject
    the control character before that strip, and insert no row.
    """
    response = await _post(
        client,
        "/ui/companies",
        {
            "name": "Control Type",
            "ticker": "CTRLTY",
            "instrument_type": "ETF\n",
        },
    )
    assert response.status_code == 422
    assert 'id="field-instrument_type-error"' in response.text
    assert _counts(client) == (0, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("posted", "ticker"),
    [("etf", "FOLD1"), (" ETF ", "FOLD2")],
)
async def test_form_normalises_instrument_type_case_and_space(
    client, posted, ticker
):
    """The form stores the enum. Case and surrounding spaces fold away."""
    company_id, _data = await _create(
        client,
        name="Folded Type",
        ticker=ticker,
        instrument_type=posted,
    )
    assert _stored_instrument_type(client, company_id) == "ETF"


@pytest.mark.asyncio
async def test_whitespace_instrument_type_is_treated_as_omitted(client):
    """Spaces are a blank select, not a type named with whitespace.

    Create then uses the model default STOCK. An edit that posts only
    spaces leaves the stored type alone.
    """
    company_id, _data = await _create(
        client,
        name="Space Type",
        ticker="SPCTYP",
        instrument_type="   ",
    )
    assert _stored_instrument_type(client, company_id) == "STOCK"
    changed = await _post(
        client,
        f"/ui/companies/{company_id}/edit",
        {
            "name": "Space Type",
            "ticker": "SPCTYP",
            "instrument_type": "ETF",
        },
    )
    assert changed.status_code == 303
    assert _stored_instrument_type(client, company_id) == "ETF"
    kept = await _post(
        client,
        f"/ui/companies/{company_id}/edit",
        {
            "name": "Space Type kept",
            "ticker": "SPCTYP",
            "instrument_type": "   ",
        },
    )
    assert kept.status_code == 303
    assert _stored_instrument_type(client, company_id) == "ETF"


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["pl", "en"])
async def test_unknown_instrument_type_is_422_on_the_select(client, language):
    if language == "en":
        client.cookies.set("ui_lang", "en")
    sentence = CATALOGS[language]["error.instrument_type"]
    response = await _post(
        client,
        "/ui/companies",
        {
            "name": "Bad Type",
            "ticker": "BADTYP",
            "instrument_type": "EQUITY",
        },
    )
    assert response.status_code == 422
    assert 'id="field-instrument_type"' in response.text
    assert 'name="instrument_type"' in response.text
    assert 'aria-invalid="true"' in response.text
    assert 'id="field-instrument_type-error"' in response.text
    assert sentence in response.text
    assert 'value="EQUITY" selected' in response.text
    _assert_labeled(response.text)
    assert _counts(client) == (0, 0)

    hostile = await _post(
        client,
        "/ui/companies",
        {
            "name": "Bad Type",
            "ticker": "BADTYP",
            "instrument_type": _SCRIPT,
        },
    )
    assert hostile.status_code == 422
    assert "<script>" not in hostile.text
    assert "&lt;script&gt;" in hostile.text
    assert 'aria-invalid="true"' in hostile.text
    assert _counts(client) == (0, 0)


@pytest.mark.asyncio
async def test_origin_check_blocks_cross_site_posts(client):
    before = _counts(client)
    data = {
        "name": "Evil Co",
        "ticker": "EVILCO",
        "instrument_type": "ETF",
    }
    cross = await _post(
        client, "/ui/companies", data, origin="http://evil.example"
    )
    assert cross.status_code == 403
    assert "text/html" in cross.headers["content-type"]
    assert "Żądanie zostało odrzucone" in cross.text
    assert not cross.text.lstrip().startswith("{")
    _assert_ui_headers(cross)
    assert _counts(client) == before

    client.cookies.set("ui_lang", "en")
    missing = await _post(client, "/ui/companies", data, origin=None)
    assert missing.status_code == 403
    assert "Request rejected" in missing.text
    assert "Changes are only accepted from this site." in missing.text
    assert _counts(client) == before

    referer_evil = await _post(
        client,
        "/ui/companies",
        data,
        origin=None,
        headers={"referer": "http://evil.example/form"},
    )
    assert referer_evil.status_code == 403
    scheme = await _post(
        client, "/ui/companies", data, origin="https://127.0.0.1"
    )
    assert scheme.status_code == 403
    port = await _post(
        client, "/ui/companies", data, origin="http://127.0.0.1:9999"
    )
    assert port.status_code == 403
    null = await _post(client, "/ui/companies", data, origin="null")
    assert null.status_code == 403
    userinfo = await _post(
        client,
        "/ui/companies",
        data,
        origin="http://user:secret@127.0.0.1",
    )
    assert userinfo.status_code == 403
    rescued = await _post(
        client,
        "/ui/companies",
        data,
        origin="http://evil.example",
        headers={"referer": "http://127.0.0.1/ui/companies/new"},
    )
    assert rescued.status_code == 403
    assert _counts(client) == before
    client.cookies.clear()

    fallback = await _post(
        client,
        "/ui/companies",
        {"name": "Referer Co", "ticker": "REFCO"},
        origin=None,
        headers={"referer": "http://127.0.0.1/ui/companies/new"},
    )
    assert fallback.status_code == 303
    explicit = await _post(
        client,
        "/ui/companies",
        {"name": "Port Co", "ticker": "PORTCO"},
        origin="http://127.0.0.1:80",
    )
    assert explicit.status_code == 303

    listing = await client.get(
        "/ui/companies/new", headers={"origin": "http://evil.example"}
    )
    assert listing.status_code == 200
    assert "Nowy instrument" in listing.text


@pytest.mark.asyncio
async def test_get_never_changes_rows_and_json_body_is_not_500(client):
    company_id, _data = await _create(client, name="Still Co", ticker="STILL")
    before = _counts(client)
    for path in (
        "/ui/companies/new",
        f"/ui/companies/{company_id}/edit",
        f"/ui/companies/{company_id}/delete",
        f"/ui/companies/{company_id}/metrics/new",
    ):
        response = await client.get(path)
        assert response.status_code == 200
        assert _counts(client) == before
    unused = await client.post(
        "/ui",
        data={"name": "Nope"},
        headers={"origin": _ORIGIN},
    )
    assert unused.status_code == 405
    assert "text/html" in unused.headers["content-type"]
    assert "Metoda niedozwolona" in unused.text
    assert "form-action 'self'" in unused.headers["content-security-policy"]
    assert unused.headers["referrer-policy"] == "same-origin"
    assert unused.headers["x-frame-options"] == "DENY"
    assert "GET" in unused.headers["allow"]
    assert _counts(client) == before
    client.cookies.set("ui_lang", "en")
    english = await client.put(
        "/ui/companies/new", headers={"origin": _ORIGIN}
    )
    assert english.status_code == 405
    assert "Method not allowed" in english.text
    assert "text/html" in english.headers["content-type"]
    client.cookies.clear()
    api = await client.put("/api/v1/companies/")
    assert api.status_code == 405
    assert api.headers["content-type"].startswith("application/json")
    foreign = await client.post(
        "/ui/companies",
        json={"name": "Json Co", "ticker": "JSONCO"},
        headers={"origin": _ORIGIN},
    )
    assert foreign.status_code < 500
    assert foreign.status_code != 303
    assert _counts(client) == before


@pytest.mark.asyncio
async def test_repository_integrity_error_stays_a_400(client, monkeypatch):
    company_id, _data = await _create(client, name="Guard Co", ticker="GUARD")

    def explode(self, metrics):
        raise IntegrityError("INSERT", {}, Exception("constraint"))

    monkeypatch.setattr(FinancialMetricsRepository, "create", explode)
    response = await _post(
        client,
        f"/ui/companies/{company_id}/metrics",
        {
            "period_end": "2024-12-31T00:00:00",
            "period_type": "annual",
            "revenue": "1",
        },
    )
    assert response.status_code == 400
    assert "regułę unikalności" in response.text
    assert _counts(client) == (1, 0)


def test_origin_rejection_is_the_handler_signal():
    assert issubclass(OriginRejected, Exception)


def test_formatters_and_non_string_form_values_do_not_crash():
    """Form values are strings. A non-string must not raise."""
    from datetime import datetime, timezone

    from app.ui.form_fields import _input_datetime, _input_number

    assert _input_number(None) == ""
    assert _input_number(True) == ""
    assert _input_number(float("nan")) == ""
    assert _input_number(1.25) == "1.25"
    assert _input_number(3) == "3"
    assert _input_number(object()) != ""
    assert _input_datetime("2024-01-01") == ""
    assert _input_datetime(datetime(2024, 1, 2, tzinfo=timezone.utc)) == (
        "2024-01-02T00:00:00"
    )
    payload = company_payload(
        {"name": None, "ticker": 12, "website": None, "currency": "USD"}
    )
    assert payload["name"] == ""
    assert payload["ticker"] == "12"
    assert payload["website"] is None
    metrics = metrics_payload(
        {"period_end": None, "period_type": None, "revenue": None},
        9,
        include_period_type=True,
    )
    assert metrics["period_end"] == ""
    assert metrics["period_type"] == ""
    assert metrics["revenue"] is None
    assert metrics["company_id"] == 9


@pytest.mark.asyncio
async def test_posts_to_bad_ids_are_html_404(client):
    company_id, _data = await _create(client, name="Stay Co", ticker="STAYCO")
    created = await _post(
        client,
        f"/ui/companies/{company_id}/metrics",
        {
            "period_end": "2024-12-31T00:00:00",
            "period_type": "annual",
            "revenue": "2",
        },
    )
    assert created.status_code == 303
    before = _counts(client)
    paths = (
        "/ui/companies/abc/edit",
        "/ui/companies/999999/delete",
        "/ui/companies/abc/metrics",
        f"/ui/companies/{company_id}/metrics/abc/edit",
        "/ui/companies/nope/metrics/1/edit",
        f"/ui/companies/{company_id}/metrics/999999/delete",
    )
    for path in paths:
        response = await _post(
            client, path, {"name": "Nope", "ticker": "NOPE"}
        )
        assert response.status_code == 404, path
        assert "Nie znaleziono instrumentu" in response.text
        assert "text/html" in response.headers["content-type"]
    assert _counts(client) == before


@pytest.mark.asyncio
async def test_failed_edit_keeps_the_posted_text_and_period_type(client):
    company_id, _data = await _create(client, name="Edit Co", ticker="EDITCO")
    await _post(
        client,
        f"/ui/companies/{company_id}/metrics",
        {
            "period_end": "2024-03-31T00:00:00",
            "period_type": "quarterly",
            "revenue": "4",
        },
    )
    session = client.app.state.testing_session_local()
    try:
        metrics_id = session.query(FinancialMetricsDB).one().id
    finally:
        session.close()
    company_edit = await _post(
        client,
        f"/ui/companies/{company_id}/edit",
        {"name": "Edit Co", "ticker": "", "currency": "USD"},
    )
    assert company_edit.status_code == 422
    assert "Ticker musi mieć od 1 do 20 znaków ASCII" in company_edit.text
    assert 'value="Edit Co"' in company_edit.text
    metrics_edit = await _post(
        client,
        f"/ui/companies/{company_id}/metrics/{metrics_id}/edit",
        {
            "period_end": "",
            "period_type": "annual",
            "revenue": "nan",
        },
    )
    assert metrics_edit.status_code == 422
    assert "Podaj datę i czas" in metrics_edit.text
    assert "Podaj skończoną liczbę" in metrics_edit.text
    assert "quarterly" in metrics_edit.text
    assert 'name="period_type"' not in metrics_edit.text
    assert _metrics_for(client, company_id) == [("quarterly", 4.0, None)]
