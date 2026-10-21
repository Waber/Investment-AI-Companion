"""Load and save notes for one company.

Every method takes ``company_id`` and uses it in the WHERE clause.
A note id that belongs to another company is treated as missing:
``get`` and ``update`` return ``None``, and ``delete`` returns
``False``. The row is left unchanged. That stops a tampered URL
from editing another company's note.

``create`` raises ``CompanyNotFoundError`` when the company id is
not stored. It does not raise ``IntegrityError`` for that case.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.database_models import NoteDB
from app.models.research import Note, NoteCreate, NoteUpdate
from app.repositories.research_store import (
    commit_company_scoped,
    commit_research_change,
    ensure_company_exists,
)


class NoteRepository:
    """CRUD for ``notes``, always limited to one company."""

    def __init__(self, db: Session):
        self.db = db

    def list_for_company(self, company_id: int) -> list[Note]:
        """Notes for this company, newest edit first.

        ``updated_at`` descending, then ``id`` descending, so two
        notes edited at the same time stay in a stable order. A
        company with no notes, including an unknown company id,
        returns an empty list.
        """
        rows = (
            self.db.query(NoteDB)
            .filter(NoteDB.company_id == company_id)
            .order_by(NoteDB.updated_at.desc(), NoteDB.id.desc())
            .all()
        )
        return [Note.model_validate(row) for row in rows]

    def get(self, company_id: int, note_id: int) -> Note | None:
        """Return the note, or None when it is not this company's."""
        row = self._row(company_id, note_id)
        if row is None:
            return None
        return Note.model_validate(row)

    def create(self, company_id: int, note: NoteCreate) -> Note:
        """Insert a note and return it with id and timestamps.

        Raises:
            CompanyNotFoundError: ``company_id`` is not in ``companies``.
        """
        ensure_company_exists(self.db, company_id)
        row = NoteDB(company_id=company_id, body=note.body)
        self.db.add(row)
        commit_company_scoped(self.db, company_id)
        self.db.refresh(row)
        return Note.model_validate(row)

    def update(
        self,
        company_id: int,
        note_id: int,
        note_update: NoteUpdate,
    ) -> Note | None:
        """Apply the fields the caller sent.

        An empty update (no fields) returns the stored note and does
        not move ``updated_at``. None means the note is missing or
        belongs to another company, and the row is not changed.
        """
        row = self._row(company_id, note_id)
        if row is None:
            return None
        changes = note_update.model_dump(exclude_unset=True)
        if not changes:
            return Note.model_validate(row)
        for field, value in changes.items():
            setattr(row, field, value)
        # One clock. The column has no ``onupdate``, so this UTC
        # value is the only timestamp the UPDATE writes.
        row.updated_at = datetime.now(timezone.utc)
        commit_research_change(self.db)
        self.db.refresh(row)
        return Note.model_validate(row)

    def delete(self, company_id: int, note_id: int) -> bool:
        """Delete the note. False means it was not this company's."""
        row = self._row(company_id, note_id)
        if row is None:
            return False
        self.db.delete(row)
        commit_research_change(self.db)
        return True

    def _row(self, company_id: int, note_id: int) -> NoteDB | None:
        return (
            self.db.query(NoteDB)
            .filter(NoteDB.id == note_id, NoteDB.company_id == company_id)
            .first()
        )
