import math
import unicodedata
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# A 200k-character name would otherwise be copied into the 422 body.
# Short inputs stay intact so the overflow tests can still see "inf".
_MAX_ERROR_INPUT_CHARS = 100


def _truncate_error_input(value: Any) -> Any:
    """Shorten string inputs. Nested lists and dicts are walked too."""
    if isinstance(value, str):
        if len(value) <= _MAX_ERROR_INPUT_CHARS:
            return value
        return value[:_MAX_ERROR_INPUT_CHARS]
    if isinstance(value, list):
        return [_truncate_error_input(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _truncate_error_input(item) for key, item in value.items()
        }
    return value


def _escape_surrogates(value: Any) -> Any:
    """Replace lone surrogates so the 422 body can be encoded as UTF-8.

    A surrogate is a real Python character (category Cs) and not a
    valid UTF-8 byte. ``JSONResponse`` writes with ``ensure_ascii``
    off, then encodes the text. Leaving the character in ``input``
    turns a 422 into a 500. The six ASCII characters ``\\uXXXX``
    stand in for it. The validator message never contains the
    character in the first place.
    """
    if isinstance(value, str):
        if not any(unicodedata.category(char) == "Cs" for char in value):
            return value
        return "".join(
            (
                "\\u%04x" % ord(char)
                if unicodedata.category(char) == "Cs"
                else char
            )
            for char in value
        )
    if isinstance(value, list):
        return [_escape_surrogates(item) for item in value]
    if isinstance(value, dict):
        return {key: _escape_surrogates(item) for key, item in value.items()}
    return value


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
    for error in errors:
        if isinstance(error, dict) and "input" in error:
            error["input"] = _truncate_error_input(error["input"])
    # After truncation, so a huge surrogate string is shortened first.
    errors = _escape_surrogates(errors)
    return JSONResponse(status_code=422, content={"detail": errors})
