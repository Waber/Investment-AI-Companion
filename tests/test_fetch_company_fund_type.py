"""fetch-company stores the provider's instrument type and fund facts.

The fake collector and stub collectors replace Yahoo, so no test
touches the network.
"""

from datetime import date, datetime, timezone

import pytest

from app.api.data_collection import get_collector
from app.data_collectors.base import (
    Provenance,
    ProviderError,
    Sourced,
    TransientProviderError,
)

URL = "/api/v1/data-collection/fetch-company"
RETRIEVED = datetime(2026, 11, 27, 9, 0, tzinfo=timezone.utc)
DAY = RETRIEVED.date()
ETF_FACTS = {
    "fund_type": "ETF",
    "ter": 0.000945,
    "aum": 796865200128.0,
    "aum_currency": "USD",
    "aum_as_of": DAY,
    "issuer": "State Street Investment Management",
    "underlying": None,
    "domicile": None,
    "replication_method": None,
    "distribution_policy": None,
}


def _provenance():
    return Provenance(
        source="yahoo_finance", retrieved_at=RETRIEVED, as_of=DAY
    )


class StubCollector:
    """A provider that names a type and serves fund facts or fails."""

    def __init__(
        self,
        instrument_type="ETF",
        facts=ETF_FACTS,
        error=None,
        provenance=None,
    ):
        self.instrument_type = instrument_type
        self.facts = facts
        self.error = error
        self.provenance = provenance or _provenance()
        self.fund_calls = 0

    def fetch_company_info(self, ticker):
        return Sourced(
            {
                "name": "SPDR S&P 500 ETF Trust",
                "currency": "USD",
                "instrument_type": self.instrument_type,
            },
            _provenance(),
        )

    def fetch_fund_attributes(self, ticker):
        self.fund_calls += 1
        if self.error is not None:
            raise self.error
        if self.facts is None:
            return None
        return Sourced(dict(self.facts), self.provenance)


def _use(client, collector):
    client.app.dependency_overrides[get_collector] = lambda: collector


async def _fetch(client, ticker="SPY"):
    response = await client.post(URL, json={"ticker": ticker})
    assert response.status_code == 200, response.text
    return response.json()


async def _instrument(client, company_id):
    response = await client.get(f"/api/v1/instruments/{company_id}")
    assert response.status_code == 200
    return response.json()


