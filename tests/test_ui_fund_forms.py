"""Create and edit forms for ETF and ETC fund attributes.

TER is typed as a percent. ``0.07`` means 0.07 percent and is stored
as the fraction ``0.0007``. The conversion uses ``Decimal``. The
write models and the repository still see the fraction.

Posts go through ``FundAttributesRepository``. They do not call the
JSON API and they do not read the demo-seed header. A form body
cannot set ``source`` or ``is_synthetic``.
"""

import math
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.demo_seed_auth import DEMO_SEED_HEADER, demo_seed_token
from app.models.database_models import (
    RECORD_SOURCE_DEMO,
    RECORD_SOURCE_MANUAL,
    CompanyDB,
    FundAttributesDB,
    NoteDB,
    PriceBarDB,
    ThesisDB,
)
from app.models.price_bar import PriceBarCreate
from app.models.research import NoteCreate, ThesisCreate
from app.repositories.company_errors import CompanyNotFoundError
from app.repositories.fund_attributes_repository import (
    FundAttributesRepository,
)
from app.repositories.note_repository import NoteRepository
from app.repositories.price_bar_repository import PriceBarRepository
from app.repositories.thesis_repository import ThesisRepository
from app.ui.catalog import CATALOGS
from app.ui.form_fields import (
    fund_repository_error,
    ter_fraction_to_percent,
    ter_percent_text,
    ter_percent_to_fraction,
    validate_fund,
)
from tests.ui_html import assert_labeled

_ORIGIN = "http://127.0.0.1"
_SCRIPT = "<script>alert(1)</script>"


def _sentence(language, key):
    return CATALOGS[language][key]


def test_ter_percent_and_fraction_convert_both_ways():
    """Percent and fraction meet in the middle without binary dust.

    ``0.07 / 100`` as a float is ``0.0007000000000000001``. The form
    divides ``Decimal`` values, so ``0.07`` percent is the fraction
    ``0.0007`` exactly. Empty and blank stay null. The bounds are
    ``0`` and ``100`` percent, which are the fractions ``0`` and ``1``.
    """
    assert ter_percent_to_fraction("0.07") == Decimal("0.0007")
    assert ter_percent_to_fraction("  0.07 ") == Decimal("0.0007")
    assert ter_percent_to_fraction("0.07") != Decimal(str(0.07 / 100))
    assert ter_fraction_to_percent(Decimal("0.0007")) == Decimal("0.07")
    assert ter_fraction_to_percent(ter_percent_to_fraction("0.07")) == Decimal(
        "0.07"
    )
    assert ter_percent_to_fraction("0") == Decimal("0")
    assert ter_percent_to_fraction("100") == Decimal("1")
    assert ter_percent_to_fraction("100.0") == Decimal("1")
    assert ter_percent_to_fraction("0,07") == Decimal("0.0007")
    assert ter_percent_to_fraction("1,5") == Decimal("0.015")
    assert ter_fraction_to_percent(Decimal("0")) == Decimal("0")
    assert ter_fraction_to_percent(Decimal("1")) == Decimal("100")
    assert ter_fraction_to_percent(Decimal("0.0007")) == Decimal("0.07")
    stored = float(Decimal("0.0007"))
    assert ter_fraction_to_percent(stored) == Decimal("0.07")
    assert ter_percent_text(stored) == "0.07"
    assert ter_percent_text(0) == "0"
    assert ter_percent_text(1) == "100"
    assert ter_percent_text(float(Decimal("1"))) == "100"
    for blank in ("", "   ", None):
        assert ter_percent_to_fraction(blank) is None
    assert ter_fraction_to_percent(None) is None
    assert ter_percent_text(None) == ""
    with pytest.raises(ValueError):
        ter_percent_to_fraction("nope")
    with pytest.raises(ValueError):
        ter_percent_to_fraction("NaN")
    with pytest.raises(ValueError):
        ter_percent_to_fraction("1,2,3")
    with pytest.raises(ValueError):
        ter_percent_to_fraction("1,5.2")
    with pytest.raises(ValueError):
        ter_percent_to_fraction(True)
    with pytest.raises(ValueError):
        ter_percent_to_fraction(1.5)
    with pytest.raises(ValueError):
        ter_fraction_to_percent(True)
    with pytest.raises(ValueError):
        ter_fraction_to_percent(float("nan"))
    with pytest.raises(ValueError):
        ter_fraction_to_percent("nope")
    with pytest.raises(ValueError):
        ter_fraction_to_percent("NaN")
    with pytest.raises(ValueError):
        ter_fraction_to_percent(object())
    assert ter_fraction_to_percent("0.0007") == Decimal("0.07")
    assert ter_percent_text(True) == ""
    assert ter_percent_text(float("inf")) == ""


def test_validate_fund_maps_a_surrogate_to_the_invalid_text_key():
    """A lone surrogate cannot be posted as UTF-8. The helper still maps it.

    ``clean_text`` rejects it. The form shows ``error.surrogate`` and
    does not build a write model.
    """
    _model, errors, _form_key = validate_fund(
        {"issuer": "bad\ud800name", "as_of": "2026-09-30"},
        update=False,
    )
    assert errors["issuer"] == "error.surrogate"
    assert _model is None


