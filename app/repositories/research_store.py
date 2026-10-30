"""Commit a note or thesis, and require the company to exist.

SQLite does not enforce a foreign key unless the connection ran
``PRAGMA foreign_keys=ON``. PostgreSQL always enforces it. Checking
the company before the insert makes ``create`` fail the same way on
both databases.

The commit helpers roll a failed write back and raise a typed error,
not the driver error. Callers catch ``CompanyNotFoundError`` and
``ResearchStorageError`` and can keep using the session.
"""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.database_models import CompanyDB, NoteDB, ThesisDB
from app.repositories.company_errors import CompanyNotFoundError


class ResearchStorageError(RuntimeError):
    """A note or thesis write failed and was rolled back.

    There is one exception: when only the refresh after the commit of
    a ``create`` fails, this is raised although the commit has already
    stored the row (see ``commit_company_scoped``).

    ``create``, ``update``, ``delete``, and ``set_status`` raise it.
    A ``create`` for a company that is not stored raises
    ``CompanyNotFoundError`` instead.

    The message is fixed. It does not include driver text, which
    differs between SQLite and PostgreSQL. This is a
    ``RuntimeError``, not a ``ValueError``. ``WatchlistStorageError``
    is a ``ValueError``, and an ``except ValueError`` that already
    handles that class must not swallow a failed note or thesis
    write.
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


def _failed_insert_error(
    db: Session, company_id: int
) -> CompanyNotFoundError | ResearchStorageError:
    """Choose the error for an insert that was already rolled back.

    The company is looked up again. A company that is gone now is
    ``CompanyNotFoundError``. If the lookup fails as well, the cause
    stays unknown, so the answer is ``ResearchStorageError``. The
    second rollback ends the failed lookup's transaction. PostgreSQL
    refuses every later statement in that transaction until then.
    """
    try:
        if missing_company(db, company_id):
            return CompanyNotFoundError(company_id)
    except SQLAlchemyError:
        db.rollback()
    return ResearchStorageError()


def commit_company_scoped(
    db: Session, company_id: int, row: NoteDB | ThesisDB
) -> None:
    """Insert one new note or thesis and load what the database set.

    The company check, the commit, and the refresh share one ``try``.
    The refresh loads the new id and the default timestamps into
    ``row``. The row is added after the check, so an unknown company
    leaves nothing pending in the session.

    ``CompanyNotFoundError`` from the check passes through. Any
    ``SQLAlchemyError`` rolls the session back, so the next call can
    use it. If the company is gone by then, for example deleted
    after the check, the error is still ``CompanyNotFoundError``.
    Every other failure is ``ResearchStorageError``. A failed
    refresh comes after the commit, so in that one case the row can
    be stored even though the call raised.

    The typed error is raised after the ``except`` block. Raised
    inside it, even with ``from None``, the error would keep the
    driver error on ``__context__``. That error's text holds the SQL
    and its parameters, which for an insert include the body. The
    company repository uses the same shape for a duplicate ticker.
    """
    failed = False
    try:
        ensure_company_exists(db, company_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    except SQLAlchemyError:
        db.rollback()
        failed = True
    if failed:
        raise _failed_insert_error(db, company_id) from None


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
