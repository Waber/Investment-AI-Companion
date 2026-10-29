"""The notes and theses panel on the company page (issue #33).

The sticky-note button beside the watchlist heart opens a panel under
the company name. This module holds the panel's routes. Each one
answers in two ways (``_panel_response``):

- HTMX gets only the panel, plus out of band the sticky-note form and
  the language switch's return path;
- a plain request gets the whole company page in the same state. So
  every panel state also has a GET URL that works without JavaScript.

The note and thesis forms post here too. A change that worked answers
HTMX with the panel, and a plain POST with a 303 to the open panel, so
a reload does not post again (``_changed``). Invalid text is a 422,
and a failed save is a 500. Both show the panel again with the typed
text and the focus on the form's error summary
(``_panel_with_errors``).

An unknown company is the instrument 404, as on the company page. A
note or thesis that is unknown, or that belongs to another company,
is the research 404, which links back to the panel.
"""

import re

from fastapi import APIRouter, Depends, Form, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.research import (
    NoteCreate,
    NoteUpdate,
    ThesisCreate,
    ThesisStatus,
    ThesisUpdate,
)
from app.repositories.company_errors import CompanyNotFoundError
from app.repositories.note_repository import NoteRepository
from app.repositories.research_store import ResearchStorageError
from app.repositories.thesis_repository import ThesisRepository
from app.ui.form_fields import errors_from_validation
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

# The thesis form's fields, in the order it shows them. Its error
# summary lists them in the same order.
_THESIS_FIELDS = ("title", "body", "thesis_breakers")


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


def validate_note(
    values: dict, *, update: bool
) -> tuple[NoteCreate | NoteUpdate | None, dict[str, str], str | None]:
    """Return ``(model, field_errors, form_error)`` for a posted note.

    ``model`` is a ``NoteCreate`` for an add, a ``NoteUpdate`` for an
    edit, or None when the text is not valid. The write models own
    every rule: blank text, the length after the CRLF fold, and
    control characters. The errors are catalog keys, so the panel
    shows them in either language. ``errors_from_validation`` is the
    rule the company and metrics forms use; ``research_error_key``
    only picks the keys.
    """
    model_type = NoteUpdate if update else NoteCreate
    try:
        model = model_type.model_validate({"body": values.get("body", "")})
    except ValidationError as exc:
        errors, form_error = errors_from_validation(
            exc, ("body",), key_for=research_error_key
        )
        return None, errors, form_error
    return model, {}, None


def validate_thesis(
    values: dict, *, update: bool
) -> tuple[ThesisCreate | ThesisUpdate | None, dict[str, str], str | None]:
    """Return ``(model, field_errors, form_error)`` for a posted thesis.

    The same shape as ``validate_note``: a ``ThesisCreate`` for a new
    thesis, a ``ThesisUpdate`` for an edit, or None when a field is
    not valid. Only the three text fields are read, so the status is
    never set here. A new thesis therefore starts active, and an edit
    keeps the stored status and closing date. "Zamknij tezę" and
    "Otwórz ponownie" are the only ways to change them.
    """
    model_type = ThesisUpdate if update else ThesisCreate
    fields = {name: values.get(name, "") for name in _THESIS_FIELDS}
    try:
        model = model_type.model_validate(fields)
    except ValidationError as exc:
        errors, form_error = errors_from_validation(
            exc, _THESIS_FIELDS, key_for=research_error_key
        )
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