def test_a_huge_aum_uses_the_number_sentence():
    """The model cap is a percent-sized number error on the AUM field."""
    model, errors, _form_key = validate_fund(
        {
            "as_of": "2026-09-30",
            "aum": "1e16",
            "aum_currency": "EUR",
            "aum_as_of": "2026-09-30",
        },
        update=False,
    )
    assert model is None
    assert errors["aum"] == "error.number"


def test_an_unknown_repository_sentence_is_the_constraint_error():
    key, fields = fund_repository_error(
        ValueError("Failed to create fund attributes")
    )
    assert key == "error.constraint"
    assert fields == ()


def _row(client, company_id):
    session = client.app.state.testing_session_local()
    try:
        return (
            session.query(FundAttributesDB)
            .filter(FundAttributesDB.company_id == company_id)
            .one_or_none()
        )
    finally:
        session.close()


def _facts(client, company_id):
    session = client.app.state.testing_session_local()
    try:
        row = (
            session.query(FundAttributesDB)
            .filter(FundAttributesDB.company_id == company_id)
            .one()
        )
        return {
            "issuer": row.issuer,
            "underlying": row.underlying,
            "ter": row.ter,
            "domicile": row.domicile,
            "replication_method": row.replication_method,
            "distribution_policy": row.distribution_policy,
            "aum": row.aum,
            "aum_currency": row.aum_currency,
            "aum_as_of": row.aum_as_of,
            "as_of": row.as_of,
            "source": row.source,
            "is_synthetic": row.is_synthetic,
        }
    finally:
        session.close()


async def _post(client, path, data=None, *, origin=_ORIGIN, headers=None):
    sent = {}
    if origin is not None:
        sent["origin"] = origin
    if headers:
        sent.update(headers)
    return await client.post(path, data=data or {}, headers=sent)


async def _company(client, *, ticker, instrument_type, name):
    response = await _post(
        client,
        "/ui/companies",
        {
            "name": name,
            "ticker": ticker,
            "instrument_type": instrument_type,
            "currency": "EUR",
        },
    )
    assert response.status_code == 303, response.text
    return int(response.headers["location"].rsplit("/", 1)[-1])


def _form(**overrides):
    data = {
        "issuer": "Issuer One",
        "underlying": "World Index",
        "ter": "0.07",
        "domicile": "Ireland",
        "replication_method": "physical",
        "distribution_policy": "accumulating",
        "aum": "1000",
        "aum_currency": "eur",
        "aum_as_of": "2026-09-30",
        "as_of": "2026-09-30",
    }
    data.update(overrides)
    return data


def _new(company_id):
    return f"/ui/companies/{company_id}/fund-attributes/new"


def _edit(company_id):
    return f"/ui/companies/{company_id}/fund-attributes/edit"


def _delete(company_id):
    return f"/ui/companies/{company_id}/fund-attributes/delete"


def _detail(company_id):
    return f"/ui/instruments/{company_id}"


@pytest.mark.asyncio
async def test_create_and_edit_fund_attributes_round_trip(client):
    company_id = await _company(
        client, ticker="FUNDUI", instrument_type="ETF", name="Fund UI"
    )
    blank = await client.get(_new(company_id))
    assert blank.status_code == 200
    assert "text/html" in blank.headers["content-type"]
    assert _sentence("pl", "page.create_fund") in blank.text
    assert _sentence("pl", "hint.ter") in blank.text
    assert 'name="source"' not in blank.text
    assert 'name="is_synthetic"' not in blank.text
    assert f'value="{_detail(company_id)}"' in blank.text
    assert "Ostatnia zmiana" not in blank.text
    assert_labeled(blank.text)
    assert _row(client, company_id) is None

    created = await _post(client, _new(company_id), _form())
    assert created.status_code == 303
    assert created.headers["location"].split("?", 1)[0] == _detail(company_id)
    stored = _facts(client, company_id)
    assert stored["issuer"] == "Issuer One"
    assert stored["underlying"] == "World Index"
    assert stored["domicile"] == "Ireland"
    assert stored["replication_method"] == "physical"
    assert stored["distribution_policy"] == "accumulating"
    assert stored["aum"] == 1000
    assert stored["aum_currency"] == "EUR"
    assert stored["aum_as_of"].isoformat() == "2026-09-30"
    assert stored["as_of"].isoformat() == "2026-09-30"
    assert stored["source"] == RECORD_SOURCE_MANUAL
    assert stored["is_synthetic"] is False
    assert ter_percent_text(stored["ter"]) == "0.07"
    detail = await client.get(_detail(company_id))
    assert detail.status_code == 200
    assert "Issuer One" in detail.text
    assert "0,07%" in detail.text
    assert f'href="{_edit(company_id)}"' in detail.text
    assert _sentence("pl", "action.edit_fund") in detail.text
    assert f'href="{_new(company_id)}"' not in detail.text

    edit = await client.get(_edit(company_id))
    assert edit.status_code == 200
    assert _sentence("pl", "page.edit_fund") in edit.text
    assert _sentence("pl", "field.updated_at") in edit.text
    assert 'value="0.07"' in edit.text
    assert 'value="Issuer One"' in edit.text
    assert 'value="EUR"' in edit.text
    assert 'value="2026-09-30"' in edit.text
    assert_labeled(edit.text)

    changed = await _post(
        client,
        _edit(company_id),
        _form(issuer="Issuer Two", ter="0.22"),
    )
    assert changed.status_code == 303
    assert changed.headers["location"].split("?", 1)[0] == _detail(company_id)
    updated = _facts(client, company_id)
    assert updated["issuer"] == "Issuer Two"
    assert ter_percent_text(updated["ter"]) == "0.22"
    assert updated["source"] == RECORD_SOURCE_MANUAL
    assert updated["is_synthetic"] is False
    again = await client.get(_detail(company_id))
    assert "0,22%" in again.text


