"""HTTP API for the notes and investment theses of one instrument.

The instrument id is ``companies.id``, as in ``app/api/prices.py``.
``notes_router`` serves ``/instruments/{instrument_id}/notes`` and
``theses_router`` serves ``/instruments/{instrument_id}/theses``.
``main.py`` mounts both under ``/api/v1``.

Every route checks in the same order:

1. The instrument. An unknown one is 404 ``Instrument not found``.
   Its list is that 404 as well, never an empty list.
2. The repository call. It is limited to this instrument, so a note
   or thesis of another instrument looks missing.
3. A missing note or thesis is 404 ``Note not found`` or
   ``Thesis not found``.
4. ``CompanyNotFoundError`` means the company was deleted after the
   first check. That is the instrument 404 too.
5. ``ResearchStorageError`` is 500 ``Note or thesis could not be
   stored``. Nothing else from the exception is sent.

Only the writes raise those two errors. A failed read is FastAPI's
generic 500.

``PUT`` is a partial update: send only the fields to change. An empty
JSON object returns the stored item unchanged. A thesis ``PUT`` may
carry ``status``, which is how this API closes and reopens a thesis.
Lists keep the repository order, newest edit first. The text rules
(length, blank, line breaks, unknown keys) live in the write models
in ``app/models/research.py``. The routes add none of their own.

There is no origin check, as on every other API route. The app
listens on loopback only until there is a login (#48).
"""

from typing import Annotated, Callable, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.research import (
    Note,
    NoteCreate,
    NoteUpdate,
    Thesis,
    ThesisCreate,
    ThesisStatus,
    ThesisUpdate,
)
from app.repositories.company_errors import CompanyNotFoundError
from app.repositories.company_repository import CompanyRepository
from app.repositories.note_repository import NoteRepository
from app.repositories.research_store import ResearchStorageError
from app.repositories.thesis_repository import ThesisRepository

notes_router = APIRouter(prefix="/instruments", tags=["notes"])
theses_router = APIRouter(prefix="/instruments", tags=["theses"])

_NO_INSTRUMENT = "Instrument not found"
_NO_NOTE = "Note not found"
_NO_THESIS = "Thesis not found"
_NOT_STORED = "Note or thesis could not be stored"

# ``Annotated`` adds FastAPI's ``Path`` limits to ``int``, the way
# ``Skip`` and ``Limit`` do in ``app/api/pagination.py``. SQLite
# stores an INTEGER in a signed 64-bit value, so 2**63 - 1 is the
# largest id. A larger number would reach the driver and fail with a
# 500. Zero, a negative number, and text fail too. All of them are
# FastAPI's 422, before the route runs.
ItemId = Annotated[int, Path(gt=0, le=2**63 - 1)]

# Whatever the repository call returns. ``_write`` returns the same.
T = TypeVar("T")


def _require_instrument(db: Session, instrument_id: int) -> None:
    """404 when this id is not a stored instrument."""
    if CompanyRepository(db).get_by_id(instrument_id) is None:
        raise HTTPException(status_code=404, detail=_NO_INSTRUMENT)


def _write(call: Callable[[], T]) -> T:
    """Run one repository write and turn its typed errors into HTTP.

    ``call`` takes no arguments. The routes pass a ``lambda`` around
    the repository method, like a ``Supplier`` in Java. Its result is
    returned unchanged, so ``None`` or ``False`` for a missing item
    is left to the route. Any other exception is not caught.

    The HTTP error is raised after the ``except`` block, as in
    ``app/api/watchlist.py``. Raised inside it, the HTTP error would
    keep the repository error on ``__context__``. ``from None`` only
    hides that error from a printed traceback; it stays on
    ``__context__``.
    """
    try:
        return call()
    except CompanyNotFoundError:
        # The company was deleted after ``_require_instrument``.
        error = HTTPException(status_code=404, detail=_NO_INSTRUMENT)
    except ResearchStorageError:
        error = HTTPException(status_code=500, detail=_NOT_STORED)
    raise error


@notes_router.get("/{instrument_id}/notes", response_model=list[Note])
def list_notes(instrument_id: ItemId, db: Session = Depends(get_db)):
    """Notes of one instrument, newest edit first, then the higher id."""
    _require_instrument(db, instrument_id)
    return NoteRepository(db).list_for_company(instrument_id)


