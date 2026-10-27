"""HTML routes under /ui.

The JSON API stays under /api/v1. These routes are left out of the
OpenAPI document so /docs remains the API reference.
"""

import posixpath
from urllib.parse import unquote, urlsplit

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.repositories.watchlist_repository import WatchlistRepository
from app.ui import watchlist_view
from app.ui.catalog import LANGUAGE_COOKIE, SUPPORTED_LANGUAGES
from app.ui.origin import require_same_origin
from app.ui.queries import ListFilters, get_instrument, list_instruments
from app.ui.templating import render
from app.ui.view_models import METRIC_FIELDS, MONETARY_FIELDS

router = APIRouter(
    prefix="/ui",
    tags=["ui"],
    # POST, PUT, PATCH, and DELETE must come from this host. GET is
    # not checked here. The language cookie is set by
    # POST /ui/language/{code}, so that request is covered here.
    # GET of the same path only redirects. The forms router uses
    # the same dependency.
    dependencies=[Depends(require_same_origin)],
)

_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
# SQLite stores an INTEGER in a signed 64-bit value. A larger Python
# int reaches the driver and the query fails with 500.
_MAX_INSTRUMENT_ID = 2**63 - 1
# The pages load CSS and HTMX from this origin only. frame-ancestors
# and X-Frame-Options both refuse to be embedded. same-origin still
# keeps the local address off a company website. no-referrer would
# make Chrome send Origin: null on a form POST, and the same-origin
# check would then reject every save.
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
    response.headers["Referrer-Policy"] = "same-origin"
    # A fragment and a full page share the URL. Caches must not mix them.
    response.headers["Vary"] = "HX-Request"
    response.headers["Cache-Control"] = "no-store"
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


# ``%252e`` is an encoded ``%2e``. One unquote is not enough to see
# the dot. A handful of layers covers a doubled or tripled encoding.
# Anything still changing after that is not a path we will follow.
_MAX_UNQUOTES = 8


def _fully_unquoted_path(candidate):
    """Return the path with percent-encoding removed, repeatedly.

    ``urlsplit`` does not decode ``%2e``. One ``unquote`` turns
    ``%252e`` into ``%2e``, and the next turns that into ``.``.
    ``None`` means the encoding did not settle.
    """
    path = urlsplit(candidate).path
    for _ in range(_MAX_UNQUOTES):
        decoded = unquote(path)
        if decoded == path:
            return path
        path = decoded
    return None


def _path_escapes_ui(candidate):
    """True when the path is not a page under /ui.

    ``/ui/../api/v1/companies/`` starts with ``/ui/`` and is still
    outside /ui once the ``..`` segment is applied. ``/ui/./language/pl``
    is the language route once the ``.`` segment is applied.
    ``%2e`` and ``%252e`` are that same dot. Same-origin is not enough.
    """
    parts = urlsplit(candidate)
    if parts.scheme or parts.netloc:
        return True
    path = _fully_unquoted_path(candidate)
    if path is None or "\\" in path:
        return True
    # ``.`` is the current directory and ``..`` is the parent. Either
    # one can hide the language route or leave /ui.
    return any(segment in {".", ".."} for segment in path.split("/"))


def _is_language_switch(candidate):
    """True when the return path is the language cookie route.

    The comparison uses the fully decoded path after
    ``posixpath.normpath``, so ``/ui/./language/pl`` and
    ``/ui/%2e/language/pl`` are the same route as ``/ui/language/pl``.
    The POST that sets the cookie must not send the browser back
    there.
    """
    path = _fully_unquoted_path(candidate)
    if path is None:
        return True
    normalized = posixpath.normpath(path)
    return normalized == "/ui/language" or normalized.startswith(
        "/ui/language/"
    )


def safe_next(value):
    """Allow a return path under /ui, and nothing else.

    The language switch puts the current path in a hidden form
    field. A value that points at another site, or at a scheme, is
    ignored. A path under ``/ui/language/`` is also ignored, including
    one hidden by a ``.`` or ``..`` segment. The POST must not send
    the browser back to the language route. The fallback is ``/ui``.
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
    if _is_language_switch(candidate):
        return "/ui"
    return candidate


def _instrument_id(value):
    """Return a decimal id, or None when the path is not one.

    A non-integer path such as ``abc`` must be the HTML 404. Leaving
    the parameter as ``int`` would make FastAPI return the API's 422
    JSON instead.

    ``str.isdigit`` is also true for Unicode digits. Superscript
    ``²`` then makes ``int`` raise, and Arabic-Indic ``١`` becomes
    ``1``. ``int`` also raises ``ValueError`` once an ASCII digit
    string is longer than about 4300 characters, which became a
    plain-text 500. A signed 64-bit value has at most 19 digits,
    so anything longer is rejected before ``int``.

    ``01`` and ``007`` are the same rows as ``1`` and ``7``. A
    leading zero is not a second URL for that row. The single
    character ``0`` is a normal id. The JSON API is unchanged.
    """
    if not value.isascii() or not value.isdigit() or len(value) > 19:
        return None
    if len(value) > 1 and value.startswith("0"):
        return None
    parsed = int(value)
    if parsed > _MAX_INSTRUMENT_ID:
        return None
    return parsed


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
            oob_language_next=is_htmx(request),
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
            on_watchlist=WatchlistRepository(db).contains(instrument.id),
        )
    )


@router.get("/watchlist", include_in_schema=False)
def watchlist(request: Request, db: Session = Depends(get_db)):
    """The single watchlist as a table, oldest addition first.

    Freshness counts from today's UTC date, so a series that stopped
    more than ``WATCHLIST_STALE_PRICE_DAYS`` days ago is marked stale.
    """
    return _with_ui_headers(
        render(
            request,
            "watchlist.html",
            entries=watchlist_view.list_entries(db),
            stale_days=settings.WATCHLIST_STALE_PRICE_DAYS,
            focus_index=None,
        )
    )


@router.get("/language/{language_code}", include_in_schema=False)
def language_bookmark(request: Request, language_code: str, next: str = ""):
    """Redirect an old language URL without changing the cookie.

    The switch itself is the POST below. A bookmark or a typed URL
    is still this GET. It used to set the cookie, or answer 403 when
    the request had no ``Origin`` and no ``Referer``. It now does
    neither: a known code redirects to ``safe_next`` and leaves the
    cookie as it was, so an old bookmark stays useful. An unknown
    code is the HTML 404 and does not set a cookie.
    """
    if language_code not in SUPPORTED_LANGUAGES:
        return _with_ui_headers(
            render(request, "not_found.html", status_code=404)
        )
    return _with_ui_headers(RedirectResponse(safe_next(next), status_code=303))


@router.post("/language/{language_code}", include_in_schema=False)
def switch_language(
    request: Request, language_code: str, next: str = Form("")
):
    """Store the language in a cookie and redirect back to /ui.

    ``require_same_origin`` on this router already refused a
    cross-site POST, so this function does not call it again. An
    unknown code is the HTML 404 and does not set a cookie. That
    runs after the origin check, so a cross-site POST of an unknown
    code is 403.
    """
    if language_code not in SUPPORTED_LANGUAGES:
        return _with_ui_headers(
            render(request, "not_found.html", status_code=404)
        )
    response = RedirectResponse(safe_next(next), status_code=303)
    # Secure waits for HTTPS (#56). On this HTTP demo a Secure cookie
    # would not be stored, so the language switch would not stick.
    response.set_cookie(
        key=LANGUAGE_COOKIE,
        value=language_code,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return _with_ui_headers(response)
