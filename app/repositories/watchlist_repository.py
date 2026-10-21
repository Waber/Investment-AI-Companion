"""Database access for the single v1 watchlist."""

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.database_models import WatchlistItemDB
from app.models.watchlist import clean_watchlist_label


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
    ) -> WatchlistItemDB:
        """Return the row for ``company_id``, inserting it when missing.

        A second call does not change the stored label. When the unique
        constraint fires, the existing row is returned. Any other
        constraint failure is raised after this handler, so
        ``__context__`` does not keep the SQL text.
        """
        existing = self.get_by_company_id(company_id)
        if existing is not None:
            return existing

        row = WatchlistItemDB(
            company_id=company_id,
            label=clean_watchlist_label(label),
            added_at=datetime.now(timezone.utc),
        )
        self.db.add(row)
        stored = None
        try:
            self.db.commit()
            self.db.refresh(row)
            return row
        except IntegrityError:
            # The driver text names the constraint that fired. SQLite
            # and PostgreSQL use different names. After rollback, a row
            # that is already stored is the idempotent result. Anything
            # else, including a missing company, is raised below.
            self.db.rollback()
            stored = self.get_by_company_id(company_id)
        if stored is not None:
            return stored
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
