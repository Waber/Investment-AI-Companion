"""Read stored prices and refresh them from the configured collector.

The id in the path is an instrument id. Today that is ``companies.id``:
issue #26 stored the instrument type on the companies table and did
not add a second table. A missing id is 404. An instrument that
exists and has no bars is 200 with an empty list, because "no bars
yet" is different from "no such instrument".

Prices are not a recommendation. The payload is the stored session
and its provenance (source and retrieval time).
"""

import logging
from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.api.data_collection import get_collector
from app.core.database import get_db
from app.core.utc_datetime import as_utc
from app.data_collectors.base import PriceBar as CollectedPriceBar
from app.data_collectors.base import ProviderError
from app.models.price_bar import PriceBar, PriceBarCreate
from app.repositories.company_repository import CompanyRepository
from app.repositories.price_bar_repository import (
    PriceBarRepository,
    _remember_skip,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/instruments", tags=["prices"])

_NO_INSTRUMENT = "Instrument not found"
_NO_PRICES = "No price data for this instrument"
_PROVIDER_ERROR = "Data provider error"
# One warning per bar id for this process. Listing the series again
# must not repeat it. The dict and the cap live with
# ``_remember_skip``: oldest ids are dropped so the process does
# not keep every skipped id. Showing the skipped bars in the
# response waits for the server phase (#93). The response shape
# stays a list of bars.
_logged_skip_ids: dict = {}


class PriceRefreshResult(BaseModel):
    """What one refresh wrote. Counts are rows, not a rating."""

    instrument_id: int
    source: str = Field(
        ..., description="Provenance source stored on the bars"
    )
    retrieved_at: str = Field(
        ..., description="Retrieval time stored on the bars, UTC"
    )
    bar_count: int = Field(
        ...,
        description=(
            "Bars inserted or updated by this refresh. "
            "A repeated date and source in one refresh counts once."
        ),
    )


def db_to_price(row) -> PriceBar:
    """Copy a ``PriceBarDB`` row into the API model.

    The database column is ``bar_date`` so it is not named ``date``,
    which is both a Python type and a SQL type. The API field is
    ``date``, which is the word the issue uses for the session.
    """
    return PriceBar(
        id=row.id,
        instrument_id=row.instrument_id,
        date=row.bar_date,
        open=row.open_price,
        high=row.high_price,
        low=row.low_price,
        close=row.close_price,
        volume=row.volume,
        currency=row.currency,
        source=row.source,
        retrieved_at=row.retrieved_at,
    )


def _require_instrument(db: Session, instrument_id: int):
    company = CompanyRepository(db).get_by_id(instrument_id)
    if company is None:
        raise HTTPException(status_code=404, detail=_NO_INSTRUMENT)
    return company


@router.get("/{instrument_id}/prices", response_model=List[PriceBar])
def list_prices(
    instrument_id: int,
    start: Optional[date] = Query(
        None,
        alias="from",
        description="First session date to include.",
    ),
    end: Optional[date] = Query(
        None,
        alias="to",
        description="Last session date to include.",
    ),
    source: Optional[str] = Query(
        None,
        description=(
            "Provenance source to return. When omitted, one source "
            "is chosen from every bar of this instrument: the latest "
            "retrieved_at, including bars outside from and to. If two "
            "sources share that time, the source name that sorts last "
            "is used. The date window is applied after that choice."
        ),
    ),
    db: Session = Depends(get_db),
):
    """Return stored bars for one instrument, oldest session first.

    ``from`` and ``to`` are inclusive calendar dates. Omit them to
    leave that side open. The list is not paged: a weekly series of
    a few years, or one year of daily bars from the fake collector,
    fits in one response on this local app.

    One session can be stored under two sources. The default response
    is still a single series. That series is chosen from every stored
    bar, then ``from`` and ``to`` keep the sessions inside the window.
    Pass ``source`` to read the other series.
    """
    _require_instrument(db, instrument_id)
    if start is not None and end is not None and start > end:
        raise HTTPException(
            status_code=422,
            detail="from must be on or before to",
        )
    if source is not None:
        source = source.strip()
        if not source:
            raise HTTPException(
                status_code=422, detail="source must not be blank"
            )
    rows = PriceBarRepository(db).get_range(instrument_id, start, end, source)
    return _bars_or_skip(rows, instrument_id)


@router.post(
    "/{instrument_id}/prices",
    response_model=PriceBar,
    status_code=status.HTTP_201_CREATED,
)
def create_price(
    instrument_id: int,
    bar: PriceBarCreate,
    db: Session = Depends(get_db),
):
    """Store one bar. The demo seeder calls this once per fixture row.

    A second POST with the same date and source is 400. Use the
    refresh route to update bars that came from the collector.
    """
    _require_instrument(db, instrument_id)
    try:
        row = PriceBarRepository(db).create(instrument_id, bar)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return db_to_price(row)


@router.post(
    "/{instrument_id}/prices/refresh",
    response_model=PriceRefreshResult,
)
def refresh_prices(
    instrument_id: int,
    db: Session = Depends(get_db),
    collector=Depends(get_collector),
):
    """Pull bars from the configured collector and upsert them.

    ``DATA_COLLECTOR=fake`` (the demo and the tests) never calls the
    network. The collector's bars have no currency of their own, so
    the currency stored is the instrument's currency. The source and
    the retrieval time come from the collector's provenance.

    Running this twice does not insert a second copy of the same
    session. The unique key is the instrument, the date, and the
    source.
    """
    company = _require_instrument(db, instrument_id)
    ticker = company.ticker
    try:
        result = collector.fetch_price_history(ticker)
    except ProviderError:
        logger.error("Data provider error for ticker %r", ticker)
        raise HTTPException(status_code=502, detail=_PROVIDER_ERROR)
    except ValidationError:
        # ValidationError is a ValueError. It has to be caught first,
        # or the next handler would call it an unsupported request.
        # The message lists the provider's values, so it is not the
        # response and it is not the log line.
        logger.error(
            "Invalid price data from the collector for ticker %r",
            ticker,
        )
        raise HTTPException(status_code=502, detail=_PROVIDER_ERROR)
    except ValueError as exc:
        # The collector rejects a period or interval it does not
        # implement. This route uses the collector's own defaults,
        # so this is a programming error in the request we send,
        # not text to show from a provider.
        logger.error(
            "Price refresh rejected for ticker %r (%s)",
            ticker,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=422, detail="Unsupported price request"
        )
    except Exception as exc:
        logger.error(
            "Unexpected %s fetching prices for ticker %r",
            type(exc).__name__,
            ticker,
        )
        raise HTTPException(status_code=502, detail=_PROVIDER_ERROR)

    if result is None or not result.value:
        raise HTTPException(status_code=404, detail=_NO_PRICES)

    provenance = result.provenance
    currency = company.currency or "USD"
    try:
        payload = [
            _bar_from_collector(bar, currency, provenance)
            for bar in result.value
        ]
        stored = PriceBarRepository(db).upsert_many(instrument_id, payload)
    except ValidationError:
        # The text of this error includes the provider's values.
        # The client gets a fixed sentence. The log names the ticker
        # and not those values.
        logger.error(
            "Provider returned invalid price data for ticker %r", ticker
        )
        raise HTTPException(
            status_code=502,
            detail="Provider returned invalid price data",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    retrieved = as_utc(provenance.retrieved_at)
    return PriceRefreshResult(
        instrument_id=instrument_id,
        source=provenance.source,
        retrieved_at=retrieved.isoformat().replace("+00:00", "Z"),
        bar_count=len(stored),
    )


def _bars_or_skip(rows, instrument_id: int) -> List[PriceBar]:
    """Build the response, dropping a bar the model cannot return.

    The repository already drops a cell that is not a decimal. This
    is the second net: a decimal the write model rejects (for example
    a hand-inserted price outside Numeric(20, 8)) must not turn the
    whole series into HTTP 500. The other bars are still returned.
    """
    loaded = []
    for row in rows:
        try:
            loaded.append(db_to_price(row))
        except (ValidationError, ValueError):
            bar_id = getattr(row, "id", None)
            if _remember_skip(_logged_skip_ids, bar_id):
                logger.warning(
                    "Skipping price bar id=%s instrument_id=%s: "
                    "stored price cannot be returned",
                    bar_id,
                    instrument_id,
                )
    return loaded


def _decimal_price(value):
    """Turn a collector float into a Decimal the price model accepts.

    Collector bars use ``float`` because that is what the provider
    libraries return. ``Decimal(str(value))`` keeps the short decimal
    Python prints, so ``0.1`` stays ``0.1``. ``Decimal(value)`` would
    keep the binary expansion instead. ``None`` stays ``None``. The
    price model then rounds to Numeric(20, 8).
    """
    if value is None or isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    return Decimal(str(value))


def _bar_from_collector(bar: CollectedPriceBar, currency: str, provenance):
    """Map one collector bar onto the stored shape.

    A missing OHLC or volume stays ``None``. It is not replaced
    with zero. Prices are decimals. Volume stays an int.
    """
    return PriceBarCreate(
        date=bar.day,
        open=_decimal_price(bar.open),
        high=_decimal_price(bar.high),
        low=_decimal_price(bar.low),
        close=_decimal_price(bar.close),
        volume=bar.volume,
        currency=currency,
        source=provenance.source,
        retrieved_at=provenance.retrieved_at,
    )
