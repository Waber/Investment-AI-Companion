"""HTML routes under /ui.

The JSON API stays under /api/v1. These routes are left out of the
OpenAPI document so /docs remains the API reference.
"""

from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.ui.catalog import LANGUAGE_COOKIE, SUPPORTED_LANGUAGES
from app.ui.queries import ListFilters, get_instrument, list_instruments
from app.ui.templating import render
from app.ui.view_models import METRIC_FIELDS, MONETARY_FIELDS

router = APIRouter(prefix="/ui", tags=["ui"])

_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


def is_htmx(request):
    """True when HTMX asked for a fragment instead of the whole page."""
    return request.headers.get("hx-request", "").casefold() == "true"


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
    if not allowed:
        return "/ui"
    parts = urlsplit(candidate)
    if parts.scheme or parts.netloc:
        return "/ui"
    return candidate


@router.get("", include_in_schema=False)
@router.get("/", include_in_schema=False)
def instrument_list(
    request: Request,
    q: str = "",
    exchange: str = "",
    currency: str = "",
    db: Session = Depends(get_db),
):
    """List instruments. HTMX swaps only the results region."""
    filters = ListFilters(
        search=q.strip(),
        exchange=exchange.strip(),
        currency=currency.strip(),
    )
    instruments, exchanges, currencies = list_instruments(db, filters)
    template_name = (
        "partials/instrument_results.html"
        if is_htmx(request)
        else "instrument_list.html"
    )
    return render(
        request,
        template_name,
        instruments=instruments,
        exchanges=exchanges,
        currencies=currencies,
        filters=filters,
    )


@router.get("/instruments/{instrument_id}", include_in_schema=False)
def instrument_detail(
    request: Request,
    instrument_id: int,
    db: Session = Depends(get_db),
):
    """One instrument, or a translated 404."""
    instrument = get_instrument(db, instrument_id)
    if instrument is None:
        return render(request, "not_found.html", status_code=404)
    return render(
        request,
        "instrument_detail.html",
        instrument=instrument,
        metric_fields=METRIC_FIELDS,
        monetary_fields=MONETARY_FIELDS,
    )


@router.get("/language/{language_code}", include_in_schema=False)
def switch_language(request: Request, language_code: str, next: str = ""):
    """Store the language in a cookie and redirect back to /ui."""
    if language_code not in SUPPORTED_LANGUAGES:
        return render(request, "not_found.html", status_code=404)
    response = RedirectResponse(safe_next(next), status_code=303)
    response.set_cookie(
        key=LANGUAGE_COOKIE,
        value=language_code,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response
