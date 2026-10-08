"""Provider-data hygiene (#50) and ticker rules (#17, #50).

A provider ValidationError is HTTP 502 with a fixed detail. Tickers
match a short symbol pattern. Log lines use ``%r`` so a newline in a
ticker cannot start a second log line.
"""

import logging

import pytest
from pydantic import ValidationError

from app.api.data_collection import (
    FetchCompanyRequest,
    fetch_company_data,
    get_yahoo_finance_collector,
)
from app.data_collectors import yahoo_finance
from app.data_collectors.yahoo_finance import YahooFinanceCollector
from app.models.company import CompanyCreate, normalize_ticker
from app.models.database_models import CompanyDB
from app.repositories.company_repository import CompanyRepository

COMPANIES = "/api/v1/companies/"
METRICS = "/api/v1/financial-metrics/"
FETCH = "/api/v1/data-collection/fetch-company"
FETCH_METRICS = "/api/v1/data-collection/fetch-financial-metrics"


def test_normalize_ticker_leaves_none_and_non_strings():
    assert normalize_ticker(None) is None
    assert normalize_ticker(12) == 12


def test_non_string_currency_is_rejected():
    with pytest.raises(ValidationError):
        CompanyCreate(name="C", ticker="CURR", currency=1)


VALID_TICKERS = (
    "PKN.WA",
    "CDR.WA",
    "VWCE.DE",
    "BRK-B",
    "^GSPC",
    "EURUSD=X",
)

# Control characters stay in the value. strip() would hide a trailing
# newline, and the rule is to reject the character, not delete it.
CONTROL_TICKERS = (
    "AAPL\nINFO forged",
    "AAPL\r\nINFO",
    "\x00AAPL",
    "AAPL\x1b",
    "AAPL\t",
)


class PayloadCollector:
    """Yahoo stand-in. Returns a fixed dict and does not use the network."""

    def __init__(self, payload):
        self.payload = payload

    def fetch_company_info(self, ticker):
        return dict(self.payload)


def _count(client) -> int:
    session = client.app.state.testing_session_local()
    try:
        return session.query(CompanyDB).count()
    finally:
        session.close()


def _assert_no_forged_log_line(caplog, marker: str) -> None:
    """A newline inside a ticker must not become its own log line.

    ``%r`` renders the newline as the two characters ``\\`` and ``n``,
    so the forged marker stays on the same line as the real record.
    """
    for record in caplog.records:
        message = record.getMessage()
        assert "\n" not in message
        assert "\r" not in message
    rendered = "\n".join(record.getMessage() for record in caplog.records)
    assert f"\n{marker}" not in rendered
    assert f"\nINFO {marker}" not in rendered


@pytest.mark.asyncio
@pytest.mark.parametrize("ticker", VALID_TICKERS)
async def test_valid_tickers_are_accepted_on_create(client, ticker):
    response = await client.post(
        COMPANIES, json={"name": f"Co {ticker}", "ticker": ticker}
    )

    assert response.status_code == 201
    assert response.json()["ticker"] == ticker


@pytest.mark.asyncio
@pytest.mark.parametrize("ticker", VALID_TICKERS)
async def test_valid_tickers_are_accepted_by_fetch_company(client, ticker):
    client.app.dependency_overrides[get_yahoo_finance_collector] = (
        lambda: PayloadCollector(
            {"name": f"Fetched {ticker}", "currency": "USD"}
        )
    )

    response = await client.post(FETCH, json={"ticker": ticker})

    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_create_strips_and_uppercases_ticker(client):
    response = await client.post(
        COMPANIES, json={"name": "Orlen", "ticker": "  pkn.wa  "}
    )

    assert response.status_code == 201
    assert response.json()["ticker"] == "PKN.WA"


@pytest.mark.asyncio
async def test_fetch_strips_and_uppercases_ticker(client):
    client.app.dependency_overrides[get_yahoo_finance_collector] = (
        lambda: PayloadCollector({"name": "Orlen", "currency": "USD"})
    )

    response = await client.post(FETCH, json={"ticker": "  pkn.wa  "})

    assert response.status_code == 200
    stored = await client.get(COMPANIES)
    tickers = [row["ticker"] for row in stored.json()]
    assert tickers == ["PKN.WA"]


@pytest.mark.asyncio
@pytest.mark.parametrize("ticker", CONTROL_TICKERS)
async def test_control_character_ticker_is_rejected_on_create(client, ticker):
    before = _count(client)

    response = await client.post(
        COMPANIES, json={"name": "C", "ticker": ticker}
    )

    assert response.status_code == 422
    assert _count(client) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("ticker", CONTROL_TICKERS)
async def test_control_character_ticker_is_rejected_by_fetch_company(
    client, ticker
):
    client.app.dependency_overrides[get_yahoo_finance_collector] = (
        lambda: PayloadCollector({"name": "C", "currency": "USD"})
    )
    before = _count(client)

    response = await client.post(FETCH, json={"ticker": ticker})

    assert response.status_code == 422
    assert _count(client) == before


