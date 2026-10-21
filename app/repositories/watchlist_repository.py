"""Database access for the single v1 watchlist."""

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.database_models import CompanyDB, WatchlistItemDB
from app.models.watchlist import clean_watchlist_label
from app.repositories.company_errors import CompanyNotFoundError


class WatchlistStorageError(ValueError):
    """The row could not be stored, and it was not a duplicate add.

    The message is fixed. It does not include the driver text, which
    differs between SQLite and PostgreSQL.
    """

    def __init__(self) -> None:
        super().__init__("Watchlist item could not be stored")


class WatchlistRepository:
    """Add, remove, and list watchlist rows.

    ``add`` is idempotent. A company that is already listed is returned
    unchanged, including when two requests pass the first lookup at
    the same time and the unique constraint rejects the second insert.
    """

    def __init__(self, db: Session):
        self.db = db

    def add(
        self, company_id: int, label: str | None = None
    ) -> tuple[WatchlistItemDB, bool]:
        """Return ``(row, created)`` for ``company_id``.

        ``created`` is True only when this call inserted the row. A
        second call, including the one that loses a unique-constraint
        race, returns the stored row and False. The label is not
        changed.

        A company that is gone when the insert runs raises
        ``CompanyNotFoundError``. Any other constraint failure raises
        ``WatchlistStorageError``. Both are raised after this handler,
        so ``__context__`` does not keep the SQL text. The decision
        uses the tables after the savepoint rolls back, not the
        driver message.

        The insert runs inside ``begin_nested`` (a SAVEPOINT). A
        unique-constraint failure undoes only that insert. Earlier
        pending work in this session stays, and this method does not
        commit it. A successful insert still commits the session.
        """
        existing = self.get_by_company_id(company_id)
        if existing is not None:
            return existing, False

        row = WatchlistItemDB(
            company_id=company_id,
            label=clean_watchlist_label(label),
            added_at=datetime.now(timezone.utc),
        )
        stored = None
        missing = False
        try:
            # The savepoint, not the whole session. A full rollback
            # would drop rows the caller had already flushed.
            with self.db.begin_nested():
                self.db.add(row)
                self.db.flush()
        except IntegrityError:
            # The driver text names the constraint that fired. SQLite
            # and PostgreSQL use different names. The savepoint is
            # already rolled back. A row that is already stored is the
            # race loser. No row and no company means the company was
            # deleted. Anything else is raised below, outside this
            # handler.
            stored = self.get_by_company_id(company_id)
            if stored is None:
                found = (
                    self.db.query(CompanyDB.id)
                    .filter(CompanyDB.id == company_id)
                    .first()
                )
                missing = found is None
        else:
            self.db.commit()
            self.db.refresh(row)
            return row, True
        if stored is not None:
            return stored, False
        if missing:
            raise CompanyNotFoundError(company_id) from None
        raise WatchlistStorageError() from None

    def remove(self, company_id: int) -> bool:
        """Delete the row for ``company_id``.

        Returns True when a row was deleted, False when that company
        was not on the watchlist.
        """
        row = self.get_by_company_id(company_id)
        if row is None:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    def get_by_company_id(self, company_id: int) -> WatchlistItemDB | None:
        """Return the row for this company, or None."""
        return (
            self.db.query(WatchlistItemDB)
            .filter(WatchlistItemDB.company_id == company_id)
            .first()
        )

    def contains(self, company_id: int) -> bool:
        """True when this company is already on the watchlist."""
        return self.get_by_company_id(company_id) is not None

    def list_items(self) -> list[WatchlistItemDB]:
        """Every row, oldest ``added_at`` first, then lowest id."""
        return (
            self.db.query(WatchlistItemDB)
            .order_by(WatchlistItemDB.added_at, WatchlistItemDB.id)
            .all()
        )
