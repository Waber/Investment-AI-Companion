# Notes and theses on the company page (#33): design

Date: 2026-10-28. Issue: #33 (N1). The tables, models, and
repositories merged in #91 (text rules from #98). Follow-ups that are
out of scope: #103 (comments on buy and sell transactions), #36
(notes as optional AI context), #58 (price alerts and signals).

## Intent

Raul wants his research about a company next to the company. Short
notes, added from a sticky-note icon like the one in the DEGIRO app,
and investment theses: why he bought and when he would sell. His
example: he bought an AI-infrastructure company after an analysis
with an AI model, and he plans to sell when the price is up 20%,
probably with a stop-loss order at his broker. The app records that
plan as text. It does not watch prices or place orders.

## Goals

- A sticky-note button next to the watchlist heart on
  `/ui/instruments/{id}`, showing how many notes and theses the
  company has.
- The button opens a panel directly under the company name without a
  full page reload. A second click closes it. The panel is closed
  when the page loads.
- In the panel, theses first, then notes:
  - active theses on top;
  - closed theses folded under "Zamknięte tezy (n)";
  - a "Nowa notatka" field with "Dodaj notatkę";
  - notes newest first, each with its date and time, "Edytuj", and
    "Usuń".
- Theses: add, edit, close with one click, reopen, and delete. Several
  theses per company are allowed. A closed thesis shows its closing
  date.
- An HTTP API under `/api/v1/instruments/{instrument_id}/notes` and
  `/theses` with the same operations.
- PL and EN strings. Works offline. Notes and theses survive a server
  restart, a company data refresh (fetch-company), and a price
  refresh.

## Non-goals

