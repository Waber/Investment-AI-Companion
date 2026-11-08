"""UI and API writes record manual. The seeder records demo.

A description that starts with ``[IAC-DEMO-`` does not make a UI
create synthetic. An update stores ``manual`` and leaves
``is_synthetic`` as it was.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, create_db_engine
from app.models.company import CompanyCreate, CompanyUpdate
from app.models.database_models import (
    RECORD_SOURCE_DEMO,
    RECORD_SOURCE_MANUAL,
    CompanyDB,
    FinancialMetricsDB,
)
from app.models.financial_metrics import (
    FinancialMetricsCreate,
    FinancialMetricsUpdate,
)
from app.repositories.company_repository import CompanyRepository
from app.repositories.financial_metrics_repository import (
    FinancialMetricsRepository,
)
from scripts.seed_demo import seed_sqlite_database


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


def test_repository_create_ignores_the_demo_prefix(session):
    created = CompanyRepository(session).create(
        CompanyCreate(
            name="Demo",
            ticker="DEMO",
            description="[IAC-DEMO-V2] typed through the API",
        )
    )
    assert created.is_synthetic is False
    assert created.source == RECORD_SOURCE_MANUAL


def test_repository_update_keeps_the_flag_and_records_manual(session):
    repo = CompanyRepository(session)
    created = repo.create(
        CompanyCreate(name="Demo", ticker="DEMO", description="seeded")
    )
    created.is_synthetic = True
    created.source = RECORD_SOURCE_DEMO
    session.commit()

    updated = repo.update(
        created.id, CompanyUpdate(description="edited by a person")
    )
    assert updated.description == "edited by a person"
    assert updated.is_synthetic is True
    assert updated.source == RECORD_SOURCE_MANUAL


def test_repository_create_can_record_an_explicit_demo_row(session):
    created = CompanyRepository(session).create(
        CompanyCreate(name="Demo", ticker="DEMO", description="seeded"),
        record_source=RECORD_SOURCE_DEMO,
        is_synthetic=True,
    )
    assert created.is_synthetic is True
    assert created.source == RECORD_SOURCE_DEMO


def test_repository_create_rejects_a_non_boolean_synthetic_flag(session):
    with pytest.raises(ValueError, match="is_synthetic must be true or false"):
        CompanyRepository(session).create(
            CompanyCreate(name="Demo", ticker="DEMO"),
            is_synthetic=1,
        )
    assert session.query(CompanyDB).count() == 0


def test_repository_create_rejects_an_unknown_record_source(session):
    with pytest.raises(ValueError, match="manual, demo, or fixture"):
        CompanyRepository(session).create(
            CompanyCreate(name="Demo", ticker="DEMO"),
            record_source="yahoo",
        )
    assert session.query(CompanyDB).count() == 0


def test_metric_writes_are_manual_unless_the_caller_says_demo(session):
    company = CompanyRepository(session).create(
        CompanyCreate(name="Demo", ticker="DEMO"),
        record_source=RECORD_SOURCE_DEMO,
        is_synthetic=True,
    )
    metrics = FinancialMetricsRepository(session)
    created = metrics.create(
        FinancialMetricsCreate(
            company_id=company.id,
            period_end=datetime(2024, 12, 31, tzinfo=timezone.utc),
            period_type="annual",
            revenue=1,
        )
    )
    assert created.source == RECORD_SOURCE_MANUAL

    seeded = metrics.create(
        FinancialMetricsCreate(
            company_id=company.id,
            period_end=datetime(2023, 12, 31, tzinfo=timezone.utc),
            period_type="annual",
            revenue=2,
        ),
        record_source=RECORD_SOURCE_DEMO,
    )
    assert seeded.source == RECORD_SOURCE_DEMO

    changed = metrics.update(seeded.id, FinancialMetricsUpdate(revenue=3))
    assert changed.revenue == 3
    assert changed.source == RECORD_SOURCE_MANUAL


def test_sqlite_seeder_marks_companies_and_metrics_as_demo(tmp_path):
    database = tmp_path / "demo.db"
    summary = seed_sqlite_database(f"sqlite:///{database}", apply=True)
    assert summary["companies"]["created"] == 6
    assert summary["metrics"]["created"] == 20
    engine = create_db_engine(f"sqlite:///{database}")
    try:
        db = sessionmaker(bind=engine)()
        try:
            companies = db.query(CompanyDB).all()
            metrics = db.query(FinancialMetricsDB).all()
            assert companies
            assert metrics
            assert {row.is_synthetic for row in companies} == {True}
            assert {row.source for row in companies} == {RECORD_SOURCE_DEMO}
            assert {row.source for row in metrics} == {RECORD_SOURCE_DEMO}
        finally:
            db.close()
    finally:
        engine.dispose()
