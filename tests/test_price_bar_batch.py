"""SQLite coverage for the price-bar batch follow-ups.

The PostgreSQL copies live in ``tests/integration``. Nothing here
calls a market-data provider.
"""

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, create_db_engine
from app.models.price_amount import UnreadablePrice
from app.repositories.price_bar_repository import (
    PriceBarRepository,
    _pick_default,
)
from tests.price_bar_batch import (
    BAD_CURRENCY_SAMPLES,
    add_company,
    assert_bad_currency_leaves_no_row,
    assert_default_source_tie_is_one_grouped_query,
    assert_discarded_bad_currency_keeps_the_last_bar,
    assert_equal_duplicate_prices_leave_one_row,
    assert_failed_batch_keeps_the_stored_row,
    assert_repository_normalizes_a_lowercase_currency,
    assert_unequal_duplicate_prices_keep_the_last,
    flat_bar,
)


def _sqlite_repo():
    """An in-memory repository and one company. The caller closes it."""
    engine = create_db_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    instrument_id = add_company(session, ticker="DEMO_BATCH_SQL")
    return engine, session, PriceBarRepository(session), instrument_id


def test_upsert_many_collapses_equal_prices_to_one_row():
    engine, session, repo, instrument_id = _sqlite_repo()
    try:
        assert_equal_duplicate_prices_leave_one_row(
            repo, session, instrument_id
        )
    finally:
        session.close()
        engine.dispose()


def test_upsert_many_keeps_the_last_price_when_a_key_repeats():
    engine, session, repo, instrument_id = _sqlite_repo()
    try:
        assert_unequal_duplicate_prices_keep_the_last(
            repo, session, instrument_id
        )
    finally:
        session.close()
        engine.dispose()


def test_upsert_many_keeps_a_stored_row_when_the_batch_fails():
    engine, session, repo, instrument_id = _sqlite_repo()
    try:
        assert_failed_batch_keeps_the_stored_row(repo, session, instrument_id)
    finally:
        session.close()
        engine.dispose()


@pytest.mark.parametrize("bad", BAD_CURRENCY_SAMPLES)
def test_repository_rejects_a_currency_that_is_not_three_letters(bad):
    engine, session, repo, instrument_id = _sqlite_repo()
    try:
        assert_bad_currency_leaves_no_row(repo, session, instrument_id, bad)
    finally:
        session.close()
        engine.dispose()


def test_discarded_bad_currency_keeps_the_last_bar():
    """Last-wins stores the valid copy and does not reject the batch."""
    engine, session, repo, instrument_id = _sqlite_repo()
    try:
        assert_discarded_bad_currency_keeps_the_last_bar(
            repo, session, instrument_id
        )
    finally:
        session.close()
        engine.dispose()


def test_repository_stores_usd_and_keeps_gbp_pence():
    engine, session, repo, instrument_id = _sqlite_repo()
    try:
        assert_repository_normalizes_a_lowercase_currency(
            repo, session, instrument_id
        )
    finally:
        session.close()
        engine.dispose()


def test_default_source_tie_uses_one_grouped_query():
    engine, session, repo, instrument_id = _sqlite_repo()
    try:
        assert_default_source_tie_is_one_grouped_query(
            engine, session, repo, instrument_id
        )
    finally:
        session.close()
        engine.dispose()


def _unreadable(bar_id):
    return SimpleNamespace(
        id=bar_id,
        instrument_id=7,
        open_price=UnreadablePrice(),
        high_price=None,
        low_price=None,
        close_price=None,
    )


def test_unreadable_skip_log_drops_the_oldest_id(caplog, monkeypatch):
    """The cap is 1 here, so the third distinct id evicts the first.

    A repeated id does not log again until it has been dropped.
    """
    import app.repositories.price_bar_repository as bars

    monkeypatch.setattr(bars, "_MAX_LOGGED_SKIP_IDS", 1)
    bars._logged_skip_ids.clear()
    try:
        with caplog.at_level(
            "WARNING", logger="app.repositories.price_bar_repository"
        ):
            assert bars._readable(_unreadable(1)) is False
            assert bars._readable(_unreadable(1)) is False
            assert bars._readable(_unreadable(2)) is False
            assert bars._readable(_unreadable(1)) is False
    finally:
        bars._logged_skip_ids.clear()
    messages = [
        record.getMessage()
        for record in caplog.records
        if "not a decimal" in record.getMessage()
    ]
    assert messages == [
        "Skipping price bar id=1 instrument_id=7: "
        "stored price is not a decimal",
        "Skipping price bar id=2 instrument_id=7: "
        "stored price is not a decimal",
        "Skipping price bar id=1 instrument_id=7: "
        "stored price is not a decimal",
    ]


def _rejected_row(bar_id):
    """A row the response model cannot build.

    The open is not a decimal, so ``db_to_price`` raises and the
    route logs a skip. The currency is also too long.
    """
    return SimpleNamespace(
        id=bar_id,
        instrument_id=7,
        bar_date=datetime(2026, 1, 5).date(),
        open_price=UnreadablePrice(),
        high_price=None,
        low_price=None,
        close_price=None,
        volume=None,
        currency="LONG",
        source="fake",
        retrieved_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
    )