async def _attributes(client, company_id):
    response = await client.get(
        f"/api/v1/instruments/{company_id}/fund-attributes"
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_an_etf_is_stored_as_etf_with_its_facts(client):
    _use(client, StubCollector())

    payload = await _fetch(client)

    assert payload["instrument_type"] == "ETF"
    assert payload["fund_attributes"] == "created"
    company_id = payload["company_id"]
    assert (await _instrument(client, company_id))["instrument_type"] == "ETF"
    row = await _attributes(client, company_id)
    assert row["ter"] == 0.000945
    assert row["aum"] == 796865200128.0
    assert row["aum_currency"] == "USD"
    assert row["aum_as_of"] == DAY.isoformat()
    assert row["issuer"] == "State Street Investment Management"
    assert row["as_of"] == DAY.isoformat()
    assert row["source"] == "yahoo_finance"
    assert row["is_synthetic"] is False


@pytest.mark.asyncio
async def test_a_second_fetch_refreshes_the_collector_row(client):
    _use(client, StubCollector())
    first = await _fetch(client)
    _use(client, StubCollector(facts={**ETF_FACTS, "ter": 0.0009}))

    second = await _fetch(client)

    assert second["company_id"] == first["company_id"]
    assert second["fund_attributes"] == "updated"
    assert (await _attributes(client, first["company_id"]))["ter"] == 0.0009


@pytest.mark.asyncio
async def test_a_manual_fund_row_is_kept(client):
    _use(client, StubCollector())
    company_id = (await _fetch(client))["company_id"]
    await client.delete(f"/api/v1/instruments/{company_id}/fund-attributes")
    created = await client.post(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json={"ter": 0.002, "as_of": "2026-11-01"},
    )
    assert created.status_code == 201

    payload = await _fetch(client)

    assert payload["fund_attributes"] == "kept"
    row = await _attributes(client, company_id)
    assert row["source"] == "manual"
    assert row["ter"] == 0.002


@pytest.mark.asyncio
async def test_a_stock_gets_no_fund_attributes(client):
    _use(client, StubCollector(instrument_type="STOCK"))

    payload = await _fetch(client, "AAPL")

    assert payload["instrument_type"] == "STOCK"
    assert payload["fund_attributes"] is None
    assert await _attributes(client, payload["company_id"]) is None


@pytest.mark.asyncio
async def test_an_unknown_provider_type_is_stored_as_stock(client):
    _use(client, StubCollector(instrument_type=None))

    payload = await _fetch(client)

    assert payload["instrument_type"] == "STOCK"
    assert payload["fund_attributes"] is None


@pytest.mark.asyncio
async def test_a_refresh_never_changes_a_stored_stock(client):
    # The type is app-owned after create (docs/product-requirements.md):
    # Yahoo's quoteType is only the starting value. VWCE.DE, stored as
    # STOCK before this change, is set to ETF once on the edit form.
    _use(client, StubCollector(instrument_type="STOCK"))
    company_id = (await _fetch(client))["company_id"]
    later = StubCollector(instrument_type="ETF")
    _use(client, later)

    payload = await _fetch(client)

    assert payload["company_id"] == company_id
    assert payload["instrument_type"] == "STOCK"
    assert payload["fund_attributes"] is None
    assert later.fund_calls == 0
    assert (await _instrument(client, company_id))[
        "instrument_type"
    ] == "STOCK"


@pytest.mark.asyncio
async def test_a_stock_set_to_etf_by_hand_gets_fund_facts(client):
    _use(client, StubCollector(instrument_type="STOCK"))
    company_id = (await _fetch(client))["company_id"]
    edited = await client.put(
        f"/api/v1/companies/{company_id}", json={"instrument_type": "ETF"}
    )
    assert edited.status_code == 200
    _use(client, StubCollector(instrument_type="ETF"))

    payload = await _fetch(client)

    assert payload["instrument_type"] == "ETF"
    assert payload["fund_attributes"] == "created"


@pytest.mark.parametrize("provider_type", ["STOCK", "ETF", None])
@pytest.mark.asyncio
async def test_a_refresh_keeps_an_etc_set_by_hand(client, provider_type):
    # Yahoo labels an ETC as EQUITY, so the owner sets ETC on the form.
    _use(client, StubCollector(instrument_type="STOCK"))
    company_id = (await _fetch(client, "4GLD.DE"))["company_id"]
    edited = await client.put(
        f"/api/v1/companies/{company_id}", json={"instrument_type": "ETC"}
    )
    assert edited.status_code == 200
    _use(client, StubCollector(instrument_type=provider_type, facts=None))

    payload = await _fetch(client, "4GLD.DE")

    assert payload["instrument_type"] == "ETC"
    assert payload["fund_attributes"] == "unavailable"
    assert (await _instrument(client, company_id))["instrument_type"] == "ETC"


@pytest.mark.parametrize(
    ("error", "status"),
    [
        # Try again later: the provider failed (rate limit, timeout, ...).
        (ProviderError("down"), "provider_error"),
        (TransientProviderError("rate limited"), "provider_error"),
        # A bug in the adapter is not the provider's failure.
        (RuntimeError("bug in adapter"), "unavailable"),
    ],
)
@pytest.mark.asyncio
async def test_a_fund_fact_failure_keeps_the_saved_company(
    client, error, status
):
    _use(client, StubCollector(error=error))

    payload = await _fetch(client)

    assert payload["success"] is True
    assert payload["instrument_type"] == "ETF"
    assert payload["fund_attributes"] == status
    assert await _attributes(client, payload["company_id"]) is None


@pytest.mark.parametrize(
    "facts",
    [
        # TER above 100 percent is not a real fee.
        {**ETF_FACTS, "ter": 5.0},
        # AUM without a currency breaks the AUM trio rule.
        {**ETF_FACTS, "aum_currency": None},
        # A newline in a text fact fails clean_text.
        {**ETF_FACTS, "issuer": "Issuer\nInjected"},
    ],
)
@pytest.mark.asyncio
async def test_bad_provider_facts_store_nothing(client, facts):
    _use(client, StubCollector(facts=facts))

    payload = await _fetch(client)

    assert payload["fund_attributes"] == "unavailable"
    assert await _attributes(client, payload["company_id"]) is None


@pytest.mark.asyncio
async def test_a_snapshot_without_facts_stores_nothing(client):
    empty = dict.fromkeys(ETF_FACTS)
    empty["fund_type"] = "ETF"
    _use(client, StubCollector(facts=empty))

    payload = await _fetch(client)

    assert payload["fund_attributes"] == "unavailable"
    assert await _attributes(client, payload["company_id"]) is None


@pytest.mark.asyncio
async def test_a_collector_without_fund_facts_still_types_the_etf(client):
    class TypeOnly:
        def fetch_company_info(self, ticker):
            return StubCollector().fetch_company_info(ticker)

    _use(client, TypeOnly())

    payload = await _fetch(client)

    assert payload["instrument_type"] == "ETF"
    assert payload["fund_attributes"] == "unavailable"


@pytest.mark.parametrize(
    ("ticker", "expected_type", "ter"),
    [("DEMO_ETF_WORLD", "ETF", 0.0022), ("DEMO_ETC_GOLD", "ETC", 0.0015)],
)
@pytest.mark.asyncio
async def test_the_fake_collector_stores_synthetic_fund_rows(
    client, ticker, expected_type, ter
):
    # conftest sets DATA_COLLECTOR=fake, so no override is needed.
    payload = await _fetch(client, ticker)

    assert payload["instrument_type"] == expected_type
    assert payload["fund_attributes"] == "created"
    row = await _attributes(client, payload["company_id"])
    assert row["ter"] == ter
    assert row["source"] == "fake"
    assert row["is_synthetic"] is True
    assert row["as_of"] == date(2026, 9, 30).isoformat()


@pytest.mark.parametrize("provider_type", ["ETC", "STOCK", None])
@pytest.mark.asyncio
async def test_a_refresh_never_changes_a_stored_etf(client, provider_type):
    _use(client, StubCollector(instrument_type="ETF"))
    company_id = (await _fetch(client))["company_id"]
    _use(client, StubCollector(instrument_type=provider_type))

    payload = await _fetch(client)

    assert payload["instrument_type"] == "ETF"
    assert (await _instrument(client, company_id))["instrument_type"] == "ETF"


@pytest.mark.parametrize(
    ("later", "status"),
    [
        (StubCollector(facts=None), "unavailable"),
        (
            StubCollector(
                facts={**dict.fromkeys(ETF_FACTS), "fund_type": "ETF"}
            ),
            "unavailable",
        ),
        (StubCollector(facts={**ETF_FACTS, "ter": 5.0}), "unavailable"),
        (StubCollector(error=ProviderError("down")), "provider_error"),
    ],
    ids=["no-data", "no-facts", "bad-facts", "provider-error"],
)
@pytest.mark.asyncio
async def test_an_unavailable_refresh_keeps_the_earlier_row(
    client, later, status
):
    _use(client, StubCollector())
    company_id = (await _fetch(client))["company_id"]
    before = await _attributes(client, company_id)
    _use(client, later)

    payload = await _fetch(client)

    assert payload["fund_attributes"] == status
    assert await _attributes(client, company_id) == before


@pytest.mark.parametrize(
    ("as_of", "stored"),
    [(date(2026, 11, 20), "2026-11-20"), (None, DAY.isoformat())],
)
@pytest.mark.asyncio
async def test_the_row_is_dated_by_the_provider_then_by_retrieval(
    client, as_of, stored
):
    provenance = Provenance(
        source="yahoo_finance", retrieved_at=RETRIEVED, as_of=as_of
    )
    _use(client, StubCollector(provenance=provenance))

    payload = await _fetch(client)

    assert (await _attributes(client, payload["company_id"]))[
        "as_of"
    ] == stored


@pytest.mark.parametrize("provider_type", ["STOCK", "ETF"])
@pytest.mark.asyncio
async def test_a_manual_row_is_kept_without_asking_the_provider(
    client, provider_type
):
    # An ETC set by hand with a TER typed in: Yahoo says EQUITY and has
    # no fund facts, and the answer is still "kept", not "unavailable".
    _use(client, StubCollector(instrument_type="STOCK"))
    company_id = (await _fetch(client, "4GLD.DE"))["company_id"]
    await client.put(
        f"/api/v1/companies/{company_id}", json={"instrument_type": "ETC"}
    )
    created = await client.post(
        f"/api/v1/instruments/{company_id}/fund-attributes",
        json={"ter": 0.0036, "as_of": "2026-11-01"},
    )
    assert created.status_code == 201
    later = StubCollector(instrument_type=provider_type, facts=None)
    _use(client, later)

    payload = await _fetch(client, "4GLD.DE")

    assert payload["fund_attributes"] == "kept"
    assert later.fund_calls == 0
    assert (await _attributes(client, company_id))["ter"] == 0.0036


@pytest.mark.asyncio
async def test_the_fake_collector_refreshes_its_own_row(client):
    first = await _fetch(client, "DEMO_ETF_WORLD")

    second = await _fetch(client, "DEMO_ETF_WORLD")

    assert first["fund_attributes"] == "created"
    assert second["fund_attributes"] == "updated"


@pytest.mark.parametrize("source", ["demo", "fixture"])
@pytest.mark.asyncio
async def test_a_seeded_row_is_kept_without_asking_the_provider(
    client, source
):
    from app.models.fund_attributes import FundAttributesCreate
    from app.repositories.fund_attributes_repository import (
        FundAttributesRepository,
    )

    _use(client, StubCollector(facts=None))
    company_id = (await _fetch(client))["company_id"]
    session = client.app.state.testing_session_local()
    try:
        FundAttributesRepository(session).create(
            company_id,
            FundAttributesCreate(ter=0.002, as_of="2026-09-30"),
            record_source=source,
            is_synthetic=True,
        )
    finally:
        session.close()
    later = StubCollector(error=ProviderError("down"))
    _use(client, later)

    payload = await _fetch(client)

    assert payload["fund_attributes"] == "kept"
    assert later.fund_calls == 0


@pytest.mark.asyncio
async def test_another_collectors_row_is_kept(client):
    fake = Provenance(
        source="fake", retrieved_at=RETRIEVED, as_of=DAY, synthetic=True
    )
    _use(client, StubCollector(provenance=fake))
    company_id = (await _fetch(client))["company_id"]
    before = await _attributes(client, company_id)
    _use(client, StubCollector(facts={**ETF_FACTS, "ter": 0.0009}))

    payload = await _fetch(client)

    assert payload["fund_attributes"] == "kept"
    assert await _attributes(client, company_id) == before


class SaveDuringCall(StubCollector):
    """The owner saves the fund form while the provider call runs."""

    def __init__(self, session_factory, company_id):
        super().__init__(facts={**ETF_FACTS, "ter": 0.0009})
        self.session_factory = session_factory
        self.company_id = company_id

    def fetch_fund_attributes(self, ticker):
        from app.models.fund_attributes import FundAttributesUpdate
        from app.repositories.fund_attributes_repository import (
            FundAttributesRepository,
        )

        other = self.session_factory()
        try:
            FundAttributesRepository(other).update(
                self.company_id, FundAttributesUpdate(ter=0.0036)
            )
        finally:
            other.close()
        return super().fetch_fund_attributes(ticker)


@pytest.mark.asyncio
async def test_a_manual_save_during_the_provider_call_is_kept(client):
    _use(client, StubCollector())
    company_id = (await _fetch(client))["company_id"]
    factory = client.app.state.testing_session_local
    _use(client, SaveDuringCall(factory, company_id))

    payload = await _fetch(client)

    stored = await _attributes(client, company_id)
    assert payload["fund_attributes"] == "kept"
    assert stored["ter"] == 0.0036
    assert stored["source"] == "manual"
