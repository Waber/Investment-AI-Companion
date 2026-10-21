"""Commit a note or thesis, and require the company to exist.

SQLite does not enforce a foreign key unless the connection ran
``PRAGMA foreign_keys=ON``. PostgreSQL always enforces it. Checking
the company before the insert makes ``create`` fail the same way on
both databases. A raw ``IntegrityError`` would otherwise become an
HTTP 500 once an API exists.
"""

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.database_models import CompanyDB
from app.repositories.company_errors import CompanyNotFoundError


class ResearchStorageError(ValueError):
    """A note or thesis update, delete, or status change was rolled back.

    The message is fixed. It does not include driver text, which
    differs between SQLite and PostgreSQL. There is no shared
    storage error in this tree. The watchlist's
    ``WatchlistStorageError`` lives on another branch, so this
    class is the one for notes and theses. ``create`` does not use
    it: a missing company is ``CompanyNotFoundError``.
    """

    def __init__(self) -> None:
        super().__init__("Note or thesis could not be stored")


def missing_company(db: Session, company_id: int) -> bool:
    """Return True when ``companies`` has no row with this id."""
    found = db.query(CompanyDB.id).filter(CompanyDB.id == company_id).first()
    return found is None


def ensure_company_exists(db: Session, company_id: int) -> None:
    """Raise ``CompanyNotFoundError`` when the company is not stored."""
    if missing_company(db, company_id):
        raise CompanyNotFoundError(company_id)


def commit_company_scoped(db: Session, company_id: int) -> None:
    """Commit one new note or thesis.

    The caller already ran ``ensure_company_exists``. A company that
    disappears before this commit still becomes
    ``CompanyNotFoundError``. Any other integrity error is re-raised
    after rollback, so the session can be used again.

    The missing-company error is raised after the ``except`` block.
    Raising it inside the block would keep the driver error on
    ``__context__``. The company repository uses the same shape for
    a duplicate ticker.
    """
    missing = False
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        missing = missing_company(db, company_id)
        if not missing:
            raise
    if missing:
        raise CompanyNotFoundError(company_id) from None


def commit_research_change(db: Session) -> None:
    """Commit an update, delete, or status change.

    ``SQLAlchemyError`` covers a locked database, a broken
    connection, and a CHECK failure. The session is rolled back
    so the next call can use it. The typed error is raised after
    this handler. Raising it inside the ``except`` would keep the
    driver text on ``__context__``.
    """
    failed = False
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        failed = True
    if failed:
        raise ResearchStorageError() from None
