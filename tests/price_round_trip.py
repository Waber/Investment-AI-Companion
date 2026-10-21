"""Exact OHLC round-trips shared by the SQLite and PostgreSQL suites.

The prices are JSON strings. A Python float cannot hold
``999999999999.99999999``, so the body must not be built from one.
Each bar is flat (open, high, low, and close are the same price) so
the candle checks are satisfied and the assertion is about the price
itself.
"""

EXACT_PRICES = (
    "999999999.99999999",
    "999999999999.99999999",
    "999999999999.12345678",
)


def _company_body(ticker):
    return {
        "name": "Synthetic " + ticker,
        "ticker": ticker,
        "currency": "USD",
    }


def flat_price(price, **overrides):
    """One valid bar whose four prices are the same string."""
    payload = {
        "date": "2026-04-01",
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "volume": 100,
        "currency": "USD",
        "source": "exact",
        "retrieved_at": "2026-09-30T18:00:00Z",
    }
    payload.update(overrides)
    return payload


async def assert_exact_round_trip(client, ticker):
    """POST each exact price, then GET the same strings back.

    Returns the instrument id so a caller can also look at the column.
    """
    created_company = await client.post(
        "/api/v1/companies/", json=_company_body(ticker)
    )
    assert created_company.status_code == 201, created_company.text
    instrument_id = created_company.json()["id"]
    path = f"/api/v1/instruments/{instrument_id}/prices"
    dates = ("2026-04-01", "2026-04-02", "2026-04-03")
    for price, day in zip(EXACT_PRICES, dates):
        created = await client.post(path, json=flat_price(price, date=day))
        assert created.status_code == 201, created.text
        assert created.json()["open"] == price
        assert created.json()["high"] == price
        assert created.json()["low"] == price
        assert created.json()["close"] == price
    listed = await client.get(path)
    assert listed.status_code == 200, listed.text
    by_date = {row["date"]: row for row in listed.json()}
    assert list(by_date) == list(dates)
    for price, day in zip(EXACT_PRICES, dates):
        row = by_date[day]
        assert row["open"] == price
        assert row["high"] == price
        assert row["low"] == price
        assert row["close"] == price
    return instrument_id


async def assert_failed_post_leaves_no_row(client, ticker):
    """A rejected POST does not add a row, and does not remove one."""
    created_company = await client.post(
        "/api/v1/companies/", json=_company_body(ticker)
    )
    assert created_company.status_code == 201, created_company.text
    instrument_id = created_company.json()["id"]
    path = f"/api/v1/instruments/{instrument_id}/prices"
    kept = await client.post(
        path, json=flat_price("10.50000000", date="2026-05-01")
    )
    assert kept.status_code == 201, kept.text
    rejected = (
        (flat_price("1e400", date="2026-05-04"), 422),
        (
            flat_price(
                "10.00000000",
                date="2026-05-05",
                high="1.00000000",
            ),
            422,
        ),
        (flat_price("1000000000000", date="2026-05-06"), 422),
        (flat_price("10.50000000", date="2026-05-01"), 400),
    )
    for payload, status in rejected:
        response = await client.post(path, json=payload)
        assert response.status_code == status, response.text
    listed = await client.get(path)
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert [row["date"] for row in rows] == ["2026-05-01"]
    assert rows[0]["open"] == "10.50000000"


async def assert_negative_zero_is_zero(client, ticker):
    """POST open ``-0`` returns 201 and ``0.00000000``.

    ``Decimal('-0')`` compares equal to zero and still has a sign.
    Left alone, SQLite stores ``-0.00000000``. PostgreSQL drops the
    sign, the read-back does not match, and the POST is 400.
    The other three prices are ``0`` so the candle stays valid.
    """
    created_company = await client.post(
        "/api/v1/companies/", json=_company_body(ticker)
    )
    assert created_company.status_code == 201, created_company.text
    instrument_id = created_company.json()["id"]
    path = f"/api/v1/instruments/{instrument_id}/prices"
    created = await client.post(
        path, json=flat_price("0", open="-0", date="2026-06-01")
    )
    assert created.status_code == 201, created.text
    assert created.json()["open"] == "0.00000000"
    # This is not zero yet. Rounding half-even to 8 places makes
    # negative zero, which has the same sign split as "-0".
    rounded = await client.post(
        path,
        json=flat_price("0", open="-0.000000001", date="2026-06-02"),
    )
    assert rounded.status_code == 201, rounded.text
    assert rounded.json()["open"] == "0.00000000"
