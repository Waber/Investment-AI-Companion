"""Fund-attribute delete on PostgreSQL.

The cases live in ``tests.test_fund_attributes_delete``. This module
only opens the PostgreSQL session and client. Without
``-m integration`` pytest deselects it. The delete itself is ordinary
ORM SQL. Running it here checks that removing the child row does not
cascade to the company or its prices on PostgreSQL either.
"""

import pytest

from tests.test_fund_attributes_delete import (
    _HUGE_ID,
    assert_delete_header_is_ignored,
    assert_delete_keeps_the_instrument,
    assert_delete_on_a_stock_keeps_the_stock,
    assert_delete_rejects_id,
    assert_etc_without_a_row_is_404,
    assert_failed_delete_commit_rolls_back,
    assert_http_delete_leaves_the_other_fund,
    assert_repository_delete_happy_path,
    assert_repository_delete_leaves_the_other_row,
    assert_repository_delete_missing,
    assert_unknown_instrument_is_404,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def session(postgres_session_factory):
    db = postgres_session_factory()
    try:
        yield db
    finally:
        db.close()


def test_repository_delete_on_postgresql(session):
    assert_repository_delete_happy_path(session)
    assert_repository_delete_missing(session)
    assert_repository_delete_leaves_the_other_row(session)
    assert_failed_delete_commit_rolls_back(session, ticker="ROLL")


@pytest.mark.asyncio
async def test_http_delete_on_postgresql(postgres_client, monkeypatch):
    await assert_delete_keeps_the_instrument(postgres_client)
    await assert_delete_keeps_the_instrument(postgres_client, "ETC1", "ETC")
    await assert_etc_without_a_row_is_404(postgres_client)
    await assert_http_delete_leaves_the_other_fund(postgres_client)
    await assert_unknown_instrument_is_404(postgres_client)
    await assert_delete_on_a_stock_keeps_the_stock(postgres_client)
    for raw in ("0", "-1", _HUGE_ID):
        await assert_delete_rejects_id(postgres_client, raw)
    await assert_delete_header_is_ignored(postgres_client, monkeypatch)
