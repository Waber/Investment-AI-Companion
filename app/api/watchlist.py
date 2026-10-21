"""HTTP API for the single v1 watchlist.

``GET /api/v1/watchlist/`` lists every row, oldest first.
``POST /api/v1/watchlist/`` adds a company. Adding it again returns
the same row and does not change the label. ``DELETE
/api/v1/watchlist/{company_id}`` removes that company. An unknown
company is 404.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.database_models import WatchlistItemDB
from app.models.watchlist import WatchlistItem, WatchlistItemCreate
from app.repositories.company_repository import CompanyRepository
from app.repositories.watchlist_repository import (
    WatchlistRepository,
    WatchlistStorageError,
)

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


def _to_model(row: WatchlistItemDB) -> WatchlistItem:
    """Copy a database row into the read model."""
    return WatchlistItem.model_validate(row)


def _require_company(db: Session, company_id: int) -> None:
    """404 when this id is not a company."""
    if CompanyRepository(db).get_by_id(company_id) is None:
        raise HTTPException(status_code=404, detail="Company not found")


@router.get("/", response_model=list[WatchlistItem])
def list_watchlist(db: Session = Depends(get_db)):
    """Return the whole watchlist, oldest ``added_at`` first."""
    rows = WatchlistRepository(db).list_items()
    return [_to_model(row) for row in rows]


@router.post("/", response_model=WatchlistItem)
def add_to_watchlist(
    body: WatchlistItemCreate,
    response: Response,
    db: Session = Depends(get_db),
):
    """Add a company, or return the row that is already stored.

    The first add is 201. A repeat is 200 and keeps the original
    label. An unknown company is 404.
    """
    _require_company(db, body.company_id)
    repo = WatchlistRepository(db)
    existed = repo.contains(body.company_id)
    # Raised after the handler so the storage error is not chained.
    # The detail stays the fixed sentence.
    try:
        row = repo.add(body.company_id, body.label)
    except WatchlistStorageError:
        row = None
    if row is None:
        raise HTTPException(
            status_code=500,
            detail="Watchlist item could not be stored",
        ) from None
    response.status_code = (
        status.HTTP_200_OK if existed else status.HTTP_201_CREATED
    )
    return _to_model(row)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_watchlist(company_id: int, db: Session = Depends(get_db)):
    """Remove a company from the watchlist.

    An unknown company is 404 ``Company not found``. A company that
    exists but is not listed is 404 ``Not on the watchlist``.
    """
    _require_company(db, company_id)
    if not WatchlistRepository(db).remove(company_id):
        raise HTTPException(status_code=404, detail="Not on the watchlist")