def _panel_with_errors(
    request,
    db,
    company,
    prefix,
    *,
    status_code,
    form=None,
    new_note=None,
    show_closed=False,
):
    """Show one form again with its errors: a 422 or a 500.

    ``status_code`` is 422 for invalid text and 500 for a failed save.
    ``form`` is the inline form, or ``new_note`` the "Nowa notatka"
    field, with the typed text and the error keys. ``prefix`` starts
    that form's ids, such as ``note-new`` or ``thesis-4``. Its error
    summary, ``{prefix}-errors``, takes the focus: this is the only
    place the summary gets ``autofocus``. ``show_closed`` unfolds the
    closed list for a form inside a closed thesis.
    """
    panel = build_panel(
        db,
        company.id,
        form=form,
        new_note=new_note,
        show_closed=show_closed,
        focus=f"{prefix}-errors",
    )
    return _panel_response(
        request, db, company, panel, status_code=status_code
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
    or thesis deleted in another tab ends here. HTMX does not swap a
    404, so ``ui.js`` repeats the request without HTMX, and the
    browser shows this page.
    """
    return _with_ui_headers(
        render(
            request,
            "research_not_found.html",
            status_code=404,
            back_href=panel_state_path(company.id) + "#research",
        )
    )


def _load_item(request, db, company_raw, item_raw, repository_type):
    """Return ``(company, item, response)``. ``response`` is None if found.

    ``repository_type`` is ``NoteRepository`` or ``ThesisRepository``.
    An unknown company is the instrument 404. An id that is not a
    number, or that names no note or thesis of this company, is the
    research 404. The repository only looks inside this company, so
    another company's note or thesis looks missing.
    """
    company, missing = _load_company(request, db, company_raw)
    if missing is not None:
        return None, None, missing
    item_id = _instrument_id(item_raw)
    item = None
    if item_id is not None:
        item = repository_type(db).get(company.id, item_id)
    if item is None:
        return company, None, _research_not_found(request, company)
    return company, item, None


def _load_note(request, db, company_raw, note_raw):
    """Return ``(company, note, response)``, as ``_load_item`` does."""
    return _load_item(request, db, company_raw, note_raw, NoteRepository)


def _load_thesis(request, db, company_raw, thesis_raw):
    """Return ``(company, thesis, response)``, as ``_load_item`` does."""
    return _load_item(request, db, company_raw, thesis_raw, ThesisRepository)


def _in_closed_list(thesis):
    """True when the panel lists this thesis under "Zamknięte tezy".

    ``build_panel`` splits the theses the same way. After an action
    on such a thesis the closed list is shown unfolded, so the card
    that holds the inline form or takes the focus is visible.
    """
    return thesis.status != ThesisStatus.ACTIVE


def _names_closed_thesis(db, company_id, focus):
    """True when ``focus`` is ``thesis-{id}`` of a closed thesis here.

    "Anuluj" on a closed thesis comes back with that focus. The
    closed list must then be unfolded, or the card that takes the
    focus would stay hidden. ``focus`` already matched ``_FOCUS``, or
    is None. Its id still goes through ``_instrument_id``, which
    refuses an id too long for the database.
    """
    if focus is None or not focus.startswith("thesis-"):
        return False
    thesis_id = _instrument_id(focus.removeprefix("thesis-"))
    if thesis_id is None:
        return False
    thesis = ThesisRepository(db).get(company_id, thesis_id)
    return thesis is not None and _in_closed_list(thesis)


def _thesis_texts(thesis):
    """The three text fields of a ``Thesis`` or ``ThesisUpdate``, by name."""
    return {name: getattr(thesis, name) for name in _THESIS_FIELDS}


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
    ``focus`` is ignored unless it names a note or thesis. When it
    names a closed thesis, the closed list is unfolded.
    """
    company, missing = _load_company(request, db, company_id)
    if missing is not None:
        return missing
    if research == "closed":
        return _panel_response(request, db, company, None)
    kept = focus if _FOCUS.fullmatch(focus) else None
    panel = build_panel(
        db,
        company.id,
        show_closed=_names_closed_thesis(db, company.id, kept),
        focus=kept,
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
        return _panel_with_errors(
            request, db, company, "note-new", new_note=draft, status_code=422
        )
    try:
        NoteRepository(db).create(company.id, note)
    except CompanyNotFoundError:
        # The company was deleted after the check above.
        return _not_found(request)
    except ResearchStorageError:
        draft = NewNote(body=body, form_error="error.storage", preserve=False)
        return _panel_with_errors(
            request, db, company, "note-new", new_note=draft, status_code=500
        )
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
    prefix = f"note-{note.id}"
    changes, errors, form_error = validate_note({"body": body}, update=True)
    if changes is None:
        form = PanelForm(
            kind="note_edit",
            item_id=note.id,
            values={"body": body},
            errors=errors,
            form_error=form_error,
        )
        return _panel_with_errors(
            request, db, company, prefix, form=form, status_code=422
        )
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
            return _panel_with_errors(
                request, db, company, prefix, form=form, status_code=500
            )
        if saved is None:
            # Deleted in another tab after the check above.
            return _research_not_found(request, company)
    panel = build_panel(db, company.id, focus=prefix)
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
        return _panel_with_errors(
            request, db, company, f"note-{note.id}", form=form, status_code=500
        )
    if not deleted:
        # Deleted in another tab after the check above.
        return _research_not_found(request, company)
    focus = focus_after_delete(shown, note.id, "note")
    panel = build_panel(db, company.id, focus=focus)
    return _changed(request, db, company, panel)


@router.get("/companies/{company_id}/theses/new", include_in_schema=False)
def new_thesis_form(
    request: Request,
    company_id: str,
    db: Session = Depends(get_db),
):
    """The empty thesis form, in place of the "+ Nowa teza" link."""
    company, missing = _load_company(request, db, company_id)
    if missing is not None:
        return missing
    form = PanelForm(
        kind="thesis_new", values=dict.fromkeys(_THESIS_FIELDS, "")
    )
    panel = build_panel(db, company.id, form=form, focus="thesis-new-title")
    return _panel_response(request, db, company, panel)


@router.post("/companies/{company_id}/theses", include_in_schema=False)
def add_thesis(
    request: Request,
    company_id: str,
    title: str = Form(""),
    body: str = Form(""),
    thesis_breakers: str = Form(""),
    db: Session = Depends(get_db),
):
    """Add a thesis from the "+ Nowa teza" form. It always starts active.

    After a success the form closes and the focus goes to the new
    card. A 422 or a failed save keeps the form open with the typed
    text.
    """
    company, missing = _load_company(request, db, company_id)
    if missing is not None:
        return missing
    values = {"title": title, "body": body, "thesis_breakers": thesis_breakers}
    thesis, errors, form_error = validate_thesis(values, update=False)
    if thesis is None:
        form = PanelForm(
            kind="thesis_new",
            values=values,
            errors=errors,
            form_error=form_error,
        )
        return _panel_with_errors(
            request, db, company, "thesis-new", form=form, status_code=422
        )
    try:
        created = ThesisRepository(db).create(company.id, thesis)
    except CompanyNotFoundError:
        # The company was deleted after the check above.
        return _not_found(request)
    except ResearchStorageError:
        form = PanelForm(
            kind="thesis_new", values=values, form_error="error.storage"
        )
        return _panel_with_errors(
            request, db, company, "thesis-new", form=form, status_code=500
        )
    panel = build_panel(db, company.id, focus=f"thesis-{created.id}")
    return _changed(request, db, company, panel)


@router.get(
    "/companies/{company_id}/theses/{thesis_id}/edit", include_in_schema=False
)
def edit_thesis_form(
    request: Request,
    company_id: str,
    thesis_id: str,
    db: Session = Depends(get_db),
):
    """The thesis's fields in an inline form, in place of its card text."""
    company, thesis, missing = _load_thesis(request, db, company_id, thesis_id)
    if missing is not None:
        return missing
    form = PanelForm(
        kind="thesis_edit", item_id=thesis.id, values=_thesis_texts(thesis)
    )
    panel = build_panel(
        db,
        company.id,
        form=form,
        show_closed=_in_closed_list(thesis),
        focus=f"thesis-{thesis.id}-title",
    )
    return _panel_response(request, db, company, panel)


@router.post(
    "/companies/{company_id}/theses/{thesis_id}/edit", include_in_schema=False
)
def save_thesis(
    request: Request,
    company_id: str,
    thesis_id: str,
    title: str = Form(""),
    body: str = Form(""),
    thesis_breakers: str = Form(""),
    db: Session = Depends(get_db),
):
    """Save the inline form. Saving the same text stores nothing.

    As for a note, ``update`` would move ``updated_at`` even for the
    same text, so the three validated fields are compared with the
    stored ones first. The status and the closing date stay as they
    are: ``validate_thesis`` never sets them.
    """
    company, thesis, missing = _load_thesis(request, db, company_id, thesis_id)
    if missing is not None:
        return missing
    prefix = f"thesis-{thesis.id}"
    show_closed = _in_closed_list(thesis)
    values = {"title": title, "body": body, "thesis_breakers": thesis_breakers}
    changes, errors, form_error = validate_thesis(values, update=True)
    if changes is None:
        form = PanelForm(
            kind="thesis_edit",
            item_id=thesis.id,
            values=values,
            errors=errors,
            form_error=form_error,
        )
        return _panel_with_errors(
            request,
            db,
            company,
            prefix,
            form=form,
            show_closed=show_closed,
            status_code=422,
        )
    if _thesis_texts(changes) != _thesis_texts(thesis):
        try:
            saved = ThesisRepository(db).update(company.id, thesis.id, changes)
        except ResearchStorageError:
            form = PanelForm(
                kind="thesis_edit",
                item_id=thesis.id,
                values=values,
                form_error="error.storage",
            )
            return _panel_with_errors(
                request,
                db,
                company,
                prefix,
                form=form,
                show_closed=show_closed,
                status_code=500,
            )
        if saved is None:
            # Deleted in another tab after the check above.
            return _research_not_found(request, company)
    panel = build_panel(db, company.id, show_closed=show_closed, focus=prefix)
    return _changed(request, db, company, panel)


def _set_thesis_status(request, db, company_id, thesis_id, status):
    """Close or reopen a thesis: "Zamknij tezę" or "Otwórz ponownie".

    ``set_status`` is repeat-safe. A thesis that already has this
    status, after a second click or one in another tab, stays as it
    is, and the answer is the same. The answer sets no ``autofocus``:
    both buttons have the id ``thesis-{id}-status``, so HTMX puts the
    focus back on the button, now with the other word. A failed save
    shows its message in the thesis's card.
    """
    company, thesis, missing = _load_thesis(request, db, company_id, thesis_id)
    if missing is not None:
        return missing
    try:
        changed = ThesisRepository(db).set_status(
            company.id, thesis.id, status
        )
    except ResearchStorageError:
        form = PanelForm(
            kind="thesis_status", item_id=thesis.id, form_error="error.storage"
        )
        return _panel_with_errors(
            request,
            db,
            company,
            f"thesis-{thesis.id}",
            form=form,
            show_closed=_in_closed_list(thesis),
            status_code=500,
        )
    if changed is None:
        # Deleted in another tab after the check above.
        return _research_not_found(request, company)
    # The thesis was closed before or after the click, so the action
    # concerned the closed list: it stays unfolded.
    show_closed = _in_closed_list(thesis) or _in_closed_list(changed)
    panel = build_panel(db, company.id, show_closed=show_closed)
    return _changed(request, db, company, panel)


@router.post(
    "/companies/{company_id}/theses/{thesis_id}/close",
    include_in_schema=False,
)
def close_thesis(
    request: Request,
    company_id: str,
    thesis_id: str,
    db: Session = Depends(get_db),
):
    """Close the thesis with one click. See ``_set_thesis_status``."""
    return _set_thesis_status(
        request, db, company_id, thesis_id, ThesisStatus.CLOSED
    )


@router.post(
    "/companies/{company_id}/theses/{thesis_id}/reopen",
    include_in_schema=False,
)
def reopen_thesis(
    request: Request,
    company_id: str,
    thesis_id: str,
    db: Session = Depends(get_db),
):
    """Make a closed thesis active again. See ``_set_thesis_status``."""
    return _set_thesis_status(
        request, db, company_id, thesis_id, ThesisStatus.ACTIVE
    )


@router.get(
    "/companies/{company_id}/theses/{thesis_id}/delete",
    include_in_schema=False,
)
def delete_thesis_question(
    request: Request,
    company_id: str,
    thesis_id: str,
    db: Session = Depends(get_db),
):
    """Ask inline before deleting. This GET deletes nothing.

    The focus goes to the question, never to the "Usuń" button, so a
    stray Enter cannot delete the thesis.
    """
    company, thesis, missing = _load_thesis(request, db, company_id, thesis_id)
    if missing is not None:
        return missing
    form = PanelForm(kind="thesis_delete", item_id=thesis.id)
    panel = build_panel(
        db,
        company.id,
        form=form,
        show_closed=_in_closed_list(thesis),
        focus=f"thesis-{thesis.id}-delete-question",
    )
    return _panel_response(request, db, company, panel)


@router.post(
    "/companies/{company_id}/theses/{thesis_id}/delete",
    include_in_schema=False,
)
def delete_thesis(
    request: Request,
    company_id: str,
    thesis_id: str,
    db: Session = Depends(get_db),
):
    """Delete the thesis for good. The focus moves to a neighbour.

    The neighbour comes from the thesis's own list, active or closed.
    A failed delete keeps the question open, with the error.
    """
    company, thesis, missing = _load_thesis(request, db, company_id, thesis_id)
    if missing is not None:
        return missing
    # The list the panel showed the thesis in, top to bottom, to find
    # the neighbour that takes the focus. It is looked up in the panel
    # itself, so a thesis closed in another tab meanwhile is still
    # found in its list.
    shown = build_panel(db, company.id)
    in_closed = thesis.id in {item.id for item in shown.closed_theses}
    siblings = shown.closed_theses if in_closed else shown.active_theses
    try:
        deleted = ThesisRepository(db).delete(company.id, thesis.id)
    except ResearchStorageError:
        form = PanelForm(
            kind="thesis_delete", item_id=thesis.id, form_error="error.storage"
        )
        return _panel_with_errors(
            request,
            db,
            company,
            f"thesis-{thesis.id}",
            form=form,
            show_closed=in_closed,
            status_code=500,
        )
    if not deleted:
        # Deleted in another tab after the check above.
        return _research_not_found(request, company)
    focus = focus_after_delete(siblings, thesis.id, "thesis")
    panel = build_panel(db, company.id, show_closed=in_closed, focus=focus)
    return _changed(request, db, company, panel)