@pytest.mark.asyncio
@pytest.mark.parametrize("percent,shown", [("0", "0"), ("100", "100")])
async def test_ter_percent_bounds_are_stored_as_fractions(
    client, percent, shown
):
    company_id = await _company(
        client,
        ticker="TER" + percent,
        instrument_type="ETC",
        name="Bound " + percent,
    )
    response = await _post(
        client,
        _new(company_id),
        _form(ter=percent, aum="", aum_currency="", aum_as_of=""),
    )
    assert response.status_code == 303, response.text
    assert ter_percent_text(_facts(client, company_id)["ter"]) == shown
    edit = await client.get(_edit(company_id))
    assert f'value="{shown}"' in edit.text


@pytest.mark.asyncio
async def test_blank_ter_is_stored_as_null_and_the_edit_field_is_empty(
    client,
):
    company_id = await _company(
        client, ticker="NOTER", instrument_type="ETF", name="No TER"
    )
    response = await _post(
        client,
        _new(company_id),
        _form(ter="", aum="", aum_currency="", aum_as_of=""),
    )
    assert response.status_code == 303, response.text
    stored = _facts(client, company_id)
    assert stored["ter"] is None
    assert stored["aum"] is None
    assert stored["aum_currency"] is None
    edit = await client.get(_edit(company_id))
    assert 'id="field-ter"' in edit.text
    assert 'name="ter" type="text" value=""' in edit.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value,key",
    [
        ("ter", "nope", "error.number"),
        ("ter", "101", "error.ter_percent"),
        ("ter", "-1", "error.number"),
        ("aum", "-1", "error.number"),
        ("as_of", "", "error.required"),
        ("issuer", "a" * 256, "error.too_long"),
        ("issuer", "bad\nname", "error.control_char"),
        ("issuer", "bad\u202ename", "error.bidi"),
        ("domicile", "bad\x00place", "error.control_char"),
        ("aum_currency", "US", "error.currency"),
        ("aum_as_of", "yesterday", "error.date"),
    ],
)
async def test_invalid_fund_input_rerenders_422_not_500(
    client, field, value, key
):
    company_id = await _company(
        client,
        ticker="BAD" + field[:4].upper() + value[:2],
        instrument_type="ETF",
        name="Bad " + field,
    )
    posted = _form(**{field: value})
    response = await _post(client, _new(company_id), posted)
    assert response.status_code == 422, response.text
    assert "text/html" in response.headers["content-type"]
    assert not response.text.lstrip().startswith("{")
    assert _sentence("pl", key) in response.text
    assert f'id="field-{field}-error"' in response.text
    assert 'aria-invalid="true"' in response.text
    assert f'id="field-{field}"' in response.text
    assert_labeled(response.text)
    assert _row(client, company_id) is None
    if value:
        assert value in response.text or value.replace("\n", "") in (
            response.text
        )


@pytest.mark.asyncio
async def test_fund_forms_render_in_english(client):
    company_id = await _company(
        client, ticker="ENFUND", instrument_type="ETC", name="EN Fund"
    )
    client.cookies.set("ui_lang", "en")
    page = await client.get(_new(company_id))
    assert page.status_code == 200
    assert _sentence("en", "page.create_fund") in page.text
    assert _sentence("en", "fund.issuer") in page.text
    assert "0.07 means 0.07%" in page.text
    assert _sentence("pl", "page.create_fund") not in page.text
    detail = await client.get(_detail(company_id))
    assert _sentence("en", "action.add_fund") in detail.text
    assert f'href="{_new(company_id)}"' in detail.text


@pytest.mark.asyncio
async def test_detail_links_follow_the_instrument_type(client):
    etf = await _company(
        client, ticker="ADDME", instrument_type="ETF", name="Needs attrs"
    )
    etc = await _company(
        client, ticker="HASROW", instrument_type="ETC", name="Has attrs"
    )
    stock = await _company(
        client, ticker="STOCKX", instrument_type="STOCK", name="A share"
    )
    await _post(client, _new(etc), _form())
    empty = await client.get(_detail(etf))
    assert f'href="{_new(etf)}"' in empty.text
    assert _sentence("pl", "action.add_fund") in empty.text
    assert f'href="{_edit(etf)}"' not in empty.text
    filled = await client.get(_detail(etc))
    assert f'href="{_edit(etc)}"' in filled.text
    assert _sentence("pl", "action.edit_fund") in filled.text
    assert f'href="{_delete(etc)}"' in filled.text
    assert _sentence("pl", "action.delete_fund") in filled.text
    assert f'href="{_new(etc)}"' not in filled.text
    share = await client.get(_detail(stock))
    assert "fund-attributes" not in share.text
    assert _sentence("pl", "action.add_fund") not in share.text
    assert _sentence("pl", "action.edit_fund") not in share.text
    assert _sentence("pl", "action.delete_fund") not in share.text
    assert f'href="{_delete(etf)}"' not in empty.text
    assert "fund-attributes/delete" not in share.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    ["new", "edit", "delete"],
)
async def test_stock_and_unknown_ids_are_html_404(client, path):
    stock = await _company(
        client, ticker="NOFUND", instrument_type="STOCK", name="No fund"
    )
    for target in (
        f"/ui/companies/{stock}/fund-attributes/{path}",
        f"/ui/companies/999999/fund-attributes/{path}",
        f"/ui/companies/abc/fund-attributes/{path}",
        f"/ui/companies/01/fund-attributes/{path}",
    ):
        got = await client.get(target)
        assert got.status_code == 404, target
        assert "text/html" in got.headers["content-type"]
        assert "Nie znaleziono" in got.text
        posted = await _post(client, target, _form())
        assert posted.status_code == 404, target
        assert "text/html" in posted.headers["content-type"]
        assert not posted.text.lstrip().startswith("{")


