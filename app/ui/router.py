"""HTML routes under /ui.

The JSON API stays under /api/v1. These routes are left out of the
OpenAPI document so /docs remains the API reference.
"""

from urllib.parse import unquote, urlsplit

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.ui.catalog import LANGUAGE_COOKIE, SUPPORTED_LANGUAGES
from app.ui.queries import ListFilters, get_instrument, list_instruments
from app.ui.templating import render
from app.ui.view_models import METRIC_FIELDS, MONETARY_FIELDS

router = APIRouter(prefix="/ui", tags=["ui"])

_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
# The pages load CSS and HTMX from this origin only. frame-ancestors
# and X-Frame-Options both refuse to be embedded. Referrer-Policy
# keeps the local address off links to a company website.
_CSP = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)


def _with_ui_headers(response):
    """Security headers shared by every /ui response, including 404."""
    response.headers["Content-Security-Policy"] = _CSP
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    # A fragment and a full page share the URL. Caches must not mix them.
    response.headers["Vary"] = "HX-Request"
    return response


def is_htmx(request):
    """True when HTMX asked for a fragment instead of the whole page.

    A history restore sets ``HX-Request`` and
    ``HX-History-Restore-Request``. HTMX then writes the response
    into ``body``. The fragment has no header, language switch, or
    disclaimer, so a restore must get the full page.
    """
    restore = request.headers.get("hx-history-restore-request", "")
    if restore.casefold() == "true":
        return False
    return request.headers.get("hx-request", "").casefold() == "true"


def _path_escapes_ui(candidate):
    """True when the path is not a page under /ui.

    ``/ui/../api/v1/companies/`` starts with ``/ui/`` and is still
    outside /ui once the ``..`` segment is applied. Same-origin is
    not enough.
    """
    parts = urlsplit(candidate)
    if parts.scheme or parts.netloc:
        return True
    path = unquote(parts.path)
    if "\\" in path:
        return True
    return any(segment == ".." for segment in path.split("/"))


def safe_next(value):
    """Allow a return path under /ui, and nothing else.

    The language switch puts the current path in the query string.
    A value that points at another site, or at a scheme, is ignored.
    """
    if not value:
        return "/ui"
    candidate = value.strip()
    lowered = candidate.casefold()
    if "%0d" in lowered or "%0a" in lowered:
        return "/ui"
    if "\r" in candidate or "\n" in candidate:
        return "/ui"
    if "\\" in candidate or candidate.startswith("//"):
        return "/ui"
    allowed = (
        candidate == "/ui"
        or candidate.startswith("/ui/")
        or candidate.startswith("/ui?")
    )
    if not allowed or _path_escapes_ui(candidate):
        return "/ui"
    return candidate


def _instrument_id(value):
    """Return a decimal id, or None when the path is not one.

    A non-integer path such as ``abc`` must be the HTML 404. Leaving
    the parameter as ``int`` would make FastAPI return the API's 422
    JSON instead.
    """
    if not value.isdigit():
        return None
    return int(value)


@router.get("", include_in_schema=False)
@router.get("/", include_in_schema=False)
def instrument_list(
    request: Request,
    q: str = "",
    instrument_type: str = Query("", alias="type"),
    exchange: str = "",
    currency: str = "",
    db: Session = Depends(get_db),
):
    """List instruments. HTMX swaps only the results region.

    ``type`` is the query name. An unknown value matches no rows and
    still returns the page. It does not raise.
    """
    filters = ListFilters(
        search=q.strip(),
        instrument_type=instrument_type.strip(),
        exchange=exchange.strip(),
        currency=currency.strip(),
    )
    instruments, instrument_types, exchanges, currencies = list_instruments(
        db, filters
    )
    template_name = (
        "partials/instrument_results.html"
        if is_htmx(request)
        else "instrument_list.html"
    )
    return _with_ui_headers(
        render(
            request,
            template_name,
            instruments=instruments,
            instrument_types=instrument_types,
            exchanges=exchanges,
            currencies=currencies,
            filters=filters,
        )
    )


@router.get("/instruments/{instrument_id}", include_in_schema=False)
def instrument_detail(
    request: Request,
    instrument_id: str,
    db: Session = Depends(get_db),
):
    """One instrument, or a translated HTML 404."""
    parsed_id = _instrument_id(instrument_id)
    instrument = None if parsed_id is None else get_instrument(db, parsed_id)
    if instrument is None:
        return _with_ui_headers(
            render(request, "not_found.html", status_code=404)
        )
    return _with_ui_headers(
        render(
            request,
            "instrument_detail.html",
            instrument=instrument,
            metric_fields=METRIC_FIELDS,
            monetary_fields=MONETARY_FIELDS,
        )
    )


@router.get("/language/{language_code}", include_in_schema=False)
def switch_language(request: Request, language_code: str, next: str = ""):
    """Store the language in a cookie and redirect back to /ui."""
    if language_code not in SUPPORTED_LANGUAGES:
        return _with_ui_headers(
            render(request, "not_found.html", status_code=404)
        )
    response = RedirectResponse(safe_next(next), status_code=303)
    response.set_cookie(
        key=LANGUAGE_COOKIE,
        value=language_code,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return _with_ui_headers(response)