- Comments on transactions and the transaction history (#103, after
  #57).
- Sending notes or theses to an AI model (A1/A2, #36).
- Watching a price target or alerting at +20% (#58).
- Markdown, attachments, tags, search, edit history, undo.
- Showing notes or theses on the watchlist page.

## Anti-goals

- A company page full of text. Raul picked icons (the heart, now the
  sticky note) so the page stays clean.
- A click that silently does nothing: a failed request must show
  something, and typed text must not vanish on a validation error.
- User text rendered as HTML.
- A note time that is two hours off because it is shown in UTC.

## Decided with Raul (2026-10-28)

1. A sticky-note icon next to the heart, like DEGIRO, with a count.
2. It opens a panel under the company name without a page reload;
   clicking again closes it.
3. Notes: one text field, newest note first, date and time on each,
   "Edytuj" and "Usuń" on each.
4. Plain text. Line breaks are kept. HTML is shown as text.
5. Theses sit in the same panel, above the notes. Active theses are
   on top; closed ones are folded below.
6. Thesis fields are labelled "Tytuł", "Dlaczego kupiłem", and
   "Kiedy sprzedam / co złamie tezę". Status is active or closed.
7. Closing is one click. A closed thesis shows its closing date and
   can be reopened.
8. A price target such as +20% is plain text. Reminders belong to
   #58. Trade comments are #103.

## Decided by Claude (Raul can overrule)

Each call is described in full in the sections below.

1. The sticky note is a GET form button: no JavaScript is needed to
   open the panel. The count is notes plus theses.
2. Every panel action re-renders the whole panel. Every state also
   has a GET URL that renders the full page in that state.
3. A validation error is a 422 for HTMX and for a plain POST. HTMX is
   configured to swap 422.
4. Panel forms and panel links fall back to a plain request when HTMX
   fails. `static/ui.js` learns to follow a link. A duplicate note
   after a lost response is an accepted risk.
5. Deleting asks first, inline in the panel. It is a hard delete.
6. Notes are sorted by creation time, so an edit does not move them.
   An edited note says so. The API keeps the repository order.
7. Times are shown in Polish time (`Europe/Warsaw`) with a 24-hour
   clock, in both languages. Theses show dates only.
8. The closing date is a new column, `theses.closed_at` (revision
   0008). The app refuses to start on an older database without it
   and names the Alembic command to run.
9. A failed insert of a note or thesis becomes `ResearchStorageError`
   in the repository, the same as update and delete already do.
10. A new thesis always starts active. Its status changes only
    through "Zamknij tezę" and "Otwórz ponownie".
11. Drafts:
    - the "Nowa notatka" text survives other panel actions;
    - only one inline form (edit, delete question, new thesis) is
      open at a time;
    - unsaved text in that inline form is dropped when another
      action starts.
12. A missing note or thesis of an existing company gets its own 404
    text, with a link back to the panel.
13. There are no screen-reader status messages yet. Focus rules
    replace them.

## What exists (master `3c40413`)

- `app/models/research.py`:
  - limits `NOTE_BODY_MAX` 10000, `THESIS_TITLE_MAX` 200,
    `THESIS_BODY_MAX` 10000, `THESIS_BREAKERS_MAX` 5000;
  - `ThesisStatus` (`active`, `closed`);
  - write models `NoteCreate`, `NoteUpdate`, `ThesisCreate`,
    `ThesisUpdate` (`extra="forbid"`, strip then length, CRLF folded,
    title one line, blank title or body rejected);
  - read models `Note` and `Thesis`.
- `NoteRepository` and `ThesisRepository`: `list_for_company`, `get`,
  `create`, `update`, `delete`, and `ThesisRepository.set_status`.
  Every call is scoped to one `company_id`, so another company's id
  looks missing. Lists are ordered `updated_at` desc, then `id` desc.
- `create` raises `CompanyNotFoundError` for an unknown company.
- A failed commit in `update`, `delete`, or `set_status` raises
  `ResearchStorageError` after a rollback.
- In `create`, a failed commit behaves differently:
  - another `IntegrityError` is re-raised after a rollback
    (`commit_company_scoped` in `app/repositories/research_store.py`);
  - any other `SQLAlchemyError`, for example SQLite "database is
    locked", escapes without a rollback.
- Tables `notes` and `theses` (revision 0005), `ON DELETE CASCADE`
  from `companies`. There is no `closed_at` column.
- There is no HTTP route and no UI. `python-multipart` is already
  pinned.

## Parts of the how already decided

### The panel

- The button is a GET form beside the heart, the same shape as the
  heart form. Without JavaScript it opens
  `/ui/instruments/{id}?research=open#research`, which renders the
  page with the panel open. With HTMX it fetches only the panel.
- The button carries `aria-expanded`, `aria-controls="research"`, and
  an accessible name with the count ("Notatki i tezy (3)"). The icon
  is an inline SVG styled by classes in `static/ui.css`, because the
  CSP allows no `style` attribute.
- The count is notes plus theses, active and closed. With nothing
  stored the button shows the icon without a number.
- Every action inside the panel (add, edit, delete, close, reopen,
  open a form, cancel) replaces the whole panel. Each response also
  brings the button with its new count. One target means one
  rendering of the panel, used by both the full page and HTMX.
- Without JavaScript every action still works:
  - each "Edytuj", "Usuń", and "+ Nowa teza" link opens a GET URL
    that renders the full company page with the panel in that state
    (an inline edit form, an inline delete question);
  - each POST ends in a 303 to
    `/ui/instruments/{id}?research=open#research`.
- Validation errors return 422 for HTMX and for a plain POST. The
  form keeps the typed text and shows the error summary and the field
  error. HTMX 2 does not swap 4xx answers by default, so the
  `htmx-config` meta in `base.html` gains a `responseHandling` rule
  that swaps 422. No other `/ui` HTMX request returns 422 today; the
  builder confirms that while making the change.
- Panel forms and panel links carry `data-plain-fallback`. A 404, a
  500, or a network error then repeats the request without HTMX, and
  the browser shows the server's answer:
  - a form is posted again;
  - a link is followed. `static/ui.js` handles only forms today and
    learns links.
  This includes "Dodaj notatkę". A duplicate note is possible only if
  the server stored the note and the answer was lost on the loopback
  connection. Raul can delete it; that cost is accepted.
- Deleting asks first, inline: "Usunąć tę notatkę?" with "Usuń" and
  "Anuluj". Delete is a hard delete.
- Drafts:
  - With HTMX, text typed in "Nowa notatka" survives the other panel
    actions (`hx-preserve`). Its own successful add clears it, and
    its own 422 shows it with the error.
  - Only one inline form is open at a time: a note edit, a delete
    question, or a new or edited thesis. Opening another one, or
    "Anuluj", drops unsaved text in it.
  - Without JavaScript, every action is a page load, so text in other
    forms is lost, as on the other `/ui` forms.
- After any panel action, keyboard focus stays in the panel. After
  adding a note, focus is back in the empty note field. Focus never
  falls back to the top of the page. There are no screen-reader
  status messages in this slice. A lasting status region outside the
  panel can come later.

### What the panel shows

- **Notes:** created date and time, newest created first (`created_at`
  desc, then `id` desc). Editing a note does not move it. An edited
  note also shows "edytowano" with the edit time.
- **Active theses:** newest created first. Each card shows:
  - the title, an "aktywna" badge, and "od {date}";
  - "Dlaczego kupiłem" with the body;
  - "Kiedy sprzedam / co złamie tezę" with the breakers, or "brak
    danych" when empty;
  - "Edytuj", "Zamknij tezę", and "Usuń".
- **Closed theses:** folded in a native `<details>` "Zamknięte tezy
  (n)", newest closing first. Each card shows "zamknięta {date}" and
  "Otwórz ponownie" instead of "Zamknij tezę".
- **Times:** stored as UTC and shown in Polish time (`Europe/Warsaw`,
  24-hour clock) in both languages, because the app is Raul's. PL
  `28.10.2026, 14:05`; EN `Oct 28, 2026, 14:05`. Theses show dates
  only, also in Polish time. Existing UTC dates elsewhere on the page
  do not change.
- **Text:** shown with `white-space: pre-wrap` from a CSS class, so
  line breaks show and HTML stays escaped. Long words wrap. There is
  no truncation.
- **Empty states:** "Brak tez." and "Brak notatek."
- A new thesis always starts active. The edit form has title, body,
  and breakers; the status changes only through "Zamknij tezę" and
  "Otwórz ponownie".

### Closing date (data change)

- Revision 0008 adds a nullable `theses.closed_at` (aware UTC, the
  same column type as `updated_at`). Existing closed rows get
  `closed_at = updated_at`. Downgrade drops the column.
- The repository sets `closed_at` when the status changes to
  `closed`, using the same clock as `updated_at`, and clears it when
  the status changes to `active`. That covers `set_status`, an
  `update` that changes the status, and a `create` with `closed`.
  Saving the status a thesis already has leaves `closed_at` alone.
- The read model `Thesis` gains `closed_at: datetime | None`. The
  API returns it.
- `create_all` does not add a column to an existing table. A database
  built by an older startup, or a demo file kept with `--keep`, would
  otherwise fail on the first thesis query. Startup therefore refuses
  to serve when `theses` exists without `closed_at`, the same way
  `require_company_instrument_columns` already guards `companies`
  (`app/core/init_db.py`). The message names the commands:
  - an Alembic-managed database runs `alembic upgrade head`;
  - an older `create_all` database runs `alembic stamp 0007`, then
    `alembic upgrade head`.
- The existing "stamp head" advice, in the 0005 docstring and the
  companies message, says it applies only to a fresh `create_all`
  database. On an older one it would skip 0008.

### Storage failures

- `create` maps a failed commit the way `update` and `delete`
  already do:
  - it rolls back;
  - a company that vanished is still `CompanyNotFoundError`;
  - any other `SQLAlchemyError` becomes `ResearchStorageError`, with
    no driver text and nothing chained.
- The API and the UI then catch only the two typed errors. The test
  that expects a re-raised `IntegrityError` (`tests/research_cases.py`)
  changes with the contract.

### The API

Mounted under `/api/v1`, one module per resource, in the style of
`app/api/watchlist.py` and `app/api/prices.py`.

| Method | Path | Success | Errors |
|---|---|---|---|
| GET | `/instruments/{instrument_id}/notes` | 200, list | 404 `Instrument not found` |
| POST | `/instruments/{instrument_id}/notes` | 201, note | 404, 422 |
| GET | `/instruments/{instrument_id}/notes/{note_id}` | 200 | 404 `Note not found` |
| PUT | `/instruments/{instrument_id}/notes/{note_id}` | 200 | 404, 422 |
| DELETE | `/instruments/{instrument_id}/notes/{note_id}` | 204 | 404 |
| GET, POST | `/instruments/{instrument_id}/theses` | 200, 201 | 404, 422 |
| GET, PUT, DELETE | `/instruments/{instrument_id}/theses/{thesis_id}` | 200, 200, 204 | 404 `Thesis not found`, 422 |

- The unknown instrument is checked first, so it is a 404, not an
  empty list.
- `PUT` is a partial update, the house style (there is no `PATCH`).
  An empty body returns the stored item unchanged. A thesis `PUT` may
  carry `status`, which is how the API closes and reopens.
- `GET /theses?status=active|closed` filters by status. Any other
  value is a 422.
- API lists keep the repository order (newest edit first). The UI
  sorts for display.
- Every id is an integer from 1 to 2^63−1. Anything else is a 422,
  never a 500.
- A storage failure is a 500 `Note or thesis could not be stored`,
  with nothing else from the exception.
- There is no origin check, the same as every other API route. The
  app listens on loopback only until login (#48).

### UI routes

All of these are in a router with `require_same_origin`, as every
`/ui` POST is:

- `GET /ui/companies/{company_id}/research`: the panel, open or closed.
- `POST /ui/companies/{company_id}/notes`
- `GET` and `POST /ui/companies/{company_id}/notes/{note_id}/edit`
- `GET` and `POST /ui/companies/{company_id}/notes/{note_id}/delete`
- `GET /ui/companies/{company_id}/theses/new` and
  `POST /ui/companies/{company_id}/theses`
- `GET` and `POST /ui/companies/{company_id}/theses/{thesis_id}/edit`
- `POST /ui/companies/{company_id}/theses/{thesis_id}/close` and
  `.../reopen`
- `GET` and `POST /ui/companies/{company_id}/theses/{thesis_id}/delete`

Behaviour of these routes:

- An unknown company is the existing instrument 404.
- A note or thesis that is unknown, or that belongs to another
  company, is a 404 with its own text when the company exists:
  "Nie znaleziono notatki ani tezy." / "Note or thesis not found."
  It links back to `/ui/instruments/{id}?research=open#research`.
  This is the page the 404 fallback shows after a delete in another
  tab.
- A POST that renders a full page (a 422 without HTMX) must also give
  the language switch a GET page to return to. That is the
  `_get_form_for_post` lookup in `app/ui/templating.py`.
- A storage failure re-renders the panel with the typed text and a
  form-level message "Nie udało się zapisać. Spróbuj ponownie." with
  status 500.

### Other copy

- The company delete warning says the company's notes and theses are
  deleted too, because the cascade does that.
- PL and EN for every new string. The words "kupiłem" and "sprzedam"
  appear only in field labels. Keys under the prefixes that
  `tests/test_ui_forms.py` scans for buy and sell words stay free of
  them.

## Left to the builder

- Module split, the template and partial structure, and helper and
  catalog key names.
- Element ids for several forms on one page. They must be unique, and
  error-summary links must point at the right field.
- CSS for the panel, the cards, and the icon.
- `maxlength` attributes, if any. The server's limits decide.
- Test file layout and fixtures.
- How the docs are updated: `docs/api-demo.md` with examples, the
  README API list, and `docs/RUN_DEMO.md`. The demo starts with no
  notes, like the watchlist; demo flow step 6 adds them live.

## Done when

- [ ] The #33 acceptance criteria hold:
  - CRUD for notes and theses, close and reopen;
  - a `<script>` payload is escaped in every field: page, fragment,
    and 422 re-render;
  - the data persists across a restart and across data and price
    refreshes;
  - PL and EN work;
  - the full SQLite suite and CI are green;
  - scoped black, isort, and flake8 pass.
- [ ] The API table above is covered by tests, including the id
  bounds, the length limits, and the status filter.
- [ ] Revision 0008 upgrades and downgrades on SQLite, and CI covers
  PostgreSQL.
- [ ] Driven in Chrome on the demo with the mouse and the keyboard:
  - open and close the panel;
  - add, edit, and delete a note;
  - add, close, reopen, and delete a thesis;
  - a validation error;
  - the 404 fallback.
- [ ] The Chrome console has no uncaught exception and no CSP
  violation. A deliberate 422 or 404 step may log only two lines:
  the browser's line for that one request, and HTMX's single
  "Response Status Error Code" line for the 404.
- [ ] Journal, work-state, and HANDOFF updated; Code Reviewer
  approved.
