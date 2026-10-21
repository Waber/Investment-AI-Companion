"""Load and save investment theses for one company.

The methods match ``NoteRepository``: every read and write is
limited to one ``company_id``. A thesis that belongs to another
company looks missing. ``create`` raises ``CompanyNotFoundError``
when that company is not stored.

``set_status`` closes or reopens a thesis without editing the text.
``list_for_company`` can return every status, or only one.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.database_models import ThesisDB
from app.models.research import (
    Thesis,
    ThesisCreate,
    ThesisStatus,
    ThesisUpdate,
)
from app.repositories.research_store import (
    commit_company_scoped,
    ensure_company_exists,
)


def _status_value(status: ThesisStatus) -> str:
    """Store the enum as the lowercase string the column expects.

    A plain ``'active'`` or ``'closed'`` is accepted too, because
    ``ThesisStatus`` is a ``str`` enum. Anything else raises
    ``ValueError`` from the enum constructor.
    """
    if not isinstance(status, ThesisStatus):
        status = ThesisStatus(status)
    return status.value


class ThesisRepository:
    """CRUD for ``theses``, always limited to one company."""

    def __init__(self, db: Session):
        self.db = db

    def list_for_company(
        self,
        company_id: int,
        status: ThesisStatus | None = None,
    ) -> list[Thesis]:
        """Theses for this company, newest edit first.

        ``status=None`` returns active and closed. A value filters
        to that status. The order is ``updated_at`` descending, then
        ``id`` descending. An unknown company returns an empty list.
        """
        query = self.db.query(ThesisDB).filter(
            ThesisDB.company_id == company_id
        )
        if status is not None:
            query = query.filter(ThesisDB.status == _status_value(status))
        rows = query.order_by(
            ThesisDB.updated_at.desc(),
            ThesisDB.id.desc(),
        ).all()
        return [Thesis.model_validate(row) for row in rows]

    def get(self, company_id: int, thesis_id: int) -> Thesis | None:
        """Return the thesis, or None when it is not this company's."""
        row = self._row(company_id, thesis_id)
        if row is None:
            return None
        return Thesis.model_validate(row)

    def create(self, company_id: int, thesis: ThesisCreate) -> Thesis:
        """Insert a thesis and return it with id and timestamps.

        Raises:
            CompanyNotFoundError: ``company_id`` is not in ``companies``.
        """
        ensure_company_exists(self.db, company_id)
        row = ThesisDB(
            company_id=company_id,
            title=thesis.title,
            body=thesis.body,
            thesis_breakers=thesis.thesis_breakers,
            status=_status_value(thesis.status),
        )
        self.db.add(row)
        commit_company_scoped(self.db, company_id)
        self.db.refresh(row)
        return Thesis.model_validate(row)

    def update(
        self,
        company_id: int,
        thesis_id: int,
        thesis_update: ThesisUpdate,
    ) -> Thesis | None:
        """Apply the fields the caller sent.

        An empty update returns the stored thesis and does not move
        ``updated_at``. None means the thesis is missing or belongs
        to another company.
        """
        row = self._row(company_id, thesis_id)
        if row is None:
            return None
        changes = thesis_update.model_dump(exclude_unset=True)
        if not changes:
            return Thesis.model_validate(row)
        if "status" in changes:
            changes["status"] = _status_value(changes["status"])
        for field, value in changes.items():
            setattr(row, field, value)
        row.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return Thesis.model_validate(row)

    def set_status(
        self,
        company_id: int,
        thesis_id: int,
        status: ThesisStatus,
    ) -> Thesis | None:
        """Close or reopen a thesis.

        Writing the status the row already has returns the thesis
        and does not move ``updated_at``. None means the thesis is
        missing or belongs to another company, and the row is not
        changed.
        """
        row = self._row(company_id, thesis_id)
        if row is None:
            return None
        value = _status_value(status)
        if row.status == value:
            return Thesis.model_validate(row)
        row.status = value
        row.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return Thesis.model_validate(row)

    def delete(self, company_id: int, thesis_id: int) -> bool:
        """Delete the thesis. False means it was not this company's."""
        row = self._row(company_id, thesis_id)
        if row is None:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    def _row(self, company_id: int, thesis_id: int) -> ThesisDB | None:
        return (
            self.db.query(ThesisDB)
            .filter(
                ThesisDB.id == thesis_id,
                ThesisDB.company_id == company_id,
            )
            .first()
        )