@pytest.mark.asyncio
async def test_fetch_financial_metrics_rejects_control_character_ticker(
    client,
):
    response = await client.post(
        FETCH_METRICS, json={"ticker": "AAPL\nINFO forged"}
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_blank_ticker_is_rejected_on_update(client):
    created = (
        await client.post(COMPANIES, json={"name": "Keep", "ticker": "KEEP"})
    ).json()
    url = f"/api/v1/companies/{created['id']}"

    response = await client.put(url, json={"ticker": "   "})

    assert response.status_code == 422
    assert (await client.get(url)).json()["ticker"] == "KEEP"


@pytest.mark.asyncio
async def test_ticker_longer_than_the_column_is_rejected(client):
    accepted = await client.post(
        COMPANIES, json={"name": "Twenty", "ticker": "A" * 20}
    )
    rejected = await client.post(
        COMPANIES, json={"name": "Twenty One", "ticker": "B" * 21}
    )

    assert accepted.status_code == 201
    assert rejected.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field, value",
    [
        ("name", "N" * 300),
        ("currency", "USDD"),
        ("currency", "US"),
        ("sector", "S" * 101),
        ("industry", "I" * 101),
        ("country", "C" * 101),
        ("exchange", "E" * 51),
        ("website", "https://example.com/" + ("a" * 500)),
    ],
)
async def test_overlong_company_fields_are_422_on_create(client, field, value):
    payload = {"name": "C", "ticker": "LEN1", field: value}
    if field == "name":
        payload["name"] = value

    response = await client.post(COMPANIES, json=payload)

    assert response.status_code == 422
    assert _count(client) == 0


@pytest.mark.asyncio
async def test_overlong_name_is_422_on_update(client):
    created = (
        await client.post(COMPANIES, json={"name": "Short", "ticker": "SHRT"})
    ).json()
    url = f"/api/v1/companies/{created['id']}"

    response = await client.put(url, json={"name": "N" * 300})

    assert response.status_code == 422
    assert (await client.get(url)).json()["name"] == "Short"


@pytest.mark.asyncio
async def test_currency_is_normalized_to_three_uppercase_letters(client):
    response = await client.post(
        COMPANIES,
        json={"name": "Dollar", "ticker": "USDX", "currency": "usd"},
    )

    assert response.status_code == 201
    assert response.json()["currency"] == "USD"