def test_logged_skip_cap_is_the_literal_1024(caplog):
    """1024 ids stay. The 1025th drops only the oldest, which logs again.

    The cap is not patched. ``_MAX_LOGGED_SKIP_IDS`` must be 1024,
    and ``_remember_skip`` must read that constant. A cap of 1023
    drops id 1 before the 1025th insert. A cap of 1025 still holds
    id 1 after that insert.
    """
    import app.repositories.price_bar_repository as bars

    assert bars._MAX_LOGGED_SKIP_IDS == 1024
    seen = bars._logged_skip_ids
    seen.clear()
    try:
        for bar_id in range(1, 1025):
            assert bars._remember_skip(seen, bar_id) is True
        assert len(seen) == 1024
        assert list(seen)[0] == 1
        assert 1024 in seen
        with caplog.at_level(
            "WARNING", logger="app.repositories.price_bar_repository"
        ):
            assert bars._readable(_unreadable(1)) is False
            assert bars._readable(_unreadable(2)) is False
        assert [
            record.getMessage()
            for record in caplog.records
            if "not a decimal" in record.getMessage()
        ] == []
        caplog.clear()
        assert bars._remember_skip(seen, 1025) is True
        assert list(seen)[0] == 2
        assert 1 not in seen
        assert 2 in seen
        assert 1025 in seen
        assert len(seen) == 1024
        with caplog.at_level(
            "WARNING", logger="app.repositories.price_bar_repository"
        ):
            assert bars._readable(_unreadable(2)) is False
            assert bars._readable(_unreadable(1)) is False
        assert [
            record.getMessage()
            for record in caplog.records
            if "not a decimal" in record.getMessage()
        ] == [
            "Skipping price bar id=1 instrument_id=7: "
            "stored price is not a decimal"
        ]
    finally:
        seen.clear()


def test_api_skip_log_drops_the_oldest_id(caplog, monkeypatch):
    """The route's own set uses the same cap as the repository."""
    import app.api.prices as prices
    import app.repositories.price_bar_repository as bars

    monkeypatch.setattr(bars, "_MAX_LOGGED_SKIP_IDS", 1)
    prices._logged_skip_ids.clear()
    try:
        with caplog.at_level("WARNING", logger="app.api.prices"):
            assert prices._bars_or_skip([_rejected_row(1)], 7) == []
            assert prices._bars_or_skip([_rejected_row(1)], 7) == []
            assert (
                prices._bars_or_skip([_rejected_row(2), _rejected_row(1)], 7)
                == []
            )
    finally:
        prices._logged_skip_ids.clear()
    messages = [
        record.getMessage()
        for record in caplog.records
        if "cannot be returned" in record.getMessage()
    ]
    assert messages == [
        "Skipping price bar id=1 instrument_id=7: "
        "stored price cannot be returned",
        "Skipping price bar id=2 instrument_id=7: "
        "stored price cannot be returned",
        "Skipping price bar id=1 instrument_id=7: "
        "stored price cannot be returned",
    ]


def _sql_tie_key(pair):
    """Order a punctuation-ignoring, case-folded collation would use.

    ``[`` and ``]`` drop out, then the rest is case-folded. Under
    that order ``[IAC-DEMO-V2]`` sorts after ``fake``. Python
    ``max`` compares code points, so ``fake`` wins: ``f`` is after
    ``[``. C.UTF-8 and SQLite's binary collation agree with Python,
    which is why an ``ORDER BY source`` mutation still passed there.
    """
    source, retrieved = pair
    folded = "".join(char for char in source.casefold() if char not in "[]")
    return (retrieved, folded)


class _TieQuery:
    """Pairs for ``_default_source``, with a collation that is not Python.

    ``all()`` without ``order_by`` returns the pairs in the order
    they were given. Neither end of that list is the Python winner.
    ``order_by`` then ``limit`` / ``first`` returns the row the
    punctuation-ignoring collation would put first. The production
    function must ignore both of those and use ``max``.
    """

    def __init__(self, rows, order_sql=False, limit_n=None):
        self._rows = rows
        self._order_sql = order_sql
        self._limit_n = limit_n

    def _clone(self, **changes):
        return _TieQuery(
            self._rows,
            changes.get("order_sql", self._order_sql),
            changes.get("limit_n", self._limit_n),
        )

    def with_entities(self, *columns):
        return self

    def group_by(self, *columns):
        return self

    def filter(self, *args, **kwargs):
        return self

    def distinct(self):
        return self

    def order_by(self, *columns):
        return self._clone(order_sql=True)

    def limit(self, count):
        return self._clone(limit_n=count)

    def scalar(self):
        return max(retrieved for _source, retrieved in self._rows)

    def _materialize(self):
        if self._order_sql:
            rows = sorted(self._rows, key=_sql_tie_key, reverse=True)
        else:
            rows = list(self._rows)
        if self._limit_n is not None:
            rows = rows[: self._limit_n]
        return rows

    def all(self):
        return self._materialize()

    def first(self):
        rows = self._materialize()
        return rows[0] if rows else None