@pytest.mark.asyncio
async def test_edit_without_a_row_is_html_404(client):
    company_id = await _company(
        client, ticker="NOROW", instrument_type="ETF", name="No row"
    )
    got = await client.get(_edit(company_id))
    assert got.status_code == 404
    assert "text/html" in got.headers["content-type"]
    posted = await _post(client, _edit(company_id), _form())
    assert posted.status_code == 404
    assert _row(client, company_id) is None


@pytest.mark.asyncio
async def test_cross_origin_post_is_rejected(client):
    company_id = await _company(
        client, ticker="CSRFND", instrument_type="ETF", name="CSRF fund"
    )
    response = await _post(
        client,
        _new(company_id),
        _form(),
        origin="http://evil.example",
    )
    assert response.status_code == 403
    assert "text/html" in response.headers["content-type"]
    assert "Żądanie zostało odrzucone" in response.text
    assert _row(client, company_id) is None


@pytest.mark.asyncio
async def test_stored_script_in_the_issuer_is_escaped(client):
    company_id = await _company(
        client, ticker="XSSFND", instrument_type="ETF", name="XSS fund"
    )
    created = await _post(client, _new(company_id), _form(issuer=_SCRIPT))
    assert created.status_code == 303
    edit = await client.get(_edit(company_id))
    detail = await client.get(_detail(company_id))
    for page in (edit, detail):
        assert _SCRIPT not in page.text
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page.text


@pytest.mark.asyncio
async def test_form_ignores_source_synthetic_and_the_seed_header(
    client, monkeypatch
):
    monkeypatch.setattr(settings, "DEMO_SEED_ENABLED", True)
    company_id = await _company(
        client, ticker="SEEDUI", instrument_type="ETC", name="Seed UI"
    )
    created = await _post(
        client,
        _new(company_id),
        _form(source="demo", is_synthetic="true"),
        headers={DEMO_SEED_HEADER: demo_seed_token(settings.SECRET_KEY)},
    )
    assert created.status_code == 303, created.text
    stored = _facts(client, company_id)
    assert stored["source"] == RECORD_SOURCE_MANUAL
    assert stored["is_synthetic"] is False

    session = client.app.state.testing_session_local()
    try:
        row = (
            session.query(FundAttributesDB)
            .filter(FundAttributesDB.company_id == company_id)
            .one()
        )
        row.source = RECORD_SOURCE_DEMO
        row.is_synthetic = True
        session.commit()
    finally:
        session.close()

    edited = await _post(
        client,
        _edit(company_id),
        _form(issuer="Edited", source="demo", is_synthetic="false"),
        headers={DEMO_SEED_HEADER: demo_seed_token(settings.SECRET_KEY)},
    )
    assert edited.status_code == 303, edited.text
    updated = _facts(client, company_id)
    assert updated["issuer"] == "Edited"
    assert updated["source"] == RECORD_SOURCE_MANUAL
    assert updated["is_synthetic"] is True


@pytest.mark.asyncio
async def test_repository_value_error_is_400(client):
    company_id = await _company(
        client, ticker="AUMERR", instrument_type="ETF", name="AUM err"
    )
    missing = await _post(
        client,
        _new(company_id),
        _form(aum="1000", aum_currency="", aum_as_of=""),
    )
    assert missing.status_code == 400
    assert "text/html" in missing.headers["content-type"]
    assert _sentence("pl", "error.aum_needs") in missing.text
    assert _row(client, company_id) is None

    first = await _post(client, _new(company_id), _form(issuer="First"))
    assert first.status_code == 303
    duplicate = await _post(client, _new(company_id), _form(issuer="Second"))
    assert duplicate.status_code == 400
    assert _sentence("pl", "error.fund_exists") in duplicate.text
    assert _facts(client, company_id)["issuer"] == "First"

    extra = await _post(
        client,
        _edit(company_id),
        _form(aum="", aum_currency="EUR", aum_as_of=""),
    )
    assert extra.status_code == 400
    assert _sentence("pl", "error.aum_extra") in extra.text
    assert _facts(client, company_id)["issuer"] == "First"
    assert _facts(client, company_id)["aum"] == 1000


