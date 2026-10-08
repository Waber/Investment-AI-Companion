"""Instrument view-model, including which websites may be links."""

from datetime import datetime, timezone

from app.ui.view_models import (
    EXTERNAL_LINK_REL,
    http_website_href,
    to_instrument,
    website_view,
)


class Row:
    """Enough of a company or metric row for the mapper. Not a table."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_only_http_and_https_become_links():
    blocked = [
        None,
        "",
        "   ",
        "javascript:alert(1)",
        "JavaScript:alert(1)",
        " javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
        "http://",
        "http:example.com",
        "https://example.com/a b",
        "https://example.com/\nnext",
    ]
    for value in blocked:
        assert http_website_href(value) is None
        view = website_view(value)
        assert view.href is None
        assert view.rel is None

    spaced = website_view(" javascript:alert(1)")
    assert spaced.text == "javascript:alert(1)"
    assert website_view(None).text is None
    assert website_view("   ").text is None

    for value in (
        "https://example.com/demo",
        "http://example.com/demo",
        "HTTP://example.com/demo",
        "HTTPS://example.com/demo",
    ):
        assert http_website_href(value) == value
        view = website_view(value)
        assert view.href == value
        assert view.text == value
        assert view.rel == EXTERNAL_LINK_REL

    padded = website_view("  https://example.com/demo  ")
    assert padded.text == "https://example.com/demo"
    assert padded.href == "https://example.com/demo"
    assert padded.rel == EXTERNAL_LINK_REL


def test_company_row_becomes_an_instrument_view():
    company = Row(
        id=7,
        name="  Demo One  ",
        ticker="DEMO_ONE",
        description="[IAC-DEMO-V1] Synthetic only",
        website=" javascript:alert(1)",
        exchange=" DEMO-WSE ",
        currency="PLN",
        country="Poland",
        sector=None,
        industry="  ",
        financial_metrics=[
            Row(
                period_end=datetime(2023, 12, 31, tzinfo=timezone.utc),
                period_type="annual",
                revenue=0,
                net_income=None,
                pe_ratio=float("nan"),
            ),
            Row(
                period_end=datetime(2026, 3, 31, tzinfo=timezone.utc),
                period_type="quarterly",
                revenue=100000,
                net_income=-5.5,
            ),
            Row(
                period_end=datetime(2024, 6, 30, tzinfo=timezone.utc),
                period_type="Monthly",
                revenue=1,
            ),
        ],
    )
    view = to_instrument(company)
    assert view.id == 7
    assert view.instrument_type == "stock"
    assert view.name == "Demo One"
    assert view.exchange == "DEMO-WSE"
    assert view.is_synthetic is True
    assert view.source == "demo-v1"
    assert view.website.href is None
    assert view.website.text == "javascript:alert(1)"
    assert view.sector is None
    assert view.industry is None
    assert view.as_of == datetime(2026, 3, 31, tzinfo=timezone.utc)
    assert [item.period_key for item in view.annual] == ["2023-12-31"]
    assert view.annual[0].values["revenue"] == 0
    assert view.annual[0].values["net_income"] is None
    assert view.annual[0].values["pe_ratio"] is None
    assert view.annual[0].values["total_assets"] is None
    assert view.quarterly[0].values["net_income"] == -5.5
    assert [item.period_key for item in view.other] == ["2024-06-30"]

    plain = Row(
        id=8,
        name="Other",
        ticker="OTHER",
        description="User notes",
        website=None,
        exchange=None,
        currency=None,
        country=None,
        sector=None,
        industry=None,
        financial_metrics=[],
    )
    plain_view = to_instrument(plain)
    assert plain_view.is_synthetic is False
    assert plain_view.source is None
    assert plain_view.as_of is None
    assert plain_view.website.text is None
    assert plain_view.annual == []
    assert plain_view.quarterly == []
