import math
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _sanitize_nonfinite(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, list):
        return [_sanitize_nonfinite(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_nonfinite(item) for key, item in value.items()}
    return value


async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Encode first so tuples and model objects are traversable JSON containers.
    errors = _sanitize_nonfinite(jsonable_encoder(exc.errors()))
    return JSONResponse(status_code=422, content={"detail": errors})
