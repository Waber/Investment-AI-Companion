"""Create and edit forms for ETF and ETC fund attributes.

TER is typed as a percent. ``0.07`` means 0.07 percent and is stored
as the fraction ``0.0007``. The conversion uses ``Decimal``. The
write models and the repository still see the fraction.

Posts go through ``FundAttributesRepository``. They do not call the
JSON API and they do not read the demo-seed header. A form body
cannot set ``source`` or ``is_synthetic``.
"""

from decimal import Decimal

import pytest

from app.core.config import settings
from app.demo_seed_auth import DEMO_SEED_HEADER, demo_seed_token
from app.models.database_models import (
    RECORD_SOURCE_DEMO,
    RECORD_SOURCE_MANUAL,
    FundAttributesDB,
)
from app.ui.catalog import CATALOGS
from app.ui.form_fields import (
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
    assert f'href="{_new(etc)}"' not in filled.text
    share = await client.get(_detail(stock))
    assert "fund-attributes" not in share.text
    assert _sentence("pl", "action.add_fund") not in share.text
    assert _sentence("pl", "action.edit_fund") not in share.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    ["new", "edit"],
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
    assert _facts(client, company_id)["issuer"] == "Still here"
    assert _facts(client, company_id)["source"] == RECORD_SOURCE_MANUAL
