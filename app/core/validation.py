import math
import unicodedata
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.validation.text import TextValidationError

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
        # Keys are part of the body when a required field is missing.
        # A long key would otherwise be copied into the 422 body too.
        return {
            _truncate_error_input(key): _truncate_error_input(item)
            for key, item in value.items()
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

    Dict keys are escaped too. A missing required field puts the
    whole body in ``input``, and a surrogate key such as U+DC00
    is not valid UTF-8 either. Nested dicts and lists are walked.
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
        return {
            _escape_surrogates(key): _escape_surrogates(item)
            for key, item in value.items()
        }
    return value


def _limit_error_context(errors: list[Any]) -> list[Any]:
    """Publish only ``code`` and ``field`` on a text error.

    ``jsonable_encoder`` would copy every attribute on the
    exception (``vars(exc)``). A new attribute would then show up
    in ``ctx.error`` and become part of the 422 contract. A text
    error is exactly ``{code, field}``. Any other exception is
    ``{}``, which is what a plain ``ValueError`` already encoded
    to.
    """
    for error in errors:
        if not isinstance(error, dict):
            continue
        ctx = error.get("ctx")
        if not isinstance(ctx, dict) or "error" not in ctx:
            continue
        cause = ctx["error"]
        if isinstance(cause, TextValidationError):
            ctx["error"] = {"code": cause.code, "field": cause.field}
        else:
            ctx["error"] = {}
    return errors


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
    # Limit ctx.error before encoding. Encoding would otherwise copy
    # every attribute on the exception into the 422 body.
    errors = _limit_error_context(exc.errors())
    # Encode first so tuples and model objects are traversable JSON containers.
    errors = _sanitize_nonfinite(jsonable_encoder(errors))
    for error in errors:
        if isinstance(error, dict) and "input" in error:
            error["input"] = _truncate_error_input(error["input"])
    # After truncation, so a huge surrogate string is shortened first.
    errors = _escape_surrogates(errors)
    return JSONResponse(status_code=422, content={"detail": errors})
