"""Exact OHLC round-trips on PostgreSQL.

The SQLite suite covers the same HTTP contract. This module is here
so the PostgreSQL CI job, which runs only ``integration`` tests,
checks it too. Prices stay ``numeric``. They are not cast to float.
"""

import pytest
from sqlalchemy import text

from tests.price_round_trip import (
    assert_exact_round_trip,
    assert_failed_post_leaves_no_row,
    assert_negative_zero_is_zero,
    assert_same_retrieved_at_picks_fake,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_postgres_exact_price_round_trip(postgres_client):
    instrument_id = await assert_exact_round_trip(
        postgres_client, "DEMO_EXACT_PG"
    )
    with postgres_client.app.state.testing_session_local() as db:
        stored = db.execute(
            text(
                "SELECT pg_typeof(open_price)::text, open_price::text "
                "FROM price_bars WHERE instrument_id = :instrument_id"
            ),
            {"instrument_id": instrument_id},
        ).all()
    assert stored
    assert {kind for kind, _value in stored} == {"numeric"}
    assert {value for _kind, value in stored} == {
        "999999999.99999999",
        "999999999999.99999999",
        "999999999999.12345678",
    }


@pytest.mark.asyncio
async def test_postgres_failed_price_post_leaves_no_row(postgres_client):
    await assert_failed_post_leaves_no_row(
        postgres_client, "DEMO_EXACT_PG_FAIL"
    )


@pytest.mark.asyncio
async def test_postgres_negative_zero_is_zero(postgres_client):
    await assert_negative_zero_is_zero(postgres_client, "DEMO_NEG0_PG")


@pytest.mark.asyncio
async def test_postgres_tied_retrieval_picks_fake_over_demo(postgres_client):
    """Same instant as SQLite: ``fake`` beats ``[IAC-DEMO-V2]``."""
    await assert_same_retrieved_at_picks_fake(
        postgres_client, "DEMO_TIE_FAKE_PG"
    )