@notes_router.post(
    "/{instrument_id}/notes",
    response_model=Note,
    status_code=status.HTTP_201_CREATED,
)
def create_note(
    instrument_id: ItemId,
    note: NoteCreate,
    db: Session = Depends(get_db),
):
    """Add a note to an instrument."""
    _require_instrument(db, instrument_id)
    return _write(lambda: NoteRepository(db).create(instrument_id, note))


@notes_router.get("/{instrument_id}/notes/{note_id}", response_model=Note)
def get_note(
    instrument_id: ItemId,
    note_id: ItemId,
    db: Session = Depends(get_db),
):
    """Return one note of this instrument."""
    _require_instrument(db, instrument_id)
    note = NoteRepository(db).get(instrument_id, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail=_NO_NOTE)
    return note


@notes_router.put("/{instrument_id}/notes/{note_id}", response_model=Note)
def update_note(
    instrument_id: ItemId,
    note_id: ItemId,
    changes: NoteUpdate,
    db: Session = Depends(get_db),
):
    """Change the body. An empty JSON object changes nothing."""
    _require_instrument(db, instrument_id)
    repo = NoteRepository(db)
    note = _write(lambda: repo.update(instrument_id, note_id, changes))
    if note is None:
        raise HTTPException(status_code=404, detail=_NO_NOTE)
    return note


@notes_router.delete(
    "/{instrument_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_note(
    instrument_id: ItemId,
    note_id: ItemId,
    db: Session = Depends(get_db),
):
    """Delete a note. There is no undo."""
    _require_instrument(db, instrument_id)
    repo = NoteRepository(db)
    if not _write(lambda: repo.delete(instrument_id, note_id)):
        raise HTTPException(status_code=404, detail=_NO_NOTE)


@theses_router.get("/{instrument_id}/theses", response_model=list[Thesis])
def list_theses(
    instrument_id: ItemId,
    status: ThesisStatus | None = None,
    db: Session = Depends(get_db),
):
    """Theses of one instrument, newest edit first, then the higher id.

    ``?status=active`` or ``?status=closed`` lists only that status.
    Any other value is 422. Without it, both are listed.
    """
    # ``status`` is the query parameter. Inside this function it hides
    # the ``fastapi.status`` module, which this function does not use.
    _require_instrument(db, instrument_id)
    return ThesisRepository(db).list_for_company(instrument_id, status)


@theses_router.post(
    "/{instrument_id}/theses",
    response_model=Thesis,
    status_code=status.HTTP_201_CREATED,
)
def create_thesis(
    instrument_id: ItemId,
    thesis: ThesisCreate,
    db: Session = Depends(get_db),
):
    """Add a thesis. It is ``active`` unless the body says ``closed``."""
    _require_instrument(db, instrument_id)
    return _write(lambda: ThesisRepository(db).create(instrument_id, thesis))


@theses_router.get(
    "/{instrument_id}/theses/{thesis_id}", response_model=Thesis
)
def get_thesis(
    instrument_id: ItemId,
    thesis_id: ItemId,
    db: Session = Depends(get_db),
):
    """Return one thesis of this instrument."""
    _require_instrument(db, instrument_id)
    thesis = ThesisRepository(db).get(instrument_id, thesis_id)
    if thesis is None:
        raise HTTPException(status_code=404, detail=_NO_THESIS)
    return thesis


@theses_router.put(
    "/{instrument_id}/theses/{thesis_id}", response_model=Thesis
)
def update_thesis(
    instrument_id: ItemId,
    thesis_id: ItemId,
    changes: ThesisUpdate,
    db: Session = Depends(get_db),
):
    """Change the fields sent. An empty JSON object changes nothing.

    ``status`` closes or reopens the thesis. Closing sets
    ``closed_at``, and reopening clears it.
    """
    _require_instrument(db, instrument_id)
    repo = ThesisRepository(db)
    thesis = _write(lambda: repo.update(instrument_id, thesis_id, changes))
    if thesis is None:
        raise HTTPException(status_code=404, detail=_NO_THESIS)
    return thesis


@theses_router.delete(
    "/{instrument_id}/theses/{thesis_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_thesis(
    instrument_id: ItemId,
    thesis_id: ItemId,
    db: Session = Depends(get_db),
):
    """Delete a thesis. There is no undo."""
    _require_instrument(db, instrument_id)
    repo = ThesisRepository(db)
    if not _write(lambda: repo.delete(instrument_id, thesis_id)):
        raise HTTPException(status_code=404, detail=_NO_THESIS)
