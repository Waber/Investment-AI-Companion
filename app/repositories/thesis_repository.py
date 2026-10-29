"""Load and save investment theses for one company.

The methods match ``NoteRepository``: every read and write is
limited to one ``company_id``. A thesis that belongs to another
company looks missing. ``create`` raises ``CompanyNotFoundError``
when that company is not stored, and ``ResearchStorageError`` when
the insert fails for another reason.

``set_status`` closes or reopens a thesis without editing the text.
``list_for_company`` can return every status, or only one.

``closed_at`` follows the status. Closing sets it to the same instant
as ``updated_at``. Reopening clears it. Saving the status a thesis
already has leaves it alone. That holds for ``set_status`` and for an
``update`` that sends a status. ``create`` is different: a thesis
created closed takes ``closed_at`` from the Python clock, while
``updated_at`` keeps the database default, so the two can differ
slightly.
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
    commit_research_change,
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

        ``created_at`` and ``updated_at`` come from the database
        default. ``closed_at`` has no default, so a thesis created
        closed takes it from the Python clock here. On this one path
        ``closed_at`` can differ slightly from ``updated_at``.

        Raises:
            CompanyNotFoundError: ``company_id`` is not in ``companies``.
            ResearchStorageError: the insert failed and was rolled back.
        """
        status = _status_value(thesis.status)
        closed_at = None
        if status == ThesisStatus.CLOSED.value:
            closed_at = datetime.now(timezone.utc)
        row = ThesisDB(
            company_id=company_id,
            title=thesis.title,
            body=thesis.body,
            thesis_breakers=thesis.thesis_breakers,
            status=status,
            closed_at=closed_at,
        )
        commit_company_scoped(self.db, company_id, row)
        return Thesis.model_validate(row)

    def update(
        self,
        company_id: int,
        thesis_id: int,
        thesis_update: ThesisUpdate,
    ) -> Thesis | None:
        """Apply the fields the caller sent.

        An empty update returns the stored thesis and does not move
        ``updated_at``. A status that differs from the stored one
        also sets or clears ``closed_at``, as ``set_status`` does.
        None means the thesis is missing or belongs to another
        company.
        """
        row = self._row(company_id, thesis_id)
        if row is None:
            return None
        changes = thesis_update.model_dump(exclude_unset=True)
        if not changes:
            return Thesis.model_validate(row)
        # The status is written by the helper below, next to the
        # clocks, so ``closed_at`` can follow it. An edit that does
        # not send a status keeps the stored one.
        status = row.status
        if "status" in changes:
            status = _status_value(changes.pop("status"))
        for field, value in changes.items():
            setattr(row, field, value)
        self._set_status_and_clocks(row, status)
        commit_research_change(self.db)
        self.db.refresh(row)
        return Thesis.model_validate(row)

    def set_status(
        self,
        company_id: int,
        thesis_id: int,
        status: ThesisStatus,
    ) -> Thesis | None:
        """Close or reopen a thesis.

        Closing sets ``closed_at`` to the new ``updated_at``.
        Reopening clears it. Writing the status the row already has
        returns the thesis and moves neither ``updated_at`` nor
        ``closed_at``. None means the thesis is missing or belongs
        to another company, and the row is not changed.
        """
        row = self._row(company_id, thesis_id)
        if row is None:
            return None
        value = _status_value(status)
        if row.status == value:
            return Thesis.model_validate(row)
        self._set_status_and_clocks(row, value)
        commit_research_change(self.db)
        self.db.refresh(row)
        return Thesis.model_validate(row)

    def delete(self, company_id: int, thesis_id: int) -> bool:
        """Delete the thesis. False means it was not this company's."""
        row = self._row(company_id, thesis_id)
        if row is None:
            return False
        self.db.delete(row)
        commit_research_change(self.db)
        return True

    @staticmethod
    def _set_status_and_clocks(row: ThesisDB, status: str) -> None:
        """Write ``status``, ``updated_at``, and ``closed_at`` from one clock.

        ``status`` is the stored string from ``_status_value``. One
        ``now`` feeds both timestamps. Neither column has an
        ``onupdate``, so nothing else moves them after the insert.
        ``updated_at`` always moves. ``closed_at`` moves only when
        the status changes: closing sets it to that same instant,
        and reopening clears it. A closed thesis that is edited
        keeps its date.
        """
        now = datetime.now(timezone.utc)
        if status != row.status:
            closing = status == ThesisStatus.CLOSED.value
            row.closed_at = now if closing else None
        row.status = status
        row.updated_at = now

    def _row(self, company_id: int, thesis_id: int) -> ThesisDB | None:
        return (
            self.db.query(ThesisDB)
            .filter(
                ThesisDB.id == thesis_id,
                ThesisDB.company_id == company_id,
            )
            .first()
        )