@pytest.mark.asyncio
async def test_unsafe_next_does_not_leave_the_site(client):
    company_id = await _company(
        client, ticker="REDIR", instrument_type="ETF", name="Redirect"
    )
    response = await _post(
        client,
        _new(company_id),
        _form(next="https://evil.example/phish"),
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "evil.example" not in location
    assert location.split("?", 1)[0] == "/ui"
    safe = await _post(
        client,
        _edit(company_id),
        _form(issuer="Stayed", next=_detail(company_id)),
    )
    assert safe.status_code == 303
    assert safe.headers["location"].split("?", 1)[0] == _detail(company_id)


@pytest.mark.asyncio
async def test_stock_with_a_stored_row_keeps_the_detail_and_hides_the_form(
    client,
):
    """Changing ETF to STOCK does not delete the attribute row.

    The detail page still shows the stored issuer. The form routes
    answer 404 because the instrument is a stock, and the page has
    no add or edit link. Cleaning that row up is a later change.
    """
    company_id = await _company(
        client, ticker="WASFUND", instrument_type="ETF", name="Was fund"
    )
    created = await _post(client, _new(company_id), _form(issuer="Still here"))
    assert created.status_code == 303
    switched = await _post(
        client,
        f"/ui/companies/{company_id}/edit",
        {
            "name": "Was fund",
            "ticker": "WASFUND",
            "instrument_type": "STOCK",
            "currency": "EUR",
        },
    )
    assert switched.status_code == 303
    detail = await client.get(_detail(company_id))
    assert "Still here" in detail.text
    assert "fund-attributes" not in detail.text
    edit = await client.get(_edit(company_id))
    assert edit.status_code == 404
    removed = await client.get(_delete(company_id))
    assert removed.status_code == 404
    posted = await _post(client, _delete(company_id), {})
    assert posted.status_code == 404
    assert _facts(client, company_id)["issuer"] == "Still here"
    assert _facts(client, company_id)["source"] == RECORD_SOURCE_MANUAL


def _set_ter(client, company_id, fraction):
    session = client.app.state.testing_session_local()
    try:
        row = (
            session.query(FundAttributesDB)
            .filter(FundAttributesDB.company_id == company_id)
            .one()
        )
        row.ter = float(fraction)
        session.commit()
    finally:
        session.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fraction,polish,english",
    [
        (Decimal("0.0000001"), "0,00001%", "0.00001%"),
        (Decimal("0.0007"), "0,07%", "0.07%"),
        (Decimal("0"), "0%", "0%"),
    ],
)
async def test_detail_ter_keeps_small_percents_in_both_languages(
    client, fraction, polish, english
):
    company_id = await _company(
        client,
        ticker="TINY" + polish[:1] + str(fraction)[-1],
        instrument_type="ETF",
        name="Tiny TER",
    )
    created = await _post(
        client,
        _new(company_id),
        _form(ter="0", aum="", aum_currency="", aum_as_of=""),
    )
    assert created.status_code == 303
    _set_ter(client, company_id, fraction)
    page = await client.get(_detail(company_id))
    assert page.status_code == 200
    ter = page.text.split('data-field="fund-ter">', 1)[1].split("</dd>", 1)[0]
    assert polish in ter
    client.cookies.set("ui_lang", "en")
    english_page = await client.get(_detail(company_id))
    ter_en = english_page.text.split('data-field="fund-ter">', 1)[1].split(
        "</dd>", 1
    )[0]
    assert english in ter_en


def _location_next(response):
    parts = urlsplit(response.headers["location"])
    return parts.path, parse_qs(parts.query).get("next", [])


@pytest.mark.asyncio
async def test_a_comma_ter_is_stored_as_a_fraction_and_edited_with_a_period(
    client,
):
    company_id = await _company(
        client, ticker="COMMAS", instrument_type="ETF", name="Comma TER"
    )
    small = await _post(
        client,
        _new(company_id),
        _form(ter="0,07", aum="", aum_currency="", aum_as_of=""),
    )
    assert small.status_code == 303, small.text
    assert ter_fraction_to_percent(_facts(client, company_id)["ter"]) == (
        Decimal("0.07")
    )
    edit = await client.get(_edit(company_id))
    assert 'value="0.07"' in edit.text
    assert 'value="0,07"' not in edit.text

    other = await _company(
        client, ticker="COMMA2", instrument_type="ETC", name="One and a half"
    )
    one_half = await _post(
        client,
        _new(other),
        _form(ter="1,5", aum="", aum_currency="", aum_as_of=""),
    )
    assert one_half.status_code == 303, one_half.text
    stored = _facts(client, other)["ter"]
    assert ter_fraction_to_percent(stored) == Decimal("1.5")
    assert Decimal(str(stored)) == Decimal("0.015")


@pytest.mark.asyncio
async def test_more_than_one_ter_separator_is_422(client):
    company_id = await _company(
        client, ticker="BADSEP", instrument_type="ETF", name="Bad separator"
    )
    response = await _post(client, _new(company_id), _form(ter="1,2,3"))
    assert response.status_code == 422
    assert _sentence("pl", "error.number") in response.text
    assert "1,2,3" in response.text
    assert _row(client, company_id) is None
    mixed = await _post(client, _new(company_id), _form(ter="1,5.2"))
    assert mixed.status_code == 422
    assert _sentence("pl", "error.number") in mixed.text
    assert "1,5.2" in mixed.text
    assert _row(client, company_id) is None


