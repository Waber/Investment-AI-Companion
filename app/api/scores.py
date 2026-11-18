"""Instrument score and the weight set for each instrument type.

The score is computed for this request. It is not stored. Version 1
is the built-in equal weight set. A PUT stores a new version and the
next score uses it.

JSON writes are not browser forms. This module does not check
``Origin`` and it does not read the demo-seed header. Those checks
belong to ``/ui`` and to creates that record a source.
"""

import json
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.research import ItemId
from app.core.database import get_db
from app.instrument_score import load_score_inputs
from app.models.database_models import CompanyDB
from app.repositories.score_weights_repository import (
    ScoreWeightsReadError,
    ScoreWeightsRepository,
    ScoreWeightsSaveError,
)
from app.scoring import (
    WeightValidationError,
    component_names,
    parse_weights,
    score_instrument,
)

router = APIRouter(tags=["scores"])

_NOT_FOUND = "Instrument not found"
_UNKNOWN_TYPE = "Unknown instrument type"
_NOT_OBJECT = "Score weights must be an object"
_UNREADABLE = "Score weights could not be read"
_SAVE_FAILED = "Score weights could not be saved"
_TYPES = frozenset({"STOCK", "ETF", "ETC"})
_MESSAGES = {
    "not_an_object": _NOT_OBJECT,
    "unknown_field": "Unknown score field",
    "missing_weights": "Score weights are required",
    "weights_not_object": _NOT_OBJECT,
    "unknown_component": "Unknown score component",
    "missing_component": "Score weights must include every component",
    "not_a_number": "Score weights must be finite numbers",
    "out_of_range": "A score weight must be from 0 to 1000000",
    "all_zero": "Score weights cannot all be zero",
    "unknown_type": _UNKNOWN_TYPE,
}


class ScoreInput(BaseModel):
    """One stored figure that a component uses."""

    name: str
    value: Optional[str] = None
    normalized: Optional[str] = None
    status: str
    label: Optional[str] = None
    source: Optional[str] = None
    as_of: Optional[date] = None


class ScoreComponent(BaseModel):
    """One part of the total, including a part that was left out."""

    name: str
    status: str
    label: Optional[str] = None
    normalized: Optional[str] = None
    weight: float
    effective_weight: Optional[str] = None
    contribution: Optional[str] = None
    source: Optional[str] = None
    as_of: Optional[date] = None
    inputs: list[ScoreInput]


class ScoreCoverage(BaseModel):
    """How many components entered the total."""

    available: int
    total: int
    label: str


class InstrumentScore(BaseModel):
    """The score for one instrument on one day.

    ``total`` is null when ``status`` is ``no_score``.
    """

    instrument_id: int
    ticker: str
    instrument_type: str
    status: str
    total: Optional[str] = None
    coverage: ScoreCoverage
    oldest_input_date: Optional[date] = None
    weight_set_version: int
    scored_on: date
    components: list[ScoreComponent]


class ScoreWeightSet(BaseModel):
    """The weight set currently used for one instrument type."""

    instrument_type: str
    version: int
    stored: bool
    weights: dict[str, float]


def utc_today():
    """The UTC date freshness is counted back from."""
    return datetime.now(timezone.utc).date()


def _text(number):
    if number is None:
        return None
    return format(number, "f")


def _weight_numbers(instrument_type, weights):
    numbers = {}
    for name in component_names(instrument_type):
        number = weights[name]
        if number == int(number):
            numbers[name] = int(number)
        else:
            numbers[name] = float(number)
    return numbers


def _component_body(component):
    return ScoreComponent(
        name=component.name,
        status=component.status,
        label=component.label,
        normalized=_text(component.normalized),
        weight=float(component.weight),
        effective_weight=_text(component.effective_weight),
        contribution=_text(component.contribution),
        source=component.source,
        as_of=component.as_of,
        inputs=[
            ScoreInput(
                name=item.name,
                value=_text(item.value),
                normalized=_text(item.normalized),
                status=item.status,
                label=item.label,
                source=item.source,
                as_of=item.as_of,
            )
            for item in component.inputs
        ],
    )


