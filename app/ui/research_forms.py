"""The notes and theses panel on the company page (issue #33).

The sticky-note button beside the watchlist heart opens a panel under
the company name. This module holds the panel's routes. Each one
answers in two ways (``_panel_response``):

- HTMX gets only the panel, plus out of band the sticky-note form and
  the language switch's return path;
- a plain request gets the whole company page in the same state. So
  every panel state also has a GET URL that works without JavaScript.

The note forms post here too. A change that worked answers HTMX with
the panel, and a plain POST with a 303 to the open panel, so a reload
does not post again (``_changed``). Invalid text is a 422, and a
failed save is a 500. Both show the panel again with the typed text
and the focus on the form's error summary.

An unknown company is the instrument 404, as on the company page. A
note that is unknown, or that belongs to another company, is the
research 404, which links back to the panel.
"""

import re

from fastapi import APIRouter, Depends, Form, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.research import NoteCreate, NoteUpdate
from app.repositories.company_errors import CompanyNotFoundError
from app.repositories.note_repository import NoteRepository
from app.repositories.research_store import ResearchStorageError
from app.ui.forms import _load_company, _not_found, _see_other
from app.ui.origin import require_same_origin
from app.ui.research_view import (
    NewNote,
    PanelForm,
    build_panel,
    focus_after_delete,
    panel_state_path,
    research_count,
)
from app.ui.router import (
    _instrument_id,
    _with_ui_headers,
    detail_page,
    is_htmx,
)
from app.ui.templating import render
from app.ui.view_models import to_instrument
from app.validation.text import TextValidationError

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

# A "too long" error names the limit, because the fields have no
# maxlength: a browser would cut a long paste without a word.
_TOO_LONG_KEYS = {
    200: "error.max_200",
    5000: "error.max_5000",
    10000: "error.max_10000",
}


def research_error_key(error: dict) -> str:
    """The catalog key for one Pydantic error on a note or thesis field.

    ``error`` is one item of ``ValidationError.errors()``. Blank text
    fails in the write model's validator, which raises
    ``TextValidationError`` with the code ``blank``. Pydantic reports
    that as ``value_error`` and keeps the exception in ``ctx``.
    """
    kind = error.get("type")
    context = error.get("ctx") or {}
    if kind == "missing":
        return "error.required"
    if kind == "string_too_long":
        return _TOO_LONG_KEYS.get(context.get("max_length"), "error.too_long")
    cause = context.get("error")
    if (
        kind == "value_error"
        and isinstance(cause, TextValidationError)
        and cause.code == "blank"
    ):
        return "error.required"
    return "error.invalid"


def _errors_from(exc: ValidationError):
    """``(field_errors, form_error)`` from a write model's ValidationError.

    ``field_errors`` maps a field to the catalog key of its first
    error. Pydantic reports the errors in the model's field order,
    which is the form's order. An error that names no field becomes
    the form error.
    """
    errors = {}
    form_error = None
    for error in exc.errors():
        loc = error.get("loc") or ()
        field = loc[-1] if loc else None
        key = research_error_key(error)
        if isinstance(field, str):
            errors.setdefault(field, key)
        else:
            # The first error that names no field wins, like a field's.
            form_error = form_error or key
    return errors, form_error


def validate_note(
    values: dict, *, update: bool
) -> tuple[NoteCreate | NoteUpdate | None, dict[str, str], str | None]:
    """Return ``(model, field_errors, form_error)`` for a posted note.

    ``model`` is a ``NoteCreate`` for an add, a ``NoteUpdate`` for an
    edit, or None when the text is not valid. The write models own
    every rule: blank text, the length after the CRLF fold, and
    control characters. The errors are catalog keys, so the panel
    shows them in either language.
    """
    model_type = NoteUpdate if update else NoteCreate
    try:
        model = model_type.model_validate({"body": values.get("body", "")})
    except ValidationError as exc:
        errors, form_error = _errors_from(exc)
        return None, errors, form_error
    return model, {}, None


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
        state_path = panel_state_path(company.id, closed=True)
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


def _changed(request, db, company, panel):
    """Answer a change that worked: an add, a save, or a delete.

    HTMX gets the panel in its new state. A plain POST gets a 303 to
    the page with the panel open, so a reload does not post again.
    """
    if is_htmx(request):
        return _panel_response(request, db, company, panel)
    return _see_other(panel_state_path(company.id) + "#research")


def _research_not_found(request, company):
    """404 for a note or thesis that this company does not have.

    The company exists, so the page links back to its panel. A note
    deleted in another tab ends here. HTMX does not swap a 404, so
    ``ui.js`` repeats the request without HTMX, and the browser shows
    this page.
    """
    return _with_ui_headers(
        render(
            request,
            "research_not_found.html",
            status_code=404,
            back_href=panel_state_path(company.id) + "#research",
        )
    )


def _load_note(request, db, company_raw, note_raw):
    """Return ``(company, note, response)``. ``response`` is None if found.

    An unknown company is the instrument 404. A note id that is not a
    number, or that names no note of this company, is the research
    404. The repository only looks inside this company, so another
    company's note looks missing.
    """
    company, missing = _load_company(request, db, company_raw)
    if missing is not None:
        return None, None, missing
    note_id = _instrument_id(note_raw)
    note = None
    if note_id is not None:
        note = NoteRepository(db).get(company.id, note_id)
    if note is None:
        return company, None, _research_not_found(request, company)
    return company, note, None


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