@pytest.mark.asyncio
async def test_ter_just_above_100_percent_is_422(client):
    company_id = await _company(
        client, ticker="TERCAP", instrument_type="ETF", name="TER cap"
    )
    response = await _post(client, _new(company_id), _form(ter="100.0001"))
    assert response.status_code == 422
    assert "TER musi być procentem od 0 do 100." in response.text
    assert "100.0001" in response.text
    assert _row(client, company_id) is None


@pytest.mark.asyncio
async def test_get_new_redirects_when_a_row_exists_and_post_stays_400(client):
    company_id = await _company(
        client, ticker="HASONE", instrument_type="ETF", name="Has one"
    )
    created = await _post(client, _new(company_id), _form(issuer="First"))
    assert created.status_code == 303
    home = _detail(company_id)
    again = await client.get(_new(company_id))
    assert again.status_code == 303
    path, nxt = _location_next(again)
    assert path == _edit(company_id)
    assert nxt == []

    kept = await client.get(_new(company_id), params={"next": home})
    assert kept.status_code == 303
    path, nxt = _location_next(kept)
    assert path == _edit(company_id)
    assert nxt == [home]
    edit = await client.get(kept.headers["location"])
    assert edit.status_code == 200
    assert f'name="next" value="{home}"' in edit.text

    unsafe = await client.get(
        _new(company_id), params={"next": "//evil.example/phish"}
    )
    assert unsafe.status_code == 303
    assert "evil" not in unsafe.headers["location"]
    path, nxt = _location_next(unsafe)
    assert path == _edit(company_id)
    assert nxt == ["/ui"]

    posted = await _post(client, _new(company_id), _form(issuer="Second"))
    assert posted.status_code == 400
    assert _facts(client, company_id)["issuer"] == "First"


@pytest.mark.asyncio
async def test_a_missing_company_during_save_is_the_html_404(
    client, monkeypatch
):
    company_id = await _company(
        client, ticker="GONECO", instrument_type="ETF", name="Gone"
    )

    def missing(self, company_id, attributes, **kwargs):
        raise CompanyNotFoundError(company_id)

    monkeypatch.setattr(FundAttributesRepository, "create", missing)
    response = await _post(client, _new(company_id), _form())
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    assert _row(client, company_id) is None


@pytest.mark.asyncio
async def test_an_update_that_returns_none_is_the_html_404(
    client, monkeypatch
):
    company_id = await _company(
        client, ticker="VANISH", instrument_type="ETF", name="Vanish"
    )
    created = await _post(client, _new(company_id), _form(issuer="Kept"))
    assert created.status_code == 303

    def vanish(self, company_id, attributes):
        return None

    monkeypatch.setattr(FundAttributesRepository, "update", vanish)
    response = await _post(client, _edit(company_id), _form(issuer="Later"))
    assert response.status_code == 404
    assert _facts(client, company_id)["issuer"] == "Kept"


