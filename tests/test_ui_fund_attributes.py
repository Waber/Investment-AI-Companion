"""The instrument page shows fund attributes and price-derived metrics.

A missing TER is the "no data" string, not zero. A manual row does
not show the word manual. The price return is the hand-calculated
percent.
"""

from datetime import date, datetime, timezone

import pytest

from app.models.price_bar import PriceBarCreate
from app.repositories.price_bar_repository import PriceBarRepository


@pytest.mark.asyncio
async def test_etf_detail_shows_a_missing_ter_and_the_one_year_return(client):
    created = await client.post(
        "/api/v1/companies/",
        json={
            "name": "Demo Fund",
            "ticker": "FUND",
            "instrument_type": "ETF",
            "currency": "EUR",
        },
    )
    company_id = created.json()["id"]
    await client.post(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json={
            "issuer": "Demo Issuer",
            "underlying": "Synthetic Index",
            "ter": None,
            "domicile": "Ireland",
            "replication_method": "physical",
            "distribution_policy": "accumulating",
            "aum": 1000,
            "aum_currency": "EUR",
            "aum_as_of": "2026-09-30",
            "as_of": "2026-09-30",
        },
    )
    session = client.app.state.testing_session_local()
    try:
        prices = PriceBarRepository(session)
        for day, close in (
            (date(2023, 1, 2), "50"),
            (date(2025, 1, 2), "100"),
            (date(2026, 1, 2), "110"),
        ):
            prices.create(
                company_id,
                PriceBarCreate(
                    date=day,
                    open=close,
                    high=close,
                    low=close,
                    close=close,
                    currency="EUR",
                    source="demo",
                    retrieved_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
                ),
            )
    finally:
        session.close()

    page = await client.get(f"/ui/instruments/{company_id}")
    assert page.status_code == 200
    html = page.text
    assert "Atrybuty funduszu" in html
    assert 'data-field="fund-ter"' in html
    ter = html.split('data-field="fund-ter">', 1)[1].split("</dd>", 1)[0]
    assert "brak danych" in ter
    assert ">0<" not in ter
    assert "Demo Issuer" in html
    one_year = html.split('data-field="price-return_1y">', 1)[1].split(
        "</dd>", 1
    )[0]
    assert "10%" in one_year
    source = html.split('data-field="fund-source">', 1)[1].split("</dd>", 1)[0]
    assert "manual" not in source
    assert "brak danych" in source
