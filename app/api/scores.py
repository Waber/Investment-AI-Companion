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
_TOO_LARGE = "Score weights are too large"
# A few kilobytes. A weight object is a handful of numbers. 16 KiB
# leaves room for a very long number and still rejects a huge body
# before it is parsed.
_MAX_WEIGHT_BODY = 16 * 1024
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


def _declared_length(request):
    """The Content-Length, or None when the header is absent.

    A value that is not a non-negative integer is the same 413 as a
    body that is too large. The header text is not copied.
    """
    raw = request.headers.get("content-length")
    if raw is None:
        return None
    # ``isdigit`` is true for ``²``. ``int`` then raises, and the
    # client sees a 500. A size is ASCII digits only.
    if not raw.isascii() or not raw.isdigit():
        raise HTTPException(status_code=413, detail=_TOO_LARGE)
    return int(raw)


async def _read_capped(request):
    """Read at most 16 KiB plus one byte, then stop."""
    received = bytearray()
    limit = _MAX_WEIGHT_BODY
    async for chunk in request.stream():
        if not chunk:
            continue
        room = limit + 1 - len(received)
        if room <= 0:
            raise HTTPException(status_code=413, detail=_TOO_LARGE)
        received.extend(chunk[:room])
        if len(received) > limit:
            raise HTTPException(status_code=413, detail=_TOO_LARGE)
    return bytes(received)


async def _json_payload(request: Request):
    """The JSON object, or a fixed error that does not quote the body.

    A Content-Length over 16 KiB, or one that is not a size, is 413
    before any body byte is read. A chunked body with no length is
    read only until it passes that cap. Invalid text, a number that
    is too big to parse, and a value nested deep enough to overflow
    the parser are 422. ``ValueError`` covers a bad encoding and that
    oversized integer. ``RecursionError`` is not a ``ValueError``.
    """
    declared = _declared_length(request)
    if declared is not None and declared > _MAX_WEIGHT_BODY:
        raise HTTPException(status_code=413, detail=_TOO_LARGE)
    raw = await _read_capped(request)
    if not raw:
        raise HTTPException(status_code=422, detail=_NOT_OBJECT)
    try:
        return json.loads(raw)
    except (ValueError, RecursionError):
        raise HTTPException(status_code=422, detail=_NOT_OBJECT) from None


@router.put(
    "/score-weights/{instrument_type}",
    response_model=ScoreWeightSet,
)
def put_score_weights(
    instrument_type: str,
    payload=Depends(_json_payload),
    db: Session = Depends(get_db),
):
    """Replace the weight set and increase its version.

    The first saved set is version 2. The numbers are stored as sent.
    Scoring divides the ones it can use by their sum. The answer is
    the row that was saved.
    """
    if instrument_type not in _TYPES:
        raise HTTPException(status_code=422, detail=_UNKNOWN_TYPE)
    try:
        weights = parse_weights(instrument_type, payload)
    except WeightValidationError as error:
        raise HTTPException(
            status_code=422,
            detail=_MESSAGES.get(error.code, _NOT_OBJECT),
        ) from None
    try:
        saved = ScoreWeightsRepository(db).save(instrument_type, weights)
    except ScoreWeightsSaveError:
        raise HTTPException(status_code=400, detail=_SAVE_FAILED) from None
    stored = _decode_saved(instrument_type, saved.weights)
    return _weight_body(instrument_type, stored, saved.version, True)


def _decode_saved(instrument_type, raw):
    """The weights just written, read back from that row."""
    try:
        return parse_weights(instrument_type, {"weights": json.loads(raw)})
    except (WeightValidationError, TypeError, ValueError, RecursionError):
        raise HTTPException(status_code=500, detail=_UNREADABLE) from None
