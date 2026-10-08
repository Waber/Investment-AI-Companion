"""Jinja2 environment for /ui.

Autoescape stays on. Starlette enables it for ``.html`` templates.
Pages pass catalog lookups and formatters into the context. They do
not mark data as safe.
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.ui.catalog import (
    DEFAULT_LANGUAGE,
    LANGUAGE_COOKIE,
    SUPPORTED_LANGUAGES,
    translate,
)
from app.ui.formatting import format_date, format_number

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


def current_path(request):
    """Path and query the language switch should return to."""
    path = request.url.path
    if request.url.query:
        return f"{path}?{request.url.query}"
    return path


def render(request, template_name, *, status_code=200, **extra):
    """Render one template with the shared page context."""
    language = resolve_language(request)
    context = {
        "language": language,
        "t": MessageCatalog(language),
        "format_number": format_number,
        "format_date": format_date,
        "next_path": current_path(request),
    }
    context.update(extra)
    return templates.TemplateResponse(
        request,
        template_name,
        context,
        status_code=status_code,
    )
