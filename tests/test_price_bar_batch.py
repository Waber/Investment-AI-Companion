"""SQLite coverage for the price-bar batch follow-ups.

The PostgreSQL copies live in ``tests/integration``. Nothing here
calls a market-data provider.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, create_db_engine
from app.models.price_amount import UnreadablePrice
from app.repositories.price_bar_repository import PriceBarRepository
from tests.price_bar_batch import (
    add_company,
    assert_bad_currency_leaves_no_row,
    assert_default_source_tie_is_one_grouped_query,
    assert_equal_duplicate_prices_leave_one_row,
    assert_failed_batch_keeps_the_stored_row,
    assert_repository_normalizes_a_lowercase_currency,
    assert_unequal_duplicate_prices_keep_the_last,
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


def test_repository_rejects_a_currency_that_is_not_three_letters():
    engine, session, repo, instrument_id = _sqlite_repo()
    try:
        assert_bad_currency_leaves_no_row(repo, session, instrument_id)
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
