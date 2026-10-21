"""Price bars: store, query by range, and refresh without duplicates.

The collector used here is the offline fake, or a stub that returns
bars in memory. Nothing in this file calls a market-data provider.
"""

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.api.data_collection import get_collector
from app.data_collectors.base import PriceBar as CollectedPriceBar
from app.data_collectors.base import Provenance, ProviderError, Sourced
from app.data_collectors.fake import FakeCollector
from app.models.price_bar import PriceBarCreate

RETRIEVED = datetime(2026, 9, 30, 18, 0, tzinfo=timezone.utc)


def _bar(**overrides):
    payload = {
        "date": "2026-01-05",
        "open": 10.0,
        "high": 12.0,
        "low": 9.0,
        "close": 11.0,
        "volume": 100,
        "currency": "PLN",
        "source": "[IAC-DEMO-V2]",
        "retrieved_at": "2026-09-30T18:00:00Z",
    }
    payload.update(overrides)
    return payload


async def _company(client, ticker="DEMO_PL_TECH", currency="PLN"):
    response = await client.post(
        "/api/v1/companies/",
        json={
            "name": "Synthetic " + ticker,
            "ticker": ticker,
            "currency": currency,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


class _StubCollector:
    """Returns the bars it was given. No network and no fixture file."""

    def __init__(self, bars, *, source="stub", retrieved_at=RETRIEVED):
        self.bars = bars
        self.source = source
        self.retrieved_at = retrieved_at
        self.calls = 0

    def fetch_price_history(self, ticker, period="1y", interval="1d"):
        self.calls += 1
        if self.bars is None:
            return None
        provenance = Provenance(
            source=self.source,
            retrieved_at=self.retrieved_at,
            as_of=self.bars[-1].day if self.bars else None,
            synthetic=True,
        )
        return Sourced(list(self.bars), provenance)


def _use(client, collector):
    client.app.dependency_overrides[get_collector] = lambda: collector


@pytest.mark.asyncio
async def test_range_is_inclusive_and_carries_provenance(client):
    instrument_id = await _company(client)
    created = await client.post(
        f"/api/v1/instruments/{instrument_id}/prices",
        json=_bar(),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["instrument_id"] == instrument_id
    assert body["date"] == "2026-01-05"
    assert body["source"] == "[IAC-DEMO-V2]"
    assert body["retrieved_at"].startswith("2026-09-30T18:00:00")
    assert body["currency"] == "PLN"
    assert body["volume"] == 100

    inside = await client.get(
        f"/api/v1/instruments/{instrument_id}/prices",
        params={"from": "2026-01-05", "to": "2026-01-05"},
    )
    assert inside.status_code == 200
    assert [row["id"] for row in inside.json()] == [body["id"]]

    before = await client.get(
        f"/api/v1/instruments/{instrument_id}/prices",
        params={"to": "2026-01-04"},
    )
    assert before.json() == []
    after = await client.get(
        f"/api/v1/instruments/{instrument_id}/prices",
        params={"from": "2026-01-06"},
    )
    assert after.json() == []


@pytest.mark.asyncio
async def test_missing_instrument_is_404_and_empty_series_is_200(client):
    missing = await client.get("/api/v1/instruments/999/prices")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Instrument not found"

    instrument_id = await _company(client, ticker="DEMO_PL_EMPTY")
    empty = await client.get(f"/api/v1/instruments/{instrument_id}/prices")
    assert empty.status_code == 200
    assert empty.json() == []


@pytest.mark.asyncio
async def test_inverted_range_is_422(client):
    instrument_id = await _company(client)
    response = await client.get(
        f"/api/v1/instruments/{instrument_id}/prices",
        params={"from": "2026-02-01", "to": "2026-01-01"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_null_volume_is_stored_as_null_and_duplicate_is_400(client):
    instrument_id = await _company(client)
    path = f"/api/v1/instruments/{instrument_id}/prices"
    created = await client.post(path, json=_bar(volume=None, close=None))
    assert created.status_code == 201, created.text
    assert created.json()["volume"] is None
    assert created.json()["close"] is None

    again = await client.post(path, json=_bar(volume=None, close=None))
    assert again.status_code == 400
    listed = await client.get(path)
    assert len(listed.json()) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"open": 10.0, "high": 9.0, "low": None, "close": None},
            "high must be greater than or equal to open",
        ),
        (
            {"open": None, "high": 9.0, "low": None, "close": 10.0},
            "high must be greater than or equal to close",
        ),
        (
            {"open": 8.0, "high": None, "low": 9.0, "close": None},
            "low must be less than or equal to open",
        ),
        (
            {"open": None, "high": None, "low": 9.0, "close": 8.0},
            "low must be less than or equal to close",
        ),
        (
            {"open": None, "high": 1.0, "low": 2.0, "close": None},
            "high must be greater than or equal to low",
        ),
        (
            {"volume": -1},
            "volume must be zero or greater",
        ),
    ],
)
async def test_candle_violation_is_422(client, overrides, message):
    """Each broken bound is rejected, and nothing is stored."""
    instrument_id = await _company(client, ticker="DEMO_CANDLE")
    path = f"/api/v1/instruments/{instrument_id}/prices"
    response = await client.post(path, json=_bar(**overrides))
    assert response.status_code == 422
    assert message in response.text
    listed = await client.get(path)
    assert listed.json() == []


@pytest.mark.asyncio
async def test_flat_bar_and_a_boolean_volume_are_handled(client):
    """Equal prices and a zero volume are a valid session.

    A JSON boolean is still not a volume. ``True`` must not become 1.
    """
    instrument_id = await _company(client, ticker="DEMO_FLAT")
    path = f"/api/v1/instruments/{instrument_id}/prices"
    flat = await client.post(
        path,
        json=_bar(open=10.0, high=10.0, low=10.0, close=10.0, volume=0),
    )
    assert flat.status_code == 201, flat.text
    boolean = await client.post(
        path, json=_bar(volume=True, date="2026-01-12")
    )
    assert boolean.status_code == 422
    listed = await client.get(path)
    assert len(listed.json()) == 1
    assert listed.json()[0]["volume"] == 0


def test_price_model_rejects_nan_and_a_blank_source():
    with pytest.raises(ValidationError):
        PriceBarCreate(**_bar(close=float("nan")))
    with pytest.raises(ValidationError):
        PriceBarCreate(**_bar(source="   "))
    with pytest.raises(ValidationError):
        PriceBarCreate(**_bar(source=12))
    with pytest.raises(ValidationError):
        PriceBarCreate(**_bar(volume=2**63))


@pytest.mark.asyncio
async def test_sqlite_stores_a_volume_above_int32(client):
    """3_000_000_000 fits in BIGINT and in the Pydantic cap."""
    instrument_id = await _company(client, ticker="DEMO_BIG_VOL")
    path = f"/api/v1/instruments/{instrument_id}/prices"
    created = await client.post(path, json=_bar(volume=3_000_000_000))
    assert created.status_code == 201, created.text
    assert created.json()["volume"] == 3_000_000_000


@pytest.mark.asyncio
async def test_default_list_is_one_source(client):
    """Two sources on one date do not both come back by default.

    The later retrieval wins. The same retrieval time keeps the
    source name that sorts last. ``source`` reads the other series.
    """
    instrument_id = await _company(client, ticker="DEMO_TWO_SRC")
    path = f"/api/v1/instruments/{instrument_id}/prices"
    older = await client.post(
        path,
        json=_bar(source="[IAC-DEMO-V2]", retrieved_at="2026-09-30T18:00:00Z"),
    )
    assert older.status_code == 201, older.text
    newer = await client.post(
        path,
        json=_bar(source="fake", retrieved_at="2026-10-01T18:00:00Z"),
    )
    assert newer.status_code == 201, newer.text

    listed = await client.get(path)
    assert [row["source"] for row in listed.json()] == ["fake"]
    demo = await client.get(path, params={"source": "[IAC-DEMO-V2]"})
    assert [row["source"] for row in demo.json()] == ["[IAC-DEMO-V2]"]

    tied = await client.post(
        path,
        json=_bar(
            date="2026-01-12",
            source="aaa",
            retrieved_at="2026-10-02T18:00:00Z",
        ),
    )
    assert tied.status_code == 201, tied.text
    other = await client.post(
        path,
        json=_bar(
            date="2026-01-12",
            source="zzz",
            retrieved_at="2026-10-02T18:00:00Z",
        ),
    )
    assert other.status_code == 201, other.text
    that_day = await client.get(
        path, params={"from": "2026-01-12", "to": "2026-01-12"}
    )
    assert [row["source"] for row in that_day.json()] == ["zzz"]
    blank = await client.get(path, params={"source": "   "})
    assert blank.status_code == 422


@pytest.mark.asyncio
async def test_default_source_is_chosen_before_the_date_filter(client):
    """A date window must not switch the default source.

    The newest retrieval is a ``fake`` bar in 2026. Inside 2024 the
    demo bar was retrieved later than the ``fake`` bar on that same
    day. Choosing the source after the date filter would return the
    demo series. The source is chosen from every bar first, so the
    2024 window stays on ``fake``. A window that has only the demo
    series is empty.
    """
    instrument_id = await _company(client, ticker="DEMO_SRC_RANGE")
    path = f"/api/v1/instruments/{instrument_id}/prices"
    latest = await client.post(
        path,
        json=_bar(
            date="2026-01-05",
            source="fake",
            retrieved_at="2026-10-02T18:00:00Z",
        ),
    )
    assert latest.status_code == 201, latest.text
    demo = await client.post(
        path,
        json=_bar(
            date="2024-06-03",
            source="[IAC-DEMO-V2]",
            retrieved_at="2026-10-01T18:00:00Z",
        ),
    )
    assert demo.status_code == 201, demo.text
    older_fake = await client.post(
        path,
        json=_bar(
            date="2024-06-03",
            source="fake",
            retrieved_at="2024-01-01T18:00:00Z",
        ),
    )
    assert older_fake.status_code == 201, older_fake.text
    only_demo = await client.post(
        path,
        json=_bar(
            date="2023-01-02",
            source="[IAC-DEMO-V2]",
            retrieved_at="2023-01-02T18:00:00Z",
        ),
    )
    assert only_demo.status_code == 201, only_demo.text

    window = await client.get(
        path, params={"from": "2024-01-01", "to": "2024-12-31"}
    )
    assert window.status_code == 200
    assert [row["source"] for row in window.json()] == ["fake"]
    assert [row["date"] for row in window.json()] == ["2024-06-03"]

    named = await client.get(
        path,
        params={
            "from": "2024-01-01",
            "to": "2024-12-31",
            "source": "[IAC-DEMO-V2]",
        },
    )
    assert [row["source"] for row in named.json()] == ["[IAC-DEMO-V2]"]

    demo_only_window = await client.get(
        path, params={"from": "2023-01-01", "to": "2023-12-31"}
    )
    assert demo_only_window.status_code == 200
    assert demo_only_window.json() == []


@pytest.mark.asyncio
async def test_collector_validation_error_is_a_fixed_502(client):
    """A ValidationError raised by the collector is not a 422.

    ValidationError is a ValueError. The route must catch it first.
    The message contains the bad price, and the body must not.
    """
    instrument_id = await _company(client)

    class Invalid:
        def fetch_price_history(self, ticker, period="1y", interval="1d"):
            PriceBarCreate(**_bar(low=9.5, high=1.0, open=1.0, close=1.0))

    _use(client, Invalid())
    response = await client.post(
        f"/api/v1/instruments/{instrument_id}/prices/refresh"
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "Data provider error"
    assert "9.5" not in response.text
    listed = await client.get(f"/api/v1/instruments/{instrument_id}/prices")
    assert listed.json() == []


@pytest.mark.asyncio
async def test_refresh_twice_from_the_fake_collector_does_not_duplicate(
    client,
):
    """The acceptance check: two refreshes, one row per session."""
    instrument_id = await _company(
        client, ticker="DEMO_PL_TECH", currency="PLN"
    )
    path = f"/api/v1/instruments/{instrument_id}/prices/refresh"
    _use(client, FakeCollector())
    first = await client.post(path)
    assert first.status_code == 200, first.text
    assert first.json()["source"] == "fake"
    assert first.json()["bar_count"] > 0
    assert first.json()["retrieved_at"].startswith("2026-09-30T18:00:00")

    _use(client, FakeCollector())
    second = await client.post(path)
    assert second.status_code == 200
    assert second.json()["bar_count"] == first.json()["bar_count"]

    listed = await client.get(f"/api/v1/instruments/{instrument_id}/prices")
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == first.json()["bar_count"]
    assert {row["source"] for row in rows} == {"fake"}
    assert {row["currency"] for row in rows} == {"PLN"}
    dates = [row["date"] for row in rows]
    assert dates == sorted(dates)
    assert all(row["close"] is not None for row in rows)


@pytest.mark.asyncio
async def test_refresh_keeps_null_prices_and_a_different_source(client):
    instrument_id = await _company(client, ticker="DEMO_PL_TECH")
    seeded = await client.post(
        f"/api/v1/instruments/{instrument_id}/prices",
        json=_bar(date="2020-01-06"),
    )
    assert seeded.status_code == 201, seeded.text

    stub = _StubCollector(
        [
            CollectedPriceBar(date(2026, 1, 2), None, None, None, None, None),
        ]
    )
    _use(client, stub)
    refreshed = await client.post(
        f"/api/v1/instruments/{instrument_id}/prices/refresh"
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["bar_count"] == 1
    again = await client.post(
        f"/api/v1/instruments/{instrument_id}/prices/refresh"
    )
    assert again.json()["bar_count"] == 1

    listed = await client.get(f"/api/v1/instruments/{instrument_id}/prices")
    rows = listed.json()
    # Same retrieval time. The source name that sorts last is the
    # default series, so the list is not both sources at once.
    assert len(rows) == 1
    assert rows[0]["source"] == "stub"
    assert rows[0]["open"] is None
    assert rows[0]["close"] is None
    assert rows[0]["volume"] is None
    seeded_rows = await client.get(
        f"/api/v1/instruments/{instrument_id}/prices",
        params={"source": "[IAC-DEMO-V2]"},
    )
    assert [row["source"] for row in seeded_rows.json()] == ["[IAC-DEMO-V2]"]


@pytest.mark.asyncio
async def test_refresh_of_an_unknown_ticker_stores_nothing(client):
    instrument_id = await _company(client, ticker="DEMO_NO_BARS")
    _use(client, FakeCollector())
    response = await client.post(
        f"/api/v1/instruments/{instrument_id}/prices/refresh"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "No price data for this instrument"
    listed = await client.get(f"/api/v1/instruments/{instrument_id}/prices")
    assert listed.json() == []


@pytest.mark.asyncio
async def test_refresh_reports_collector_failures_without_their_text(client):
    """A provider failure is a fixed sentence. The cause stays out of it."""
    instrument_id = await _company(client)
    path = f"/api/v1/instruments/{instrument_id}/prices/refresh"

    class Unsupported:
        def fetch_price_history(self, ticker, period="1y", interval="1d"):
            raise ValueError("period secret-period is unsupported")

    _use(client, Unsupported())
    rejected = await client.post(path)
    assert rejected.status_code == 422
    assert rejected.json()["detail"] == "Unsupported price request"
    assert "secret-period" not in rejected.text

    class Broken:
        def fetch_price_history(self, ticker, period="1y", interval="1d"):
            raise RuntimeError("secret-runtime")

    _use(client, Broken())
    unexpected = await client.post(path)
    assert unexpected.status_code == 502
    assert unexpected.json()["detail"] == "Data provider error"
    assert "secret-runtime" not in unexpected.text

    class Empty:
        def fetch_price_history(self, ticker, period="1y", interval="1d"):
            provenance = Provenance(
                source="stub",
                retrieved_at=RETRIEVED,
                as_of=None,
                synthetic=True,
            )
            return Sourced([], provenance)

    _use(client, Empty())
    empty = await client.post(path)
    assert empty.status_code == 404
    assert empty.json()["detail"] == "No price data for this instrument"


@pytest.mark.asyncio
async def test_invalid_collector_bar_is_a_fixed_502(client):
    instrument_id = await _company(client)

    class Inverted:
        def fetch_price_history(self, ticker, period="1y", interval="1d"):
            provenance = Provenance(
                source="stub",
                retrieved_at=RETRIEVED,
                as_of=date(2026, 1, 2),
                synthetic=True,
            )
            # high below low. The numbers must not be copied into the body.
            bar = CollectedPriceBar(date(2026, 1, 2), 1.0, 1.0, 9.5, 1.0, 1)
            return Sourced([bar], provenance)

    _use(client, Inverted())
    response = await client.post(
        f"/api/v1/instruments/{instrument_id}/prices/refresh"
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "Provider returned invalid price data"
    assert "9.5" not in response.text
    listed = await client.get(f"/api/v1/instruments/{instrument_id}/prices")
    assert listed.json() == []


@pytest.mark.asyncio
async def test_refresh_uses_usd_when_the_instrument_has_no_currency(client):
    instrument_id = await _company(
        client, ticker="DEMO_NO_CCY", currency="USD"
    )
    with client.app.state.testing_session_local() as db:
        from app.models.database_models import CompanyDB

        row = db.get(CompanyDB, instrument_id)
        row.currency = None
        db.commit()
    _use(
        client,
        _StubCollector(
            [CollectedPriceBar(date(2026, 1, 2), 1.0, 1.0, 1.0, 1.0, 1)]
        ),
    )
    refreshed = await client.post(
        f"/api/v1/instruments/{instrument_id}/prices/refresh"
    )
    assert refreshed.status_code == 200, refreshed.text
    listed = await client.get(f"/api/v1/instruments/{instrument_id}/prices")
    assert listed.json()[0]["currency"] == "USD"


@pytest.mark.asyncio
async def test_provider_error_is_a_fixed_502(client):
    class Boom:
        def fetch_price_history(self, ticker, period="1y", interval="1d"):
            raise ProviderError("upstream secret text")

    instrument_id = await _company(client)
    _use(client, Boom())
    response = await client.post(
        f"/api/v1/instruments/{instrument_id}/prices/refresh"
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "Data provider error"
    assert "secret" not in response.text


def _race_repo():
    """A repository whose next commit raises, and a stored company."""
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core.database import Base, create_db_engine
    from app.models.database_models import CompanyDB
    from app.repositories.price_bar_repository import PriceBarRepository

    engine = create_db_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(
        CompanyDB(name="Synthetic", ticker="DEMO_RACE", currency="USD")
    )
    session.commit()
    instrument_id = session.query(CompanyDB).one().id
    repo = PriceBarRepository(session)

    def fail_commit():
        raise IntegrityError("INSERT", {}, Exception("duplicate key"))

    session.commit = fail_commit
    return engine, session, repo, instrument_id


def test_a_lost_insert_race_is_already_stored_when_the_row_remains():
    """The pre-check misses a row that is there after rollback.

    That row is a duplicate. The driver text is not the message, and
    it is not chained on ``__context__``.
    """
    engine, session, repo, instrument_id = _race_repo()
    try:
        bar = PriceBarCreate(**_bar())
        calls = {"count": 0}

        def hide_then_find(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                return None
            return object()

        repo.get_by_key = hide_then_find
        with pytest.raises(ValueError, match="already exists") as caught:
            repo.create(instrument_id, bar)
        assert "duplicate key" not in str(caught.value)
        assert caught.value.__context__ is None
        assert caught.value.__cause__ is None

        calls["count"] = 0
        with pytest.raises(ValueError, match="already exists") as upserted:
            repo.upsert_many(instrument_id, [bar])
        assert "duplicate key" not in str(upserted.value)
        assert upserted.value.__context__ is None
        assert upserted.value.__cause__ is None
    finally:
        session.close()
        engine.dispose()


def test_integrity_error_without_a_row_is_a_generic_constraint_error():
    """A failed commit that leaves no row is not reported as a duplicate."""
    engine, session, repo, instrument_id = _race_repo()
    try:
        bar = PriceBarCreate(**_bar())
        repo.get_by_key = lambda *args, **kwargs: None
        with pytest.raises(
            ValueError, match="^Price bar could not be stored$"
        ) as caught:
            repo.create(instrument_id, bar)
        assert caught.value.__context__ is None
        assert caught.value.__cause__ is None
        assert "duplicate key" not in str(caught.value)
        with pytest.raises(
            ValueError, match="^Price bar could not be stored$"
        ) as upserted:
            repo.upsert_many(instrument_id, [bar])
        assert upserted.value.__context__ is None
        assert upserted.value.__cause__ is None
        assert "duplicate key" not in str(upserted.value)
    finally:
        session.close()
        engine.dispose()


@pytest.mark.asyncio
async def test_deleting_the_instrument_deletes_its_bars(client):
    instrument_id = await _company(client)
    created = await client.post(
        f"/api/v1/instruments/{instrument_id}/prices",
        json=_bar(),
    )
    assert created.status_code == 201
    with client.app.state.testing_session_local() as db:
        from app.models.database_models import PriceBarDB

        assert db.query(PriceBarDB).count() == 1
    deleted = await client.delete(f"/api/v1/companies/{instrument_id}")
    assert deleted.status_code == 204
    with client.app.state.testing_session_local() as db:
        from app.models.database_models import PriceBarDB

        assert db.query(PriceBarDB).count() == 0
    missing = await client.get(f"/api/v1/instruments/{instrument_id}/prices")
    assert missing.status_code == 404