@router.post("/companies/{company_id}/notes", include_in_schema=False)
def add_note(
    request: Request,
    company_id: str,
    body: str = Form(""),
    db: Session = Depends(get_db),
):
    """Add a note from the "Nowa notatka" field.

    After a success the field is empty and has the focus, ready for
    the next note. A 422 or a failed save keeps the typed text.
    """
    company, missing = _load_company(request, db, company_id)
    if missing is not None:
        return missing
    note, errors, form_error = validate_note({"body": body}, update=False)
    if note is None:
        draft = NewNote(
            body=body, errors=errors, form_error=form_error, preserve=False
        )
        panel = build_panel(
            db, company.id, new_note=draft, focus="note-new-errors"
        )
        return _panel_response(request, db, company, panel, status_code=422)
    try:
        NoteRepository(db).create(company.id, note)
    except CompanyNotFoundError:
        # The company was deleted after the check above.
        return _not_found(request)
    except ResearchStorageError:
        draft = NewNote(body=body, form_error="error.storage", preserve=False)
        panel = build_panel(
            db, company.id, new_note=draft, focus="note-new-errors"
        )
        return _panel_response(request, db, company, panel, status_code=500)
    panel = build_panel(
        db, company.id, new_note=NewNote(preserve=False), focus="note-new-body"
    )
    return _changed(request, db, company, panel)


@router.get(
    "/companies/{company_id}/notes/{note_id}/edit", include_in_schema=False
)
def edit_note_form(
    request: Request,
    company_id: str,
    note_id: str,
    db: Session = Depends(get_db),
):
    """The note's text in an inline form, in place of the note."""
    company, note, missing = _load_note(request, db, company_id, note_id)
    if missing is not None:
        return missing
    form = PanelForm(
        kind="note_edit", item_id=note.id, values={"body": note.body}
    )
    panel = build_panel(
        db, company.id, form=form, focus=f"note-{note.id}-body"
    )
    return _panel_response(request, db, company, panel)


@router.post(
    "/companies/{company_id}/notes/{note_id}/edit", include_in_schema=False
)
def save_note(
    request: Request,
    company_id: str,
    note_id: str,
    body: str = Form(""),
    db: Session = Depends(get_db),
):
    """Save the inline form. Saving the same text stores nothing.

    ``update`` would move ``updated_at`` even for the same text, and
    the note would then say "edytowano". So the validated text, which
    is stripped and has CRLF folded, is compared with the stored text
    first.
    """
    company, note, missing = _load_note(request, db, company_id, note_id)
    if missing is not None:
        return missing
    changes, errors, form_error = validate_note({"body": body}, update=True)
    if changes is None:
        form = PanelForm(
            kind="note_edit",
            item_id=note.id,
            values={"body": body},
            errors=errors,
            form_error=form_error,
        )
        panel = build_panel(
            db, company.id, form=form, focus=f"note-{note.id}-errors"
        )
        return _panel_response(request, db, company, panel, status_code=422)
    if changes.body != note.body:
        try:
            saved = NoteRepository(db).update(company.id, note.id, changes)
        except ResearchStorageError:
            form = PanelForm(
                kind="note_edit",
                item_id=note.id,
                values={"body": body},
                form_error="error.storage",
            )
            panel = build_panel(
                db, company.id, form=form, focus=f"note-{note.id}-errors"
            )
            return _panel_response(
                request, db, company, panel, status_code=500
            )
        if saved is None:
            # Deleted in another tab after the check above.
            return _research_not_found(request, company)
    panel = build_panel(db, company.id, focus=f"note-{note.id}")
    return _changed(request, db, company, panel)


@router.get(
    "/companies/{company_id}/notes/{note_id}/delete", include_in_schema=False
)
def delete_note_question(
    request: Request,
    company_id: str,
    note_id: str,
    db: Session = Depends(get_db),
):
    """Ask inline before deleting. This GET deletes nothing.

    The focus goes to the question, never to the "Usuń" button, so a
    stray Enter cannot delete the note.
    """
    company, note, missing = _load_note(request, db, company_id, note_id)
    if missing is not None:
        return missing
    form = PanelForm(kind="note_delete", item_id=note.id)
    panel = build_panel(
        db, company.id, form=form, focus=f"note-{note.id}-delete-question"
    )
    return _panel_response(request, db, company, panel)


@router.post(
    "/companies/{company_id}/notes/{note_id}/delete", include_in_schema=False
)
def delete_note(
    request: Request,
    company_id: str,
    note_id: str,
    db: Session = Depends(get_db),
):
    """Delete the note for good. The focus moves to a neighbour.

    A failed delete keeps the question open, with the error.
    """
    company, note, missing = _load_note(request, db, company_id, note_id)
    if missing is not None:
        return missing
    # The notes in the order the panel showed them, to find the
    # neighbour that takes the focus.
    shown = build_panel(db, company.id).notes
    try:
        deleted = NoteRepository(db).delete(company.id, note.id)
    except ResearchStorageError:
        form = PanelForm(
            kind="note_delete", item_id=note.id, form_error="error.storage"
        )
        panel = build_panel(
            db, company.id, form=form, focus=f"note-{note.id}-errors"
        )
        return _panel_response(request, db, company, panel, status_code=500)
    if not deleted:
        # Deleted in another tab after the check above.
        return _research_not_found(request, company)
    focus = focus_after_delete(shown, note.id, "note")
    panel = build_panel(db, company.id, focus=focus)
    return _changed(request, db, company, panel)
