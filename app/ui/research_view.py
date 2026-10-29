"""The research panel on the company page, as the templates render it.

The panel lists a company's theses, then its notes. One
``ResearchPanel`` describes everything the panel shows, and one
partial (``partials/research_panel.html``) renders it, for the full
page and for every HTMX answer alike.

The repositories list rows newest edit first, which suits the API.
The panel sorts for display:

- notes and active theses by creation time, newest first, so editing
  an old note does not move it to the top;
- closed theses by closing time, newest first.

Ties are broken by id, the newer row first.
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.research import Note, Thesis, ThesisStatus
from app.repositories.note_repository import NoteRepository
from app.repositories.thesis_repository import ThesisRepository


@dataclass(frozen=True)
class PanelForm:
    """The one inline form open in the panel, if any.

    ``kind`` is ``note_edit``, ``note_delete``, ``thesis_new``,
    ``thesis_edit``, or ``thesis_delete``. ``thesis_status`` is a
    close or reopen that failed to save: it opens no form, and its
    message shows in the thesis's card. ``item_id`` is the note or
    thesis it belongs to (None for a new thesis). ``values`` are the
    field texts to show. ``errors`` maps a field to the catalog key
    of its message. ``form_error`` is the catalog key of a message
    for the whole form.
    """

    kind: str
    item_id: int | None = None
    # A plain ``{}`` default would be one dict shared by every
    # instance, so dataclasses refuse it. ``default_factory`` makes a
    # new dict for each instance.
    values: dict[str, str] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    form_error: str | None = None


@dataclass(frozen=True)
class NewNote:
    """The "Nowa notatka" field, which keeps its draft across actions.

    ``preserve`` is False only in the answers to its own add: the
    success, the 422, and a failed save. Those show the field as the
    server rendered it, empty after a success and with the typed text
    otherwise. Every other answer lets HTMX keep the text typed in the
    browser.
    """

    body: str = ""
    errors: dict[str, str] = field(default_factory=dict)
    form_error: str | None = None
    preserve: bool = True


@dataclass(frozen=True)
class ResearchPanel:
    """Everything the open panel shows.

    ``focus`` is the id of the one element that gets ``autofocus``,
    or None. ``state_path`` is the GET URL that renders the page in
    this state; the language switch returns there.
    """

    company_id: int
    notes: list[Note]
    active_theses: list[Thesis]
    closed_theses: list[Thesis]
    form: PanelForm | None
    new_note: NewNote
    show_closed: bool
    focus: str | None
    state_path: str

    @property
    def count(self) -> int:
        """Notes plus theses, active and closed: the button's number."""
        return (
            len(self.notes) + len(self.active_theses) + len(self.closed_theses)
        )


# The GET route of each inline form. It renders the company page with
# that form open. Without JavaScript the "Edytuj", "Usuń", and
# "+ Nowa teza" links open it, and with HTMX the language switch
# returns there. ``thesis_status`` has no form of its own, so it
# returns to the open panel.
_FORM_PATHS = {
    "note_edit": "/ui/companies/{company_id}/notes/{item_id}/edit",
    "note_delete": "/ui/companies/{company_id}/notes/{item_id}/delete",
    "thesis_new": "/ui/companies/{company_id}/theses/new",
    "thesis_edit": "/ui/companies/{company_id}/theses/{item_id}/edit",
    "thesis_delete": "/ui/companies/{company_id}/theses/{item_id}/delete",
}


def panel_state_path(
    company_id: int, *, form: PanelForm | None = None, closed: bool = False
) -> str:
    """The GET URL that shows the company page in one panel state.

    The language switch returns there, so PL/EN keeps the panel as it
    is. ``closed`` is the page with the panel closed. An inline form
    or question opens at its own GET route. Every other state is the
    page with the panel open, which is also where a plain POST lands.
    """
    if closed:
        return f"/ui/instruments/{company_id}"
    path = _FORM_PATHS.get(form.kind) if form is not None else None
    if path is None:
        return f"/ui/instruments/{company_id}?research=open"
    return path.format(company_id=company_id, item_id=form.item_id)


def focus_after_delete(items, deleted_id: int, prefix: str) -> str:
    """The id that takes the focus once an item is deleted.

    ``items`` is the list the panel showed before the delete, top to
    bottom, and it holds ``deleted_id``. The focus moves to the next
    item, else to the previous one, else to the panel heading, so it
    never drops to the top of the page. ``prefix`` is ``note`` or
    ``thesis``, as in the item ids.
    """
    ids = [item.id for item in items]
    position = ids.index(deleted_id)
    if position + 1 < len(ids):
        return f"{prefix}-{ids[position + 1]}"
    if position > 0:
        return f"{prefix}-{ids[position - 1]}"
    return "research-title"


def research_count(db: Session, company_id: int) -> int:
    """The button's number when the panel is closed.

    It counts the repository lists. The repositories stay the only
    way the UI reads notes and theses, and one company has few rows.
    """
    notes = NoteRepository(db).list_for_company(company_id)
    theses = ThesisRepository(db).list_for_company(company_id)
    return len(notes) + len(theses)


def _newest_created_first(items):
    """Newest ``created_at`` first, so an edit does not move an item."""
    return sorted(
        items, key=lambda item: (item.created_at, item.id), reverse=True
    )


def _newest_closed_first(theses):
    """Newest ``closed_at`` first. A thesis without a date goes last.

    The repository always dates a closing, and revision 0008 dated
    the theses that were already closed. A row written past the
    repository can still be closed without a date. Those come after
    the dated ones, newest id first.
    """
    dated = [thesis for thesis in theses if thesis.closed_at is not None]
    undated = [thesis for thesis in theses if thesis.closed_at is None]
    dated.sort(key=lambda thesis: (thesis.closed_at, thesis.id), reverse=True)
    undated.sort(key=lambda thesis: thesis.id, reverse=True)
    return dated + undated


def build_panel(
    db: Session,
    company_id: int,
    *,
    form: PanelForm | None = None,
    new_note: NewNote | None = None,
    show_closed: bool = False,
    focus: str | None = None,
) -> ResearchPanel:
    """Load one company's notes and theses into an open panel.

    The company must exist; the routes check that first. The state
    path follows ``form``: the inline form's own GET, or the company
    page with the panel open (``panel_state_path``).
    """
    notes = NoteRepository(db).list_for_company(company_id)
    theses = ThesisRepository(db).list_for_company(company_id)
    active = [item for item in theses if item.status == ThesisStatus.ACTIVE]
    closed = [item for item in theses if item.status != ThesisStatus.ACTIVE]
    return ResearchPanel(
        company_id=company_id,
        notes=_newest_created_first(notes),
        active_theses=_newest_created_first(active),
        closed_theses=_newest_closed_first(closed),
        form=form,
        new_note=new_note if new_note is not None else NewNote(),
        show_closed=show_closed,
        focus=focus,
        state_path=panel_state_path(company_id, form=form),
    )
