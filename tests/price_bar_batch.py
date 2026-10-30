"""Batch rules shared by the SQLite and PostgreSQL price-bar tests.

These functions call the repository, not the HTTP API. A currency
that skips ``PriceBarCreate`` is assigned after the model is built.
Assignment does not re-run validators, which is how a direct caller
bypasses the three-letter rule. The repository has to reject that
itself.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import event

from app.models.database_models import CompanyDB, PriceBarDB
from app.models.price_bar import PriceBarCreate
from app.repositories.price_bar_repository import PriceBarRepository

_RETRIEVED = datetime(2026, 10, 2, 18, 0, tzinfo=timezone.utc)
_LATER = datetime(2026, 10, 3, 18, 0, tzinfo=timezone.utc)


def add_company(session, ticker="DEMO_BATCH"):
    """One company, and the id the bars point at."""
    session.add(CompanyDB(name="Synthetic", ticker=ticker, currency="USD"))
    session.commit()
    return session.query(CompanyDB).one().id


def flat_bar(day, price, **overrides):
    """One valid bar. The four prices match, so the candle checks pass."""
    payload = {
        "date": day,
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "volume": 100,
        "currency": "PLN",
        "source": "fake",
        "retrieved_at": "2026-09-30T18:00:00Z",
    }
    payload.update(overrides)
    return PriceBarCreate(**payload)


def stored_rows(session):
    """Rows as the database has them, oldest session first."""
    return session.query(PriceBarDB).order_by(PriceBarDB.bar_date.asc()).all()


def select_statements(engine, call):
    """SQL ``SELECT`` text executed while ``call`` runs."""
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        call()
    finally:
        event.remove(engine, "before_cursor_execute", record)
    return [
        statement
        for statement in statements
        if statement.lstrip().lower().startswith("select")
    ]


def _oversized(day):
    """A price the column type rejects. The model would reject it too.

    ``model_construct`` skips that check, so the failure happens in
    the repository while the batch is flushed.
    """
    huge = Decimal("1000000000000")
    return PriceBarCreate.model_construct(
        date=day,
        open=huge,
        high=huge,
        low=huge,
        close=huge,
        volume=100,
        currency="PLN",
        source="oversized",
        retrieved_at=_RETRIEVED,
    )


def assert_equal_duplicate_prices_leave_one_row(repo, session, instrument_id):
    """Two copies of the same key and the same price are one row."""
    first = flat_bar("2026-02-02", 4, volume=4)
    second = flat_bar("2026-02-02", 4, volume=4)
    stored = repo.upsert_many(instrument_id, [first, second])
    assert len(stored) == 1
    rows = stored_rows(session)
    assert len(rows) == 1
    assert rows[0].bar_date == date(2026, 2, 2)
    assert rows[0].close_price == Decimal("4.00000000")
    assert rows[0].volume == 4
    assert rows[0].source == "fake"


def assert_unequal_duplicate_prices_keep_the_last(
    repo, session, instrument_id
):
    """The later bar in the batch is the row. A second batch updates it.

    The first phase inserts. The second phase finds that row and
    still keeps the last copy, so last-wins is not only an insert.
    """
    stored = repo.upsert_many(
        instrument_id,
        [
            flat_bar("2026-02-03", 4, volume=4),
            flat_bar("2026-02-03", 7, volume=7),
        ],
    )
    assert len(stored) == 1
    assert stored[0].close_price == Decimal("7.00000000")
    assert stored[0].volume == 7
    rows = stored_rows(session)
    assert len(rows) == 1
    assert rows[0].close_price == Decimal("7.00000000")
    assert rows[0].volume == 7

    updated = repo.upsert_many(
        instrument_id,
        [
            flat_bar("2026-02-03", 8, volume=8),
            flat_bar("2026-02-03", 9, volume=9),
        ],
    )
    assert len(updated) == 1
    rows = stored_rows(session)
    assert len(rows) == 1
    assert rows[0].close_price == Decimal("9.00000000")
    assert rows[0].volume == 9
    assert rows[0].open_price == Decimal("9.00000000")


def assert_failed_batch_keeps_the_stored_row(repo, session, instrument_id):
    """A duplicate's last-wins update is rolled back with the batch.

    The stored row would become price 30 if the batch committed.
    The oversized bar fails the flush. The stored row keeps price 10
    and its original volume.
    """
    repo.create(instrument_id, flat_bar("2026-01-05", 10, volume=100))
    try:
        repo.upsert_many(
            instrument_id,
            [
                flat_bar("2026-01-05", 20, volume=20),
                flat_bar("2026-01-05", 30, volume=30),
                _oversized(date(2026, 1, 7)),
            ],
        )
    except ValueError as caught:
        assert str(caught) == "Price bar could not be stored"
        assert caught.__cause__ is None
        assert caught.__context__ is None
        assert "1000000000000" not in str(caught)
        assert "INSERT" not in str(caught)
    else:
        raise AssertionError("the oversized bar should have failed")
    rows = stored_rows(session)
    assert [row.bar_date for row in rows] == [date(2026, 1, 5)]
    kept = rows[0]
    assert kept.close_price == Decimal("10.00000000")
    assert kept.open_price == Decimal("10.00000000")
    assert kept.volume == 100
    assert list(session.new) == []


# One case per test. ``ids`` are the node names pytest prints.
# ``usd `` has a trailing space, which is not three letters.
BAD_CURRENCY_SAMPLES = (
    pytest.param("PLNX", id="PLNX"),
    pytest.param("US", id="US"),
    pytest.param("PL1", id="PL1"),
    pytest.param(None, id="None"),
    pytest.param("usd ", id="usd-space"),
)


def assert_bad_currency_leaves_no_row(repo, session, instrument_id, bad):
    """A code that is not three letters never reaches the database.

    The batch also carries a valid new bar. That bar is not stored
    either: the check runs before any row is added. The row that
    was already stored keeps PLN and its price.
    """
    repo.create(instrument_id, flat_bar("2026-03-01", 10))
    created = flat_bar("2026-03-02", 11)
    created.currency = bad
    try:
        repo.create(instrument_id, created)
    except ValueError as caught:
        assert str(caught) == "currency must be exactly three letters"
        assert caught.__cause__ is None
        assert caught.__context__ is None
    else:
        raise AssertionError("create should reject " + repr(bad))
    updated = flat_bar("2026-03-01", 12, volume=12)
    updated.currency = bad
    fresh = flat_bar("2026-03-03", 13)
    try:
        repo.upsert_many(instrument_id, [fresh, updated])
    except ValueError as caught:
        assert str(caught) == "currency must be exactly three letters"
    else:
        raise AssertionError("upsert should reject " + repr(bad))
    assert list(session.new) == []
    assert list(session.dirty) == []
    rows = stored_rows(session)
    assert [row.bar_date for row in rows] == [date(2026, 3, 1)]
    assert rows[0].currency == "PLN"
    assert rows[0].close_price == Decimal("10.00000000")
    assert rows[0].volume == 100


def assert_repository_normalizes_a_lowercase_currency(
    repo, session, instrument_id
):
    """``usd`` is stored as ``USD``. ``GBp`` and ``ZAc`` keep their case.

    The same rule as the API model. A direct caller does not get
    a second spelling of one currency. ``ZAc`` is South African
    cents, the same kind of exception as London pence.
    """
    lower = flat_bar("2026-03-04", 6)
    lower.currency = "usd"
    stored = repo.create(instrument_id, lower)
    assert stored.currency == "USD"
    pence = flat_bar("2026-03-05", 6, source="pence")
    pence.currency = "GBp"
    stored = repo.create(instrument_id, pence)
    assert stored.currency == "GBp"
    cents = flat_bar("2026-03-06", 6, source="cents")
    cents.currency = "ZAc"
    stored = repo.create(instrument_id, cents)
    assert stored.currency == "ZAc"
    rows = {row.bar_date: row for row in stored_rows(session)}
    assert rows[date(2026, 3, 4)].currency == "USD"
    assert rows[date(2026, 3, 5)].currency == "GBp"
    assert rows[date(2026, 3, 6)].currency == "ZAc"


def assert_discarded_bad_currency_keeps_the_last_bar(
    repo, session, instrument_id
):
    """Last-wins does not validate a copy that is not written.

    The first bar's currency is not three letters. The later bar
    for the same date and source is valid, so that bar is stored
    and the batch does not raise.
    """
    discarded = flat_bar("2026-04-01", 3, volume=3)
    discarded.currency = "NOPE"
    winner = flat_bar("2026-04-01", 8, volume=8)
    stored = repo.upsert_many(instrument_id, [discarded, winner])
    assert len(stored) == 1
    assert stored[0].currency == "PLN"
    assert stored[0].close_price == Decimal("8.00000000")
    assert stored[0].volume == 8
    rows = stored_rows(session)
    assert len(rows) == 1
    assert rows[0].currency == "PLN"
    assert rows[0].close_price == Decimal("8.00000000")
    assert rows[0].volume == 8


def assert_default_source_tie_is_one_grouped_query(
    engine, session, repo, instrument_id
):
    """A tie is one ``GROUP BY``, and ``fake`` still beats the marker.

    A later retrieval then wins, still in that one query. An
    instrument with no bars is None. A date window that holds only
    the other source stays empty.
    """
    repo.create(
        instrument_id,
        flat_bar(
            "2026-01-05",
            10,
            source="[IAC-DEMO-V2]",
            retrieved_at=_RETRIEVED,
        ),
    )
    repo.create(
        instrument_id,
        flat_bar(
            "2026-01-06",
            10,
            source="fake",
            retrieved_at=_RETRIEVED,
        ),
    )
    query = session.query(PriceBarDB).filter(
        PriceBarDB.instrument_id == instrument_id
    )
    chosen = {}

    def read():
        chosen["source"] = PriceBarRepository._default_source(query)

    tied = select_statements(engine, read)
    # One SELECT, not the old max-then-distinct pair. The winner
    # itself is locked by the Python-max test, not by SQL text.
    assert len(tied) == 1
    assert chosen["source"] == "fake"
    # The window has the demo bar only. The source was already
    # chosen, so this is empty rather than the demo series.
    window = repo.get_range(
        instrument_id, start=date(2026, 1, 5), end=date(2026, 1, 5)
    )
    assert window == []
    named = repo.get_range(
        instrument_id,
        start=date(2026, 1, 5),
        end=date(2026, 1, 5),
        source="[IAC-DEMO-V2]",
    )
    assert [row.source for row in named] == ["[IAC-DEMO-V2]"]

    repo.create(
        instrument_id,
        flat_bar(
            "2026-01-07",
            10,
            source="zzz",
            retrieved_at=_LATER,
        ),
    )
    later = select_statements(engine, read)
    assert len(later) == 1
    assert chosen["source"] == "zzz"

    empty = session.query(PriceBarDB).filter(PriceBarDB.instrument_id == -1)
    missing = {}

    def read_empty():
        missing["source"] = PriceBarRepository._default_source(empty)

    none_rows = select_statements(engine, read_empty)
    assert len(none_rows) == 1
    assert missing["source"] is None
