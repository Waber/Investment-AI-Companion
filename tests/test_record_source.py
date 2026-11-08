"""Allowed company and metric sources live next to the models.

The database column has no CHECK. ``require_record_source`` is the
check. Missing and unknown values fail before a row is written.
``manual``, ``demo``, and ``fixture`` are the whole set.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, create_db_engine
from app.models.database_models import (
    RECORD_SOURCE_DEMO,
    RECORD_SOURCE_FIXTURE,
    RECORD_SOURCE_MANUAL,
    RECORD_SOURCES,
    CompanyDB,
    FinancialMetricsDB,
    require_record_source,
)

_INVALID_SOURCES = [
    None,
    "",
    "   ",
    "manual ",
    " Manual",
    "Manual",
    "DEMO",
    "demo-v1",
    "demo-v2",
    "yahoo",
    "fixture ",
    1,
    False,
    True,
]


def test_record_source_constants_are_the_three_allowed_values():
    assert RECORD_SOURCE_MANUAL == "manual"
    assert RECORD_SOURCE_DEMO == "demo"
    assert RECORD_SOURCE_FIXTURE == "fixture"
    assert RECORD_SOURCES == frozenset({"manual", "demo", "fixture"})


@pytest.mark.parametrize("value", ["manual", "demo", "fixture"])
def test_require_record_source_accepts_the_allowed_values(value):
    assert require_record_source(value) == value


@pytest.mark.parametrize("value", _INVALID_SOURCES)
def test_require_record_source_rejects_missing_and_unknown_values(value):
    """Missing, blank, wrong case, and unknown sources are one error.

    The message names the three allowed values. ``demo-v1`` is not a
    source: the owner label is the single word ``demo``.
    """
    with pytest.raises(ValueError, match="manual, demo, or fixture"):
        require_record_source(value)


@pytest.fixture
def session():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_omitted_company_source_is_manual_and_not_synthetic(session):
    """A row that does not name a source is a real manual company.

    The description prefix does not flip the flag. That prefix is
    only a backfill hint in revision 0009.
    """
    row = CompanyDB(
        name="Demo",
        ticker="DEMO",
        description="[IAC-DEMO-V1] typed by hand",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    assert row.source == "manual"
    assert row.is_synthetic is False


def test_explicit_none_source_is_rejected_on_assignment(session):
    """``None`` is not the omitted default. Assignment fails at once.

    No row is added, so the session has nothing to flush.
    """
    with pytest.raises(ValueError, match="manual, demo, or fixture"):
        CompanyDB(name="Acme", ticker="ACME", source=None)
    assert session.query(CompanyDB).count() == 0


@pytest.mark.parametrize("value", _INVALID_SOURCES)
def test_company_and_metric_models_reject_the_same_sources(session, value):
    company = CompanyDB(name="Acme", ticker="ACME", source="manual")
    session.add(company)
    session.flush()
    with pytest.raises(ValueError, match="manual, demo, or fixture"):
        company.source = value
    metric = FinancialMetricsDB(
        company_id=company.id,
        period_end=datetime(2024, 12, 31, tzinfo=timezone.utc),
        period_type="annual",
        source="manual",
    )
    session.add(metric)
    session.flush()
    with pytest.raises(ValueError, match="manual, demo, or fixture"):
        metric.source = value


def test_fixture_source_is_stored_when_asked_for(session):
    row = CompanyDB(
        name="Fixture",
        ticker="FIX1",
        source=RECORD_SOURCE_FIXTURE,
        is_synthetic=False,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    assert row.source == "fixture"
    assert row.is_synthetic is False


def test_raw_sql_can_store_a_source_outside_the_python_set(session):
    """No CHECK constraint. A later collector value needs no migration.

    The model rejects ``yahoo`` on assignment. A raw insert still
    stores it, and reading the row back does not raise, because a
    load must not depend on the current allow-list.
    """
    session.execute(
        CompanyDB.__table__.insert().values(
            name="Later",
            ticker="YAH1",
            source="yahoo",
            is_synthetic=False,
        )
    )
    session.commit()
    loaded = session.query(CompanyDB).filter_by(ticker="YAH1").one()
    assert loaded.source == "yahoo"
