"""Repository paths the HTTP API cannot reach on its own."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.company import CompanyCreate, CompanyUpdate
from app.models.database_models import CompanyDB, FinancialMetricsDB
from app.models.financial_metrics import FinancialMetricsUpdate
from app.repositories.company_errors import (
    DuplicateIsinError,
    DuplicateTickerError,
)
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


def test_company_create_ignores_constraint_name_in_the_driver_message(
    monkeypatch, session
):
    """A message that names the old constraint is not a duplicate.

    Nothing was inserted, so the ticker lookup after rollback finds
    no row. The driver text is not turned into a client error.
    """
    rollbacks = fail_commit(
        monkeypatch, session, "violates uq_company_name_ticker"
    )

    with pytest.raises(IntegrityError):
        CompanyRepository(session).create(
            CompanyCreate(name="Acme", ticker="ACME")
        )

    assert rollbacks == [True]


def test_dotted_ticker_is_a_duplicate_before_insert_and_after_rollback(
    monkeypatch, session
):
    """``BRK.B`` is DuplicateTickerError on both lookup paths.

    The first repeat is caught before insert. The second hides that
    lookup once, so the unique index fires. SQLite's message names
    the columns, not ``uq_company_name_ticker``. The mapping reads
    the stored row after rollback and does not chain the driver
    error.
    """
    repo = CompanyRepository(session)
    repo.create(CompanyCreate(name="Berkshire Hathaway", ticker="BRK.B"))

    with pytest.raises(DuplicateTickerError) as pre_insert:
        repo.create(CompanyCreate(name="Berkshire Hathaway", ticker="BRK.B"))

    assert pre_insert.value.code == "duplicate_ticker"
    assert pre_insert.value.__cause__ is None

    original = repo.get_by_ticker
    calls = {"count": 0}

    def hide_the_first_lookup(ticker):
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return original(ticker)

    monkeypatch.setattr(repo, "get_by_ticker", hide_the_first_lookup)

    with pytest.raises(DuplicateTickerError) as raced:
        repo.create(CompanyCreate(name="Berkshire Hathaway", ticker="brk.b"))

    assert raced.value.code == "duplicate_ticker"
    assert raced.value.__cause__ is None
    assert "uq_company_name_ticker" not in str(raced.value)
    assert "UNIQUE" not in str(raced.value)
    assert (
        session.query(CompanyDB).filter(CompanyDB.ticker == "BRK.B").count()
        == 1
    )


def test_duplicate_ticker_from_integrity_error_hides_the_driver_text(
    monkeypatch, session
):
    """The pre-check is skipped once, so the unique index fires.

    The ValueError is the fixed sentence. It is not chained to the
    database error, and the second row is not kept.
    """
    repo = CompanyRepository(session)
    repo.create(CompanyCreate(name="A", ticker="DUP"))
    original = repo.get_by_ticker
    calls = {"count": 0}

    def hide_the_first_lookup(ticker):
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return original(ticker)

    monkeypatch.setattr(repo, "get_by_ticker", hide_the_first_lookup)

    with pytest.raises(
        DuplicateTickerError,
        match="^A company with this ticker already exists$",
    ) as error:
        repo.create(CompanyCreate(name="B", ticker="DUP"))

    assert isinstance(error.value, ValueError)
    assert error.value.code == "duplicate_ticker"
    assert error.value.__cause__ is None
    assert "UNIQUE" not in str(error.value)
    assert (
        session.query(CompanyDB).filter(CompanyDB.ticker == "DUP").count() == 1
    )


def test_duplicate_isin_from_integrity_error_uses_the_fixed_sentence(
    monkeypatch, session
):
    repo = CompanyRepository(session)
    repo.create(CompanyCreate(name="A", ticker="AAA", isin="US0378331005"))
    original = repo.get_by_isin
    calls = {"count": 0}

    def hide_the_first_lookup(isin):
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return original(isin)

    monkeypatch.setattr(repo, "get_by_isin", hide_the_first_lookup)

    with pytest.raises(DuplicateIsinError) as error:
        repo.create(CompanyCreate(name="B", ticker="BBB", isin="US0378331005"))

    assert error.value.code == "duplicate_isin"
    assert str(error.value) == "A company with this ISIN already exists"

    assert session.query(CompanyDB).count() == 1


def test_update_duplicate_ticker_from_integrity_error_uses_the_fixed_sentence(
    monkeypatch, session
):
    """The name/ticker pre-check is skipped, so the unique index fires.

    Update then uses the same sentence as create. The error is not
    chained to the driver, and the old ticker stays stored.
    """
    repo = CompanyRepository(session)
    first = repo.create(CompanyCreate(name="A", ticker="AAA"))
    repo.create(CompanyCreate(name="B", ticker="BBB"))
    monkeypatch.setattr(
        repo,
        "_other_company_with_name_or_ticker",
        lambda company_id, name, ticker: None,
    )

    with pytest.raises(
        DuplicateTickerError,
        match="^A company with this ticker already exists$",
    ) as error:
        repo.update(first.id, CompanyUpdate(ticker="BBB"))

    assert error.value.code == "duplicate_ticker"
    assert error.value.__cause__ is None
    assert "UNIQUE" not in str(error.value)
    stored = session.get(CompanyDB, first.id)
    assert stored.ticker == "AAA"


def test_update_duplicate_isin_from_integrity_error_uses_the_fixed_sentence(
    monkeypatch, session
):
    """The ISIN pre-check is skipped once, so the unique index fires."""
    repo = CompanyRepository(session)
    repo.create(CompanyCreate(name="A", ticker="AAA", isin="US0378331005"))
    second = repo.create(CompanyCreate(name="B", ticker="BBB"))
    original = repo.get_by_isin
    calls = {"count": 0}

    def hide_the_first_lookup(isin):
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return original(isin)

    monkeypatch.setattr(repo, "get_by_isin", hide_the_first_lookup)

    with pytest.raises(DuplicateIsinError) as error:
        repo.update(second.id, CompanyUpdate(isin="US0378331005"))

    assert error.value.code == "duplicate_isin"
    assert error.value.__cause__ is None
    assert "UNIQUE" not in str(error.value)
    stored = session.get(CompanyDB, second.id)
    assert stored.isin is None


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
