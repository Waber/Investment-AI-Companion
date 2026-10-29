"""Jinja2 environment for /ui.

Autoescape stays on. Starlette enables it for ``.html`` templates.
Pages pass catalog lookups and formatters into the context. They do
not mark data as safe.
"""

import re
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.ui.catalog import (
    DEFAULT_LANGUAGE,
    LANGUAGE_COOKIE,
    SUPPORTED_LANGUAGES,
    translate,
)
from app.ui.formatting import (
    format_change,
    format_date,
    format_day,
    format_local_date,
    format_local_datetime,
    format_number,
    format_price,
)

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


class MessageCatalog:
    """``{{ t['missing'] }}`` in a template.

    ``__getitem__`` calls ``translate``, so a missing English key
    falls back to Polish while the page is rendering.
    """

    def __init__(self, language):
        self.language = language

    def __getitem__(self, key):
        return translate(self.language, key)


def resolve_language(request):
    """Read the language cookie. Anything else is Polish."""
    value = request.cookies.get(LANGUAGE_COOKIE, "")
    if value in SUPPORTED_LANGUAGES:
        return value
    return DEFAULT_LANGUAGE


# POST /ui/companies/{id}/edit and .../delete already have a GET at
# the same path. The create actions do not: the empty forms live at
# /new.
_COMPANY_FORM = re.compile(
    r"^/ui/companies/(?P<company_id>[^/]+)/(?:edit|delete)$"
)
_METRICS_CREATE = re.compile(r"^/ui/companies/(?P<company_id>[^/]+)/metrics$")
_METRICS_FORM = re.compile(
    r"^/ui/companies/(?P<company_id>[^/]+)/metrics/"
    r"(?P<metrics_id>[^/]+)/(?:edit|delete)$"
)
# The "Nowa notatka" field lives in the research panel, so a note add
# returns to the panel. A note's inline edit form and delete question
# have a GET at the same path.
_NOTE_CREATE = re.compile(r"^/ui/companies/(?P<company_id>[^/]+)/notes$")
_NOTE_FORM = re.compile(
    r"^/ui/companies/(?P<company_id>[^/]+)/notes/"
    r"(?P<note_id>[^/]+)/(?:edit|delete)$"
)


def _path_with_query(path, query):
    """Join a path and a raw query string. The query has no ``?``."""
    if query:
        return f"{path}?{query}"
    return path


def _get_form_for_post(path):
    """Return the GET form for a POST path, or None.

    ``POST /ui/companies`` inserts a company. The blank form is
    ``GET /ui/companies/new``. ``POST /ui/companies/{id}/metrics``
    inserts a period. That form is ``GET .../metrics/new``.
    ``POST /ui/companies/{id}/notes`` adds a note from the research
    panel, ``GET .../research``. Edit and delete are the same path for
    GET and POST.
    """
    if path == "/ui/companies":
        return "/ui/companies/new"
    created = _METRICS_CREATE.match(path)
    if created is not None:
        company_id = created.group("company_id")
        return f"/ui/companies/{company_id}/metrics/new"
    note_added = _NOTE_CREATE.match(path)
    if note_added is not None:
        company_id = note_added.group("company_id")
        return f"/ui/companies/{company_id}/research"
    if any(
        pattern.match(path)
        for pattern in (_COMPANY_FORM, _METRICS_FORM, _NOTE_FORM)
    ):
        return path
    return None


def language_next_path(request):
    """Path the language buttons can open with a GET.

    A page loaded with GET returns to that URL, including the query.
    A page rendered from a POST (a 422 or a 400) was built at the
    form action. Some of those actions do not accept GET, so opening
    them is a 405. The switch names the GET form instead. A POST
    with no form to return to uses ``/ui``.
    """
    path = request.url.path
    query = request.url.query
    if request.method.upper() == "GET":
        return _path_with_query(path, query)
    form = _get_form_for_post(path)
    if form is None:
        return "/ui"
    return _path_with_query(form, query)


def render(request, template_name, *, status_code=200, **extra):
    """Render one template with the shared page context."""
    language = resolve_language(request)
    context = {
        "language": language,
        "t": MessageCatalog(language),
        "format_number": format_number,
        "format_date": format_date,
        "format_day": format_day,
        "format_local_datetime": format_local_datetime,
        "format_local_date": format_local_date,
        "format_price": format_price,
        "format_change": format_change,
        "next_path": language_next_path(request),
    }
    context.update(extra)
    return templates.TemplateResponse(
        request,
        template_name,
        context,
        status_code=status_code,
    )
