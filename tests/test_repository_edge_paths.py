"""Repository paths the HTTP API cannot reach on its own."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.company import CompanyCreate
from app.models.database_models import CompanyDB, FinancialMetricsDB
from app.models.financial_metrics import FinancialMetricsUpdate
from app.repositories.company_repository import CompanyRepository
from app.repositories.financial_metrics_repository import (
    FinancialMetricsRepository,
)


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, autoflush=False)()
    yield db
    db.close()
    engine.dispose()


def integrity_error(message):
    return IntegrityError("INSERT ...", {}, Exception(message))


def fail_commit(monkeypatch, session, message):
    rollbacks = []

    def commit():
        raise integrity_error(message)

    original_rollback = session.rollback

    def rollback():
        rollbacks.append(True)
        original_rollback()

    monkeypatch.setattr(session, "commit", commit)
    monkeypatch.setattr(session, "rollback", rollback)
    return rollbacks


@pytest.fixture
def company(session):
    row = CompanyDB(name="Acme", ticker="ACME")
    session.add(row)
    session.commit()
    return row


# company-shaped pin, see #26
def test_company_create_maps_named_constraint_to_value_error(
    monkeypatch, session
):
    rollbacks = fail_commit(
        monkeypatch, session, "violates uq_company_name_ticker"
    )

    with pytest.raises(ValueError, match="already exists"):
        CompanyRepository(session).create(
            CompanyCreate(name="Acme", ticker="ACME")
        )

    assert rollbacks == [True]


def test_company_create_reraises_other_integrity_errors(monkeypatch, session):
    rollbacks = fail_commit(monkeypatch, session, "NOT NULL constraint failed")

    with pytest.raises(IntegrityError):
        CompanyRepository(session).create(
            CompanyCreate(name="Acme", ticker="ACME")
        )

    assert rollbacks == [True]


# company-shaped pin, see #26
def test_company_is_unique_checks_name_or_ticker(session, company):
    repo = CompanyRepository(session)

    assert repo.is_unique("Other", "OTHR") is True
    assert repo.is_unique("Acme", "OTHR") is False
    assert repo.is_unique("Other", "ACME") is False


def test_company_is_unique_ignores_excluded_id(session, company):
    repo = CompanyRepository(session)

    assert repo.is_unique("Acme", "ACME", exclude_id=company.id) is True
    assert repo.is_unique("Acme", "ACME", exclude_id=company.id + 1) is False


def test_company_delete_missing_returns_false(session):
    assert CompanyRepository(session).delete(12345) is False


def test_metrics_update_integrity_error_rolls_back(
    monkeypatch, session, company
):
    row = FinancialMetricsDB(
        company_id=company.id,
        period_end=datetime(2024, 12, 31, tzinfo=timezone.utc),
        period_type="annual",
        revenue=1.0,
    )
    session.add(row)
    session.commit()
    rollbacks = fail_commit(monkeypatch, session, "CHECK constraint failed")

    with pytest.raises(ValueError, match="constraint violation"):
        FinancialMetricsRepository(session).update(
            row.id, FinancialMetricsUpdate(revenue=2.0)
        )

    assert rollbacks == [True]


def test_metrics_is_unique_ignores_excluded_id(session, company):
    period_end = datetime(2024, 12, 31, tzinfo=timezone.utc)
    row = FinancialMetricsDB(
        company_id=company.id, period_end=period_end, period_type="annual"
    )
    session.add(row)
    session.commit()
    repo = FinancialMetricsRepository(session)

    assert repo.is_unique(company.id, period_end, "annual") is False
    assert repo.is_unique(company.id, period_end, "quarterly") is True
    assert (
        repo.is_unique(company.id, period_end, "annual", exclude_id=row.id)
        is True
    )


def test_metrics_delete_missing_returns_false(session):
    assert FinancialMetricsRepository(session).delete(12345) is False