def _score_body(company, result, version, on_date):
    return InstrumentScore(
        instrument_id=company.id,
        ticker=company.ticker,
        instrument_type=company.instrument_type,
        status=result.status,
        total=_text(result.total),
        coverage=ScoreCoverage(
            available=result.coverage_available,
            total=result.coverage_total,
            label=result.coverage_label,
        ),
        oldest_input_date=result.oldest_input_date,
        weight_set_version=version,
        scored_on=on_date,
        components=[_component_body(item) for item in result.components],
    )


def _weight_body(instrument_type, weights, version, stored):
    return ScoreWeightSet(
        instrument_type=instrument_type,
        version=version,
        stored=stored,
        weights=_weight_numbers(instrument_type, weights),
    )


@router.get(
    "/instruments/{instrument_id}/score",
    response_model=InstrumentScore,
)
def get_instrument_score(instrument_id: ItemId, db: Session = Depends(get_db)):
    """The score for one instrument, computed from stored figures.

    A missing figure is left out. The total is null when nothing
    usable remains. The weight-set version is the one this total used.
    """
    company = db.get(CompanyDB, instrument_id)
    if company is None:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    if company.instrument_type not in _TYPES:
        raise HTTPException(status_code=422, detail=_UNKNOWN_TYPE)
    on_date = utc_today()
    try:
        weights, version, _stored = ScoreWeightsRepository(db).load(
            company.instrument_type
        )
    except ScoreWeightsReadError:
        raise HTTPException(status_code=500, detail=_UNREADABLE) from None
    result = score_instrument(
        company.instrument_type,
        load_score_inputs(db, company),
        weights,
        on_date,
    )
    return _score_body(company, result, version, on_date)


@router.get(
    "/score-weights/{instrument_type}",
    response_model=ScoreWeightSet,
)
def get_score_weights(instrument_type: str, db: Session = Depends(get_db)):
    """The weight set for STOCK, ETF, or ETC.

    No stored row means version 1 and the built-in equal weights.
    """
    if instrument_type not in _TYPES:
        raise HTTPException(status_code=422, detail=_UNKNOWN_TYPE)
    try:
        weights, version, stored = ScoreWeightsRepository(db).load(
            instrument_type
        )
    except ScoreWeightsReadError:
        raise HTTPException(status_code=500, detail=_UNREADABLE) from None
    return _weight_body(instrument_type, weights, version, stored)


@router.put(
    "/score-weights/{instrument_type}",
    response_model=ScoreWeightSet,
)
async def put_score_weights(
    instrument_type: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Replace the weight set and increase its version.

    The first saved set is version 2. The numbers are stored as sent.
    Scoring divides the ones it can use by their sum.
    """
    if instrument_type not in _TYPES:
        raise HTTPException(status_code=422, detail=_UNKNOWN_TYPE)
    payload = await _payload(request)
    try:
        weights = parse_weights(instrument_type, payload)
    except WeightValidationError as error:
        raise HTTPException(
            status_code=422,
            detail=_MESSAGES.get(error.code, _NOT_OBJECT),
        ) from None
    try:
        ScoreWeightsRepository(db).save(instrument_type, weights)
    except ScoreWeightsSaveError:
        raise HTTPException(status_code=400, detail=_SAVE_FAILED) from None
    return _weight_body(
        instrument_type, weights, _saved_version(db, instrument_type), True
    )


def _saved_version(db, instrument_type):
    row = ScoreWeightsRepository(db).get(instrument_type)
    return row.version


async def _payload(request):
    """The JSON object, or a 422 that does not quote the body."""
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=422, detail=_NOT_OBJECT)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail=_NOT_OBJECT) from None
    return payload
