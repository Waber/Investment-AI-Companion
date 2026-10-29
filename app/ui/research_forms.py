"""The notes and theses panel on the company page (issue #33).

The sticky-note button beside the watchlist heart opens a panel under
the company name. This module holds the panel's routes. Each one
answers in two ways (``_panel_response``):

- HTMX gets only the panel, plus out of band the sticky-note form and
  the language switch's return path;
- a plain request gets the whole company page in the same state. So
  every panel state also has a GET URL that works without JavaScript.

An unknown company is the instrument 404, as on the company page.
"""

import re

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.ui.forms import _load_company
from app.ui.origin import require_same_origin
from app.ui.research_view import build_panel, research_count
from app.ui.router import _with_ui_headers, detail_page, is_htmx
from app.ui.templating import render
from app.ui.view_models import to_instrument

router = APIRouter(
    prefix="/ui",
    tags=["ui"],
    dependencies=[Depends(require_same_origin)],
)

# ``focus`` names the note or thesis that gets the focus, such as
# ``note-3``. ``fullmatch`` instead of ``$``: in Python ``$`` also
# matches before a trailing newline. ``[0-9]`` is ASCII only; ``\d``
# would accept other digits too.
_FOCUS = re.compile(r"(note|thesis)-[0-9]+")


def _panel_response(request, db, company, panel, *, status_code=200):
    """Answer with the panel in this state, for HTMX or a plain request.

    ``company`` is the company row. ``panel`` is a ``ResearchPanel``,
    or None for the closed panel.

    HTMX gets the panel partial. Out of band come the whole
    sticky-note form, with its count, ``aria-expanded``, and the next
    state, so a second click closes the panel; and the two language
    inputs, set to the GET URL of this state, so PL/EN keeps it.

    A plain request gets the company page in the same state.
    """
    if not is_htmx(request):
        return detail_page(
            request,
            db,
            to_instrument(company),
            research_panel=panel,
            status_code=status_code,
        )
    if panel is None:
        count = research_count(db, company.id)
        state_path = f"/ui/instruments/{company.id}"
    else:
        count = panel.count
        state_path = panel.state_path
    return _with_ui_headers(
        render(
            request,
            "partials/research_panel.html",
            status_code=status_code,
            company_id=company.id,
            research_panel=panel,
            research_count=count,
            research_open=panel is not None,
            research_oob=True,
            research_state_path=state_path,
        )
    )


@router.get("/companies/{company_id}/research", include_in_schema=False)
def show_research_panel(
    request: Request,
    company_id: str,
    research: str = "open",
    focus: str = "",
    db: Session = Depends(get_db),
):
    """The panel, open or closed.

    The sticky note sends ``research``, the state it asks for.
    ``closed`` closes the panel. Any other value, or none, opens it.
    ``focus`` is ignored unless it names a note or thesis.
    """
    company, missing = _load_company(request, db, company_id)
    if missing is not None:
        return missing
    if research == "closed":
        return _panel_response(request, db, company, None)
    panel = build_panel(
        db, company.id, focus=focus if _FOCUS.fullmatch(focus) else None
    )
    return _panel_response(request, db, company, panel)