@pytest.mark.asyncio
async def test_a_single_repository_field_error_is_inline(client, monkeypatch):
    company_id = await _company(
        client, ticker="ONEFLD", instrument_type="ETF", name="One field"
    )

    def boom(self, company_id, attributes, **kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(FundAttributesRepository, "create", boom)
    monkeypatch.setattr(
        "app.ui.forms.fund_repository_error",
        lambda exc: ("error.constraint", ("issuer",)),
    )
    response = await _post(client, _new(company_id), _form())
    assert response.status_code == 400
    assert 'id="field-issuer-error"' in response.text
    assert _sentence("pl", "error.constraint") in response.text
    assert _row(client, company_id) is None


def _plant_kept_rows(client, company_id):
    """A price, a note, and a thesis that delete must leave in place."""
    session = client.app.state.testing_session_local()
    try:
        PriceBarRepository(session).create(
            company_id,
            PriceBarCreate(
                date="2026-01-02",
                open="10",
                high="11",
                low="10",
                close="11",
                currency="EUR",
                source="demo",
                retrieved_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ),
        )
        NoteRepository(session).create(
            company_id, NoteCreate(body="Kept when attributes go.")
        )
        ThesisRepository(session).create(
            company_id,
            ThesisCreate(title="Kept thesis", body="Still the thesis."),
        )
    finally:
        session.close()


def _neighbors(client, company_id):
    session = client.app.state.testing_session_local()
    try:
        company = session.get(CompanyDB, company_id)
        return {
            "company": company.ticker if company is not None else None,
            "attributes": (
                session.query(FundAttributesDB)
                .filter(FundAttributesDB.company_id == company_id)
                .count()
            ),
            "prices": (
                session.query(PriceBarDB)
                .filter(PriceBarDB.instrument_id == company_id)
                .count()
            ),
            "notes": (
                session.query(NoteDB)
                .filter(NoteDB.company_id == company_id)
                .count()
            ),
            "theses": (
                session.query(ThesisDB)
                .filter(ThesisDB.company_id == company_id)
                .count()
            ),
        }
    finally:
        session.close()


@pytest.mark.asyncio
async def test_delete_form_removes_only_the_attribute_row(client):
    company_id = await _company(
        client, ticker="DELFUND", instrument_type="ETF", name="Delete fund"
    )
    created = await _post(client, _new(company_id), _form(issuer="Going"))
    assert created.status_code == 303
    _plant_kept_rows(client, company_id)
    confirm = await client.get(_delete(company_id))
    assert confirm.status_code == 200
    assert "text/html" in confirm.headers["content-type"]
    assert _sentence("pl", "page.delete_fund") in confirm.text
    assert _sentence("pl", "delete.fund_question") in confirm.text
    assert _sentence("pl", "delete.fund_warning") in confirm.text
    assert "Delete fund" in confirm.text
    assert f'action="{_delete(company_id)}"' in confirm.text
    assert _neighbors(client, company_id)["attributes"] == 1

    removed = await _post(client, _delete(company_id), {})
    assert removed.status_code == 303
    assert removed.headers["location"].split("?", 1)[0] == _detail(company_id)
    kept = _neighbors(client, company_id)
    assert kept["attributes"] == 0
    assert kept["company"] == "DELFUND"
    assert kept["prices"] == 1
    assert kept["notes"] == 1
    assert kept["theses"] == 1
    detail = await client.get(_detail(company_id))
    assert f'href="{_new(company_id)}"' in detail.text
    assert f'href="{_delete(company_id)}"' not in detail.text
    assert "Going" not in detail.text

    again = await _post(client, _delete(company_id), {})
    assert again.status_code == 404
    assert kept["prices"] == _neighbors(client, company_id)["prices"]


@pytest.mark.asyncio
async def test_get_delete_does_not_remove_the_row(client):
    company_id = await _company(
        client, ticker="GETDEL", instrument_type="ETC", name="Get delete"
    )
    await _post(client, _new(company_id), _form())
    page = await client.get(_delete(company_id))
    assert page.status_code == 200
    assert _row(client, company_id) is not None


@pytest.mark.asyncio
async def test_delete_form_renders_in_english(client):
    company_id = await _company(
        client, ticker="ENDEL", instrument_type="ETF", name="EN delete"
    )
    await _post(client, _new(company_id), _form())
    client.cookies.set("ui_lang", "en")
    page = await client.get(_delete(company_id))
    assert _sentence("en", "page.delete_fund") in page.text
    assert _sentence("en", "delete.fund_question") in page.text
    assert _sentence("en", "action.confirm_delete") in page.text
    detail = await client.get(_detail(company_id))
    assert _sentence("en", "action.delete_fund") in detail.text
    assert f'href="{_delete(company_id)}"' in detail.text


@pytest.mark.asyncio
async def test_cross_origin_delete_is_rejected(client):
    company_id = await _company(
        client, ticker="CSRFDEL", instrument_type="ETF", name="CSRF delete"
    )
    await _post(client, _new(company_id), _form())
    response = await _post(
        client, _delete(company_id), {}, origin="http://evil.example"
    )
    assert response.status_code == 403
    assert "text/html" in response.headers["content-type"]
    assert "Żądanie zostało odrzucone" in response.text
    assert _row(client, company_id) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "target",
    [
        "//evil.example/phish",
        "https://evil.example/phish",
        "javascript:alert(1)",
    ],
)
async def test_delete_redirect_rejects_an_unsafe_next(client, target):
    company_id = await _company(
        client,
        ticker="NXT" + str(abs(hash(target)) % 10000),
        instrument_type="ETF",
        name="Unsafe next",
    )
    await _post(client, _new(company_id), _form())
    response = await _post(client, _delete(company_id), {"next": target})
    assert response.status_code == 303
    location = response.headers["location"]
    assert "evil" not in location.casefold()
    assert "javascript" not in location.casefold()
    assert location.split("?", 1)[0] == "/ui"
    assert _row(client, company_id) is None


@pytest.mark.asyncio
async def test_delete_without_a_row_is_html_404(client):
    company_id = await _company(
        client, ticker="NOROWD", instrument_type="ETF", name="No row delete"
    )
    got = await client.get(_delete(company_id))
    assert got.status_code == 404
    assert "text/html" in got.headers["content-type"]
    posted = await _post(client, _delete(company_id), {})
    assert posted.status_code == 404
    assert not posted.text.lstrip().startswith("{")


@pytest.mark.asyncio
async def test_failed_delete_commit_is_400_and_keeps_the_row(
    client, monkeypatch
):
    company_id = await _company(
        client, ticker="ROLLBACK", instrument_type="ETF", name="Rollback"
    )
    await _post(client, _new(company_id), _form(issuer="Stay"))
    driver = "secret-driver-token"

    def commit_flushes_then_fails(self):
        self.flush()
        raise IntegrityError("DELETE", {}, Exception(driver))

    monkeypatch.setattr(Session, "commit", commit_flushes_then_fails)
    response = await _post(client, _delete(company_id), {})
    assert response.status_code == 400
    assert "text/html" in response.headers["content-type"]
    assert _sentence("pl", "error.fund_delete") in response.text
    assert driver not in response.text
    assert _facts(client, company_id)["issuer"] == "Stay"


@pytest.mark.asyncio
async def test_delete_value_error_is_400_and_does_not_echo_the_text(
    client, monkeypatch
):
    company_id = await _company(
        client, ticker="VALDEL", instrument_type="ETF", name="Value delete"
    )
    await _post(client, _new(company_id), _form(issuer="Stay"))
    secret = "driver said unique violation"

    def explode(self, company_id):
        raise ValueError(secret)

    monkeypatch.setattr(FundAttributesRepository, "delete", explode)
    response = await _post(client, _delete(company_id), {})
    assert response.status_code == 400
    assert _sentence("pl", "error.fund_delete") in response.text
    assert secret not in response.text
    assert _facts(client, company_id)["issuer"] == "Stay"


