"""Instrument detail: fund attributes and price-derived metrics.

The id is ``companies.id``. Issue #26 stored the instrument type on
that table and did not add a second table. Prices already live under
this path. This module adds the one attributes row and the metrics
computed from the stored closes.

A public body cannot set ``source`` or ``is_synthetic``. Create uses
``manual`` unless the demo-seed header is valid. Update always
records ``manual`` and does not read that header.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.research import ItemId
from app.core.config import settings
from app.core.database import get_db
from app.demo_seed_auth import request_is_demo_seed
from app.models.database_models import RECORD_SOURCE_DEMO, CompanyDB
from app.models.fund_attributes import (
    FundAttributes,
    FundAttributesCreate,
    FundAttributesUpdate,
)
from app.price_metrics import metrics_from_bars
from app.repositories.company_errors import CompanyNotFoundError
from app.repositories.fund_attributes_repository import (
    FundAttributesRepository,
)
from app.repositories.price_bar_repository import PriceBarRepository

router = APIRouter(prefix="/instruments", tags=["instruments"])

_NOT_FOUND = "Instrument not found"
_NO_ATTRIBUTES = "Fund attributes not found"


class DerivedMetricBody(BaseModel):
    """One computed metric, or the reason it is missing."""

    value: Optional[float] = None
    reason: Optional[str] = None
    start: Optional[date] = None
    end: Optional[date] = None
    as_of: Optional[date] = None
    source: Optional[str] = None


class PriceMetricsBody(BaseModel):
    """Returns, volatility, and drawdown for the default price series."""

    source: Optional[str] = None
    as_of: Optional[date] = None
    return_1y: DerivedMetricBody
    return_3y: DerivedMetricBody
    volatility: DerivedMetricBody
    max_drawdown: DerivedMetricBody


class InstrumentDetail(BaseModel):
    """The facts a detail page needs beyond the company row."""

    id: int
    ticker: str
    name: str
    instrument_type: Optional[str] = None
    currency: Optional[str] = None
    fund_attributes: Optional[FundAttributes] = None
    price_metrics: PriceMetricsBody


def _metric_body(metric):
    return DerivedMetricBody(
        value=metric.value,
        reason=metric.reason,
        start=metric.start,
        end=metric.end,
        as_of=metric.as_of,
        source=metric.source,
    )


def _price_metrics(db, instrument_id):
    bars = PriceBarRepository(db).get_range(instrument_id)
    derived = metrics_from_bars(bars)
    return PriceMetricsBody(
        source=derived.source,
        as_of=derived.as_of,
        return_1y=_metric_body(derived.return_1y),
        return_3y=_metric_body(derived.return_3y),
        volatility=_metric_body(derived.volatility),
        max_drawdown=_metric_body(derived.max_drawdown),
    )


def _company_or_404(db, instrument_id):
    company = db.get(CompanyDB, instrument_id)
    if company is None:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    return company


@router.get("/{instrument_id}", response_model=InstrumentDetail)
def get_instrument_detail(
    instrument_id: ItemId, db: Session = Depends(get_db)
):
    """Attributes and price-derived metrics for one instrument.

    A stock has ``fund_attributes`` null. An ETF or ETC with no row
    yet is also null. Missing is not returned as zero. ``price_metrics``
    is always present. A series that is too short has a null value and
    a reason.
    """
    company = _company_or_404(db, instrument_id)
    row = FundAttributesRepository(db).get_by_company(instrument_id)
    attributes = None if row is None else FundAttributes.model_validate(row)
    return InstrumentDetail(
        id=company.id,
        ticker=company.ticker,
        name=company.name,
        instrument_type=company.instrument_type,
        currency=company.currency,
        fund_attributes=attributes,
        price_metrics=_price_metrics(db, instrument_id),
    )


@router.get(
    "/{instrument_id}/fund-attributes",
    response_model=Optional[FundAttributes],
)
def get_fund_attributes(instrument_id: ItemId, db: Session = Depends(get_db)):
    """The one attribute row, or null when the instrument has none."""
    _company_or_404(db, instrument_id)
    row = FundAttributesRepository(db).get_by_company(instrument_id)
    if row is None:
        return None
    return FundAttributes.model_validate(row)


@router.post(
    "/{instrument_id}/fund-attributes",
    response_model=FundAttributes,
    status_code=status.HTTP_201_CREATED,
)
def create_fund_attributes(
    instrument_id: ItemId,
    attributes: FundAttributesCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Store the row. A stock is 400. A missing instrument is 404."""
    repo = FundAttributesRepository(db)
    try:
        if request_is_demo_seed(
            request,
            settings.SECRET_KEY,
            enabled=settings.DEMO_SEED_ENABLED,
        ):
            row = repo.create(
                instrument_id,
                attributes,
                record_source=RECORD_SOURCE_DEMO,
                is_synthetic=True,
            )
        else:
            row = repo.create(instrument_id, attributes)
    except CompanyNotFoundError:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return FundAttributes.model_validate(row)


@router.put(
    "/{instrument_id}/fund-attributes",
    response_model=FundAttributes,
)
def update_fund_attributes(
    instrument_id: ItemId,
    attributes: FundAttributesUpdate,
    db: Session = Depends(get_db),
):
    """Edit the row. The demo-seed header is not read.

    The stored source becomes ``manual``. ``is_synthetic`` stays as
    it was.
    """
    repo = FundAttributesRepository(db)
    try:
        row = repo.update(instrument_id, attributes)
    except CompanyNotFoundError:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    if row is None:
        raise HTTPException(status_code=404, detail=_NO_ATTRIBUTES)
    return FundAttributes.model_validate(row)
