"""Price-bar batch rules on PostgreSQL.

The SQLite module covers the same repository contract. This file
exists so the PostgreSQL CI job, which runs only ``integration``
tests, checks the batch too.
"""

import pytest

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

pytestmark = pytest.mark.integration


def _repo(factory, ticker):
    session = factory()
    instrument_id = add_company(session, ticker=ticker)
    return session, PriceBarRepository(session), instrument_id


def test_postgres_equal_duplicate_prices_leave_one_row(
    postgres_session_factory,
):
    session, repo, instrument_id = _repo(
        postgres_session_factory, "DEMO_BATCH_EQ"
    )
    try:
        assert_equal_duplicate_prices_leave_one_row(
            repo, session, instrument_id
        )
    finally:
        session.close()


def test_postgres_unequal_duplicate_prices_keep_the_last(
    postgres_session_factory,
):
    session, repo, instrument_id = _repo(
        postgres_session_factory, "DEMO_BATCH_LAST"
    )
    try:
        assert_unequal_duplicate_prices_keep_the_last(
            repo, session, instrument_id
        )
    finally:
        session.close()


def test_postgres_failed_batch_keeps_the_stored_row(
    postgres_session_factory,
):
    session, repo, instrument_id = _repo(
        postgres_session_factory, "DEMO_BATCH_FAIL"
    )
    try:
        assert_failed_batch_keeps_the_stored_row(repo, session, instrument_id)
    finally:
        session.close()


def test_postgres_bad_currency_leaves_no_row(postgres_session_factory):
    session, repo, instrument_id = _repo(
        postgres_session_factory, "DEMO_BATCH_CCY"
    )
    try:
        assert_bad_currency_leaves_no_row(repo, session, instrument_id)
    finally:
        session.close()


def test_postgres_repository_normalizes_currency(postgres_session_factory):
    session, repo, instrument_id = _repo(
        postgres_session_factory, "DEMO_BATCH_USD"
    )
    try:
        assert_repository_normalizes_a_lowercase_currency(
            repo, session, instrument_id
        )
    finally:
        session.close()


def test_postgres_default_source_tie_is_one_grouped_query(
    postgres_session_factory,
):
    session, repo, instrument_id = _repo(
        postgres_session_factory, "DEMO_BATCH_TIE"
    )
    try:
        assert_default_source_tie_is_one_grouped_query(
            session.get_bind(), session, repo, instrument_id
        )
    finally:
        session.close()