@pytest.mark.asyncio
async def test_a_blank_as_of_on_edit_is_422_and_keeps_the_stored_date(client):
    # The repository refuses to clear as_of, so the form must say the
    # field is required instead of a uniqueness error.
    company_id = await _company(
        client, ticker="ASOFED", instrument_type="ETF", name="As of edit"
    )
    created = await _post(client, _new(company_id), _form())
    assert created.status_code == 303, created.text

    response = await _post(client, _edit(company_id), _form(as_of=""))

    assert response.status_code == 422, response.text
    assert _sentence("pl", "error.required") in response.text
    assert 'id="field-as_of-error"' in response.text
    assert _sentence("pl", "error.constraint") not in response.text
    assert _facts(client, company_id)["as_of"].isoformat() == "2026-09-30"


def test_a_ter_out_of_range_or_with_underscores_is_not_a_fraction():
    for text in (
        "1e1000002",
        "-1e1000002",
        "100.00000000000000001",
        "0_07",
        "5_0",
    ):
        with pytest.raises(ValueError):
            ter_percent_to_fraction(text)
    assert str(ter_percent_to_fraction("-0")) == "0"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ter,key",
    [
        ("1e1000002", "error.ter_percent"),
        ("100.00000000000000001", "error.ter_percent"),
        ("-1e1000002", "error.number"),
        ("0_07", "error.number"),
    ],
)
async def test_a_ter_the_hint_does_not_describe_is_422(client, ter, key):
    company_id = await _company(
        client,
        ticker="TERX" + str(len(ter)),
        instrument_type="ETF",
        name="Odd TER",
    )
    response = await _post(client, _new(company_id), _form(ter=ter))
    assert response.status_code == 422, response.text
    assert _sentence("pl", key) in response.text
    assert 'id="field-ter-error"' in response.text
    assert _row(client, company_id) is None


@pytest.mark.asyncio
async def test_an_issuer_edit_keeps_an_aum_with_more_than_12_digits(client):
    company_id = await _company(
        client, ticker="BIGAUM", instrument_type="ETF", name="Big AUM"
    )
    created = await _post(
        client, _new(company_id), _form(aum="1234567890123.45")
    )
    assert created.status_code == 303, created.text
    edit = await client.get(_edit(company_id))
    assert 'value="1234567890123.45"' in edit.text

    changed = await _post(
        client,
        _edit(company_id),
        _form(issuer="Issuer Two", aum="1234567890123.45"),
    )

    assert changed.status_code == 303, changed.text
    assert _facts(client, company_id)["aum"] == 1234567890123.45


@pytest.mark.asyncio
async def test_a_comma_aum_is_stored_like_a_comma_ter(client):
    company_id = await _company(
        client, ticker="AUMCOMMA", instrument_type="ETF", name="Comma AUM"
    )
    created = await _post(client, _new(company_id), _form(aum="1234,5"))
    assert created.status_code == 303, created.text
    assert _facts(client, company_id)["aum"] == 1234.5
    edit = await client.get(_edit(company_id))
    assert 'value="1234.5"' in edit.text


@pytest.mark.asyncio
@pytest.mark.parametrize("aum", ["1,2,3", "1,234.5"])
async def test_more_than_one_aum_separator_is_422(client, aum):
    company_id = await _company(
        client,
        ticker="AUMSEP" + str(len(aum)),
        instrument_type="ETF",
        name="Bad AUM separator",
    )
    response = await _post(client, _new(company_id), _form(aum=aum))
    assert response.status_code == 422, response.text
    assert _sentence("pl", "error.number") in response.text
    assert 'id="field-aum-error"' in response.text
    assert aum in response.text
    assert _row(client, company_id) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("aum", ["0_07", "1,0_0", "250,000", "1,500"])
async def test_an_aum_the_form_cannot_read_safely_is_422(client, aum):
    # Pydantic reads "0_07" as 7. "250,000" may be a thousands
    # separator, and reading it as 250 would lose three zeros.
    company_id = await _company(
        client,
        ticker="AUMODD" + str(len(aum)) + aum[0],
        instrument_type="ETF",
        name="Odd AUM",
    )
    response = await _post(client, _new(company_id), _form(aum=aum))
    assert response.status_code == 422, response.text
    assert _sentence("pl", "error.number") in response.text
    assert 'id="field-aum-error"' in response.text
    assert aum in response.text
    assert _row(client, company_id) is None


def test_a_minus_zero_aum_is_a_plain_zero():
    model, errors, _form_key = validate_fund(
        {
            "as_of": "2026-09-30",
            "aum": "-0",
            "aum_currency": "EUR",
            "aum_as_of": "2026-09-30",
        },
        update=False,
    )
    assert errors == {}
    assert model.aum == 0
    assert math.copysign(1, model.aum) == 1


def test_an_aum_comma_with_more_than_three_integer_digits_is_a_decimal():
    model, errors, _form_key = validate_fund(
        {
            "as_of": "2026-09-30",
            "aum": "1234,567",
            "aum_currency": "EUR",
            "aum_as_of": "2026-09-30",
        },
        update=False,
    )
    assert errors == {}
    assert model.aum == 1234.567