@pytest.mark.asyncio
async def test_period_type_longer_than_the_column_is_422(client):
    company = (
        await client.post(COMPANIES, json={"name": "P", "ticker": "PERD"})
    ).json()

    response = await client.post(
        METRICS,
        json={
            "company_id": company["id"],
            "period_type": "Q" * 21,
            "period_end": "2025-12-31T00:00:00Z",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_provider_validation_error_is_502_without_input(client, caplog):
    """QA repro: a bad provider website must not be echoed to the client."""
    secret = "not a url secret=abc"
    client.app.dependency_overrides[get_yahoo_finance_collector] = (
        lambda: PayloadCollector(
            {"name": "Secret Co", "website": secret, "currency": "USD"}
        )
    )

    with caplog.at_level(logging.ERROR, logger="app.api.data_collection"):
        response = await client.post(FETCH, json={"ticker": "AAPL"})

    assert response.status_code == 502
    assert (
        response.json()["detail"] == "Provider returned invalid company data"
    )
    assert secret not in response.text
    assert "secret=abc" not in response.text
    assert "AAPL" in caplog.text
    assert "website" in caplog.text
    assert "secret=abc" not in caplog.text
    assert _count(client) == 0


@pytest.mark.asyncio
async def test_provider_overlong_name_is_502(client):
    long_name = "N" * 300
    client.app.dependency_overrides[get_yahoo_finance_collector] = (
        lambda: PayloadCollector({"name": long_name, "currency": "USD"})
    )

    response = await client.post(FETCH, json={"ticker": "LONG"})

    assert response.status_code == 502
    assert (
        response.json()["detail"] == "Provider returned invalid company data"
    )
    assert long_name not in response.text
    assert _count(client) == 0


@pytest.mark.asyncio
async def test_provider_bad_currency_is_502(client):
    client.app.dependency_overrides[get_yahoo_finance_collector] = (
        lambda: PayloadCollector({"name": "Ok", "currency": "USDD"})
    )

    response = await client.post(FETCH, json={"ticker": "CURR"})

    assert response.status_code == 502
    assert (
        response.json()["detail"] == "Provider returned invalid company data"
    )
    assert "USDD" not in response.text


@pytest.mark.asyncio
async def test_failed_update_returns_fixed_500(client, monkeypatch, caplog):
    """Repository update returning None is a fixed 500, with a server log."""
    await client.post(COMPANIES, json={"name": "Exists", "ticker": "EXST"})

    def update_returns_none(self, company_id, company_update):
        return None

    monkeypatch.setattr(CompanyRepository, "update", update_returns_none)
    client.app.dependency_overrides[get_yahoo_finance_collector] = (
        lambda: PayloadCollector({"name": "Exists", "currency": "USD"})
    )

    with caplog.at_level(logging.ERROR, logger="app.api.data_collection"):
        response = await client.post(FETCH, json={"ticker": "EXST"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to update company"}
    assert "Traceback" not in response.text
    assert "EXST" in caplog.text


@pytest.mark.asyncio
async def test_company_name_with_newline_does_not_forge_a_log_line(
    client, caplog
):
    """A newline in the provider name must stay inside one log record."""
    name = "Acme\nINFO forged-admin-login"
    client.app.dependency_overrides[get_yahoo_finance_collector] = (
        lambda: PayloadCollector({"name": name, "currency": "USD"})
    )

    with caplog.at_level(logging.INFO, logger="app.api.data_collection"):
        created = await client.post(FETCH, json={"ticker": "ACME"})
        updated = await client.post(FETCH, json={"ticker": "ACME"})

    assert created.status_code == 200
    assert updated.status_code == 200
    _assert_no_forged_log_line(caplog, "forged-admin-login")


def test_yahoo_error_text_with_newline_does_not_forge_a_log_line(
    monkeypatch, caplog
):
    class _Boom:
        def __init__(self, symbol):
            raise RuntimeError("provider down\nINFO forged-admin-login")

    monkeypatch.setattr(yahoo_finance.yf, "Ticker", _Boom)
    with caplog.at_level(logging.ERROR, logger=yahoo_finance.__name__):
        assert YahooFinanceCollector().fetch_company_info("FAIL") is None

    _assert_no_forged_log_line(caplog, "forged-admin-login")


def test_yahoo_logs_do_not_split_on_a_newline_ticker(monkeypatch, caplog):
    class _Info:
        def __init__(self, symbol):
            self.info = {"longName": "Acme", "currency": "USD"}

    monkeypatch.setattr(yahoo_finance.yf, "Ticker", _Info)
    ticker = "ACME\nINFO forged-admin-login"
    with caplog.at_level(logging.INFO, logger=yahoo_finance.__name__):
        info = YahooFinanceCollector().fetch_company_info(ticker)

    assert info is not None
    _assert_no_forged_log_line(caplog, "forged-admin-login")


def test_yahoo_error_log_does_not_split_on_a_newline_ticker(
    monkeypatch, caplog
):
    class _Boom:
        def __init__(self, symbol):
            raise RuntimeError("provider down")

    monkeypatch.setattr(yahoo_finance.yf, "Ticker", _Boom)
    ticker = "ACME\nINFO forged-admin-login"
    with caplog.at_level(logging.INFO, logger=yahoo_finance.__name__):
        assert YahooFinanceCollector().fetch_company_info(ticker) is None

    _assert_no_forged_log_line(caplog, "forged-admin-login")


# These two call the route with model_construct so the log lines run
# even after request validation starts rejecting control characters.
def test_data_collection_logs_do_not_split_on_a_newline_ticker(client, caplog):
    request = FetchCompanyRequest.model_construct(
        ticker="ACME\nINFO forged-admin-login"
    )
    session = client.app.state.testing_session_local()
    try:
        with caplog.at_level(logging.INFO, logger="app.api.data_collection"):
            try:
                fetch_company_data(
                    request,
                    db=session,
                    collector=PayloadCollector(
                        {"name": "Acme", "currency": "USD"}
                    ),
                )
            except Exception:
                pass
    finally:
        session.close()

    # fetch_company_data uppercases the ticker before it logs.
    _assert_no_forged_log_line(caplog, "FORGED-ADMIN-LOGIN")
    assert any(
        "FORGED-ADMIN-LOGIN" in record.getMessage()
        for record in caplog.records
    )


def test_data_collection_update_and_error_logs_do_not_split(
    client, caplog, monkeypatch
):
    """Update and exception logs stay one line when the ticker has a newline.

    The row is inserted past the model so this does not depend on the
    request schema. The collector then raises so the 500 log runs too.
    """
    session = client.app.state.testing_session_local()
    malicious = "ACME\nINFO forged-admin-login"
    session.add(CompanyDB(name="Acme", ticker=malicious, currency="USD"))
    session.commit()
    session.close()

    class _Boom:
        def fetch_company_info(self, ticker):
            raise RuntimeError("provider down")

    request = FetchCompanyRequest.model_construct(ticker=malicious)
    session = client.app.state.testing_session_local()
    try:
        with caplog.at_level(logging.INFO, logger="app.api.data_collection"):
            try:
                fetch_company_data(request, db=session, collector=_Boom())
            except Exception:
                pass
    finally:
        session.close()

    # The boom happens before the update log. This test pins the
    # exception log. fetch_company_data uppercases the ticker first.
    _assert_no_forged_log_line(caplog, "FORGED-ADMIN-LOGIN")
