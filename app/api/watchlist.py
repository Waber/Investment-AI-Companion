"""HTTP API for the single v1 watchlist.

``GET /api/v1/watchlist/`` lists every row, oldest first.
``POST /api/v1/watchlist/`` adds a company. Adding it again returns
the same row and does not change the label. ``DELETE
/api/v1/watchlist/{company_id}`` removes that company. An unknown
company is 404.
"""

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.database_models import WatchlistItemDB
from app.models.watchlist import WatchlistItem, WatchlistItemCreate
from app.repositories.company_errors import CompanyNotFoundError
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


@router.post(
    "/",
    response_model=WatchlistItem,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "model": WatchlistItem,
            "description": "The company was added to the watchlist",
        },
        200: {
            "model": WatchlistItem,
            "description": (
                "The company was already on the watchlist. "
                "A repeat keeps the original label. A different "
                "label in this request is not stored."
            ),
        },
        404: {"description": "Company not found"},
    },
)
def add_to_watchlist(
    body: WatchlistItemCreate,
    response: Response,
    db: Session = Depends(get_db),
):
    """Add a company, or return the row that is already stored.

    The first add is 201. A repeat is 200 and keeps the original label.
    A different label in the body is not stored. That includes the
    request that loses the unique-constraint race. An unknown company,
    or one deleted before the insert, is 404.
    """
    _require_company(db, body.company_id)
    repo = WatchlistRepository(db)
    # Raised after the handler so a driver error is not chained.
    # The detail stays a fixed sentence.
    missing = False
    try:
        row, created = repo.add(body.company_id, body.label)
    except CompanyNotFoundError:
        row = None
        created = False
        missing = True
    except WatchlistStorageError:
        row = None
        created = False
    if missing:
        raise HTTPException(status_code=404, detail="Company not found")
    if row is None:
        raise HTTPException(
            status_code=500,
            detail="Watchlist item could not be stored",
        )
    response.status_code = (
        status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )
    return _to_model(row)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_watchlist(
    company_id: int = Path(gt=0), db: Session = Depends(get_db)
):
    """Remove a company from the watchlist.

    An unknown company is 404 ``Company not found``. A company that
    exists but is not listed is 404 ``Not on the watchlist``.
    ``company_id`` must be greater than zero, so 0 and -1 are 422.
    """
    _require_company(db, company_id)
    if not WatchlistRepository(db).remove(company_id):
        raise HTTPException(status_code=404, detail="Not on the watchlist")