def test_pick_default_tie_is_fake_and_empty_is_none():
    """The shared rule: latest instant, then Python ``max`` on the name.

    An empty list is None. ``fake`` beats ``[IAC-DEMO-V2]`` when
    the instants match. A later ``aaa`` beats an earlier ``zzz``.
    """
    assert _pick_default(()) is None
    assert _pick_default([]) is None
    when = datetime(2026, 10, 2, 18, tzinfo=timezone.utc)
    earlier = datetime(2020, 1, 1, tzinfo=timezone.utc)
    assert _pick_default([("[IAC-DEMO-V2]", when), ("fake", when)]) == "fake"
    assert (
        _pick_default(
            [
                ("zzz", earlier),
                ("[IAC-DEMO-V2]", when),
                ("fake", when),
            ]
        )
        == "fake"
    )
    assert _pick_default([("zzz", earlier), ("aaa", when)]) == "aaa"


def test_default_source_tie_break_is_python_max_not_sql_order():
    """``fake`` wins even when SQL would return the demo marker.

    The rows are not sorted by Python ``max``. The newest instant
    is shared by ``aaa``, ``fake``, and ``[IAC-DEMO-V2]``. An older
    ``zzz`` would win a name-only max. The punctuation-ignoring
    order at the newest instant puts the demo marker first.
    """
    old = datetime(2020, 1, 1, tzinfo=timezone.utc)
    new = datetime(2026, 10, 2, 18, tzinfo=timezone.utc)
    query = _TieQuery(
        [
            ("zzz", old),
            ("fake", new),
            ("aaa", new),
            ("[IAC-DEMO-V2]", new),
        ]
    )
    assert PriceBarRepository._default_source(query) == "fake"
    assert _TieQuery(query._rows, order_sql=True).first()[0] == (
        "[IAC-DEMO-V2]"
    )


def _folded_source_key(row):
    """Punctuation-ignoring order for one grouped batch row.

    The row is ``(instrument_id, source, retrieved_at)``. ``[`` and
    ``]`` drop out and the rest is case-folded, which is the order
    where ``[IAC-DEMO-V2]`` sorts after ``fake``.
    """
    _instrument_id, source, retrieved = row
    folded = "".join(char for char in source.casefold() if char not in "[]")
    return (retrieved, folded)


class _BatchSourceQuery:
    """The grouped rows ``_default_sources_for`` reads.

    ``all()`` without ``order_by`` keeps the given order, and the
    Python winner is not at either end. ``order_by`` then returns
    the punctuation-ignoring order, demo marker first.
    """

    def __init__(self, rows, order_sql=False):
        self._rows = rows
        self._order_sql = order_sql

    def filter(self, *args, **kwargs):
        return self

    def group_by(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return _BatchSourceQuery(self._rows, order_sql=True)

    def all(self):
        if not self._order_sql:
            return list(self._rows)
        return sorted(self._rows, key=_folded_source_key, reverse=True)


class _RoutingSession:
    """Real session, except the three-column source query.

    ``_default_sources_for`` asks for instrument, source, and
    ``max(retrieved_at)``. That call gets the stand-in. The close
    queries that follow still hit the database.
    """

    def __init__(self, real, source_rows):
        self._real = real
        self._source_rows = source_rows

    def query(self, *entities, **kwargs):
        if len(entities) == 3:
            return _BatchSourceQuery(self._source_rows)
        return self._real.query(*entities, **kwargs)

    def __getattr__(self, name):
        return getattr(self._real, name)


def test_recent_closes_for_ignores_sql_source_order():
    """The watchlist batch path still picks ``fake`` when SQL would not.

    ``list_entries`` calls ``recent_closes_for``. The stand-in
    returns ``aaa`` first and ``[IAC-DEMO-V2]`` last, and its
    ``ORDER BY`` puts the demo marker first. The stored close for
    ``fake`` is the one the page would show.
    """
    engine, session, repo, instrument_id = _sqlite_repo()
    try:
        when = datetime(2026, 10, 2, 18, tzinfo=timezone.utc)
        for source, close in (
            ("aaa", 2),
            ("fake", 9),
            ("[IAC-DEMO-V2]", 1),
        ):
            repo.create(
                instrument_id,
                flat_bar(
                    "2026-04-06",
                    close,
                    volume=close,
                    source=source,
                    retrieved_at=when,
                ),
            )
        rows = [
            (instrument_id, "aaa", when),
            (instrument_id, "fake", when),
            (instrument_id, "[IAC-DEMO-V2]", when),
        ]
        assert _BatchSourceQuery(rows).all()[0][1] == "aaa"
        assert _BatchSourceQuery(rows, order_sql=True).all()[0][1] == (
            "[IAC-DEMO-V2]"
        )
        repo.db = _RoutingSession(session, rows)
        assert repo._default_sources_for([instrument_id]) == {
            instrument_id: "fake"
        }
        found = repo.recent_closes_for([instrument_id])
        assert found[instrument_id].source == "fake"
        assert found[instrument_id].latest.close_price == Decimal("9.00000000")
    finally:
        session.close()
        engine.dispose()
