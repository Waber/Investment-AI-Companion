# Notes and Theses on the Company Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Notes and investment theses for one company. They live in a
panel opened from a sticky-note button next to the watchlist heart, and
behind a JSON API under `/api/v1/instruments/{instrument_id}/notes` and
`/theses`.

**Architecture:**
- The #91 repositories stay the only data layer. A small change adds
  `theses.closed_at` (revision 0008) and maps failed inserts to
  `ResearchStorageError`.
- A view-model module builds one `ResearchPanel`, and one partial
  renders it.
- Every panel route answers HTMX with that partial, plus the button
  form and the language return path out of band.
- A plain request gets the full company page in the same state.
  Successful plain POSTs end in a 303.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, Jinja2,
HTMX 2.0.10 (bundled), pytest with httpx `AsyncClient`, node (only for
the optional `ui.js` test).

**Spec:** `docs/superpowers/specs/2026-10-28-notes-theses-design.md`

## Global Constraints

- No new dependencies. `zoneinfo` from the standard library gives
  `Europe/Warsaw`.
- CSP unchanged: `default-src 'self'; base-uri 'self'; form-action 'self';
  frame-ancestors 'none'`.
  - No `style=` attribute, no inline script, no `hx-on`.
  - No `|safe` or `Markup`.
  - User text is rendered only through autoescape.
- Every `/ui` response goes through `_with_ui_headers`. Every new `/ui`
  router has `dependencies=[Depends(require_same_origin)]`.
- `/ui` route parameters are `str`, parsed with `_instrument_id`. Form
  fields are `Form("")`. A malformed request is then the HTML 404 or
  422, never FastAPI's JSON 422, which HTMX would now swap.
- Catalogs: every key goes in both `_POLISH` and `_ENGLISH`.
  - Keys under `_NEW_KEY_PREFIXES` (`tests/test_ui_forms.py`) must not
    contain `kupuj`, `sprzedaj`, or the words buy, sell, or hold.
  - "Dlaczego kupiłem" and "Kiedy sprzedam / co złamie tezę" go under
    `field.`.
- Templates contain no ASCII letters outside Jinja and tags
  (`tests/test_ui_templates.py`).
- Write validation goes only through `NoteCreate`, `NoteUpdate`,
  `ThesisCreate`, and `ThesisUpdate`.
  - There is no sanitizer: HTML is escaped on output.
  - There is no `maxlength`.
- User text in a `white-space: pre-wrap` element sits flush against
  its tags: `<p class="research-text">{{ note.body }}</p>`.
- Times are stored in UTC. Notes and theses show them in
  `Europe/Warsaw` with a 24-hour clock, in both languages.
- Alembic keeps one chain: `0008` revises `0007`.
- Tests never call a live market-data provider.
- No new "not investment advice" copy.
- Never log a note or thesis body.
- Black, isort, and flake8 at 79 columns on every changed Python file.

## Review Focus

1. **The second click on the sticky note must close the panel.** The
   out-of-band element is the whole `<form id="research-toggle">`, so
   its hidden `research` value flips. Test: Task 7,
   `test_panel_fragment_and_closing`.
2. **Text shows exactly as typed.**
   - pre-wrap adds no blank first line and no indentation;
   - a CRLF in the middle of a note at the limit counts as one
     character.

   Tests: Task 7, `test_research_text_keeps_breaks_and_wraps`; Task 8,
   `test_crlf_note_at_the_limit_is_saved`.
3. **Keyboard focus never drops to the top of the page.** That holds
   after an add, a 422, a close, and a delete, and a delete question
   never focuses the destructive button. Tests: Task 8,
   `test_note_focus_rules`; Task 9, `test_thesis_focus_rules`.
4. **Dates are Polish dates.** A thesis created or closed at 23:30 UTC
   on 28.10 shows 29.10.2026. Tests: Task 5,
   `test_local_date_crosses_midnight_in_warsaw`; Task 7,
   `test_dates_use_polish_time`.
5. **A stale tab gets the research 404.** "Zapisz" on a note that
   another tab deleted gives that page with a link back to the panel.
   Test: Task 8, `test_saving_a_deleted_note_is_the_research_404`.

---

### Task 1: Thesis closing date (`closed_at`, revision 0008)

**Files:**
- Create: `alembic/versions/0008_theses_closed_at.py`,
  `tests/test_theses_closed_at_migration.py`,
  `tests/integration/test_postgres_theses_closed_at_migration.py`
- Modify: `app/models/database_models.py` (`ThesisDB`),
  `app/models/research.py` (`Thesis`),
  `app/repositories/thesis_repository.py`
- Modify tests: `tests/research_cases.py`,
  `tests/test_research_notes.py`, `tests/test_watchlist_migration.py`,
  `tests/test_alembic_env.py`

**Interfaces:**
- Produces:
  - `ThesisDB.closed_at = Column(UTCDateTime(), nullable=True)`,
    declared last, after `updated_at`. `op.add_column` appends, and
    `research_schema` compares columns in order;
  - `Thesis.closed_at: datetime | None = None`;
  - revision `"0008"`, `down_revision = "0007"`.
- Semantics, read by Tasks 4, 7, and 9:
  - `closed_at` is set when the status changes to `closed`, from the
    same `datetime.now(timezone.utc)` as `updated_at`;
  - it is cleared when the status changes to `active`;
  - it is unchanged when the status does not change.
- `create` keeps the server defaults for `created_at` and `updated_at`.
  It sets `closed_at` (Python clock) only for `status=CLOSED`.

- [ ] **Step 1: Write the failing tests.**
  - On `ResearchBehavior` in `tests/research_cases.py` (runs on SQLite
    and PostgreSQL):
    - `test_closing_sets_closed_at_and_reopening_clears_it`:
      - a new thesis has `closed_at is None`;
      - `set_status(CLOSED)` gives an aware `closed_at ==
        thesis.updated_at`;
      - `set_status(ACTIVE)` gives `closed_at is None`.
    - `test_update_that_changes_status_sets_closed_at`: the same rules
      through `update(ThesisUpdate(status=...))`.
    - `test_same_status_keeps_closed_at`:
      - close, then pin `closed_at` to `_OLD` with SQL;
      - `set_status(CLOSED)` leaves it at `_OLD`;
      - `update(ThesisUpdate(status=CLOSED, title="x"))` moves
        `updated_at` and leaves `closed_at == _OLD`.
    - `test_create_closed_sets_closed_at`: `status=CLOSED` on create
      gives an aware `closed_at`. An active create gives `None`.
    - In `test_column_lengths_and_check_use_the_constants`:
      - `ThesisDB.__table__.c.closed_at.nullable is True`;
      - `list(ThesisDB.__table__.c.keys())[-1] == "closed_at"`.
  - Head pins in `tests/test_research_notes.py`,
    `tests/test_watchlist_migration.py`, and `tests/test_alembic_env.py`:
    the only head is `"0008"`, and `get_revision("0008").down_revision
    == "0007"`.
  - `tests/test_theses_closed_at_migration.py`,
    `test_0008_backfills_closed_rows_and_downgrade_restores_0007(tmp_path)`.
    Use the helpers in `tests/company_migration.py` (`LEGACY_COMPANIES`,
    `LEGACY_METRICS`, `upgrade_to`, `upgrade_head`, `downgrade_to`).
    Commit where the comments say, because Alembic runs inside the
    caller's transaction:

```python
upgrade_to(connection, "0007")
# insert a company, one active thesis, one closed thesis with
# updated_at pinned to two distinct values
connection.commit()
upgrade_head(connection)
# closed row: closed_at == updated_at; active row: closed_at IS NULL
connection.commit()
downgrade_to(connection, "0007")
connection.commit()
assert version(connection) == "0007"
assert "closed_at" not in column_names(connection, "theses")
# INSERT with status 'bogus' raises IntegrityError -> rollback
assert version(connection) == "0007"  # the rollback did not undo it
# deleting the company still deletes its theses (FK cascade kept)
connection.commit()
upgrade_head(connection)
connection.commit()
assert version(connection) == "0008"
assert "closed_at" in column_names(connection, "theses")
```

  - There is no `assert_compare_metadata_is_empty` on the legacy file,
    because its companies tables always differ. The empty diff through
    0008 is covered by the existing autogenerate checks (create_all,
    drop notes and theses, stamp 0004, upgrade head) in
    `tests/test_sqlite_notes_migration.py` and
    `tests/integration/test_postgres_notes_migration.py`.
  - The PostgreSQL file runs the same sequence with that module's
    helpers. Wrap the bogus insert in `connection.begin_nested()`.

- [ ] **Step 2: Run the tests to verify they fail.**
  Run: `.venv/bin/pytest tests/test_research_notes.py tests/test_theses_closed_at_migration.py tests/test_watchlist_migration.py tests/test_alembic_env.py -q`
  Expected: FAIL. `closed_at` is missing, and the head is `"0007"`.

- [ ] **Step 3: Implement.**
  - The column on `ThesisDB`, with a comment: it is set by the
    repository, and there is no server default.
  - `Thesis.closed_at`.
  - Revision 0008:
    - `op.add_column` with `sa.DateTime(timezone=True)`, nullable;
    - `UPDATE theses SET closed_at = updated_at WHERE status = 'closed'`;
    - downgrade drops the column. On SQLite use `op.batch_alter_table`,
      keeping `ck_theses_status`, `fk_theses_company_id`, and
      `ix_theses_company_id`. The Step 1 test decides.
  - One private helper in `ThesisRepository` sets `status`,
    `updated_at`, and `closed_at` from one clock. `update` and
    `set_status` use it.
  - Update the docstrings and the "Same clocks" comment in
    `database_models.py`.

- [ ] **Step 4: Run the tests to verify they pass.**
  Run the Step 2 command, then `.venv/bin/pytest tests/test_sqlite_notes_migration.py tests/test_sqlite_legacy_migration.py tests/test_price_bar_migration.py tests/test_ticker_upper_migration.py -q`.
  These downgrade through 0008 too.
  Expected: PASS, except the two known SQLite 3.54 failures in
  `tests/test_price_bar_migration.py`.

- [ ] **Step 5: Commit.**
  `git commit -m "feat: record when a thesis was closed (revision 0008)"`

### Task 2: Startup refuses a pre-0008 `theses` table

**Files:**
- Modify:
  - `app/core/init_db.py`;
  - `alembic/versions/0005_notes_and_theses.py` (docstring only);
  - `README.md` (the migration bullets near line 186);
  - `docs/api-demo.md` (near line 175);
  - `docs/RUN_DEMO.md` (Troubleshooting).
- Test: `tests/test_init_db.py`, `tests/test_lifespan_cors.py`

**Interfaces:**
- Produces:
  - `class ThesisSchemaError(RuntimeError)`;
  - `def require_thesis_closed_at_column(db_engine) -> None`.
- `init_db()` calls it after `require_company_instrument_columns(engine)`.

- [ ] **Step 1: Write the failing tests.**
  - In `tests/test_init_db.py`, with the `memory_engine` fixture:
    - `test_missing_theses_table_is_left_for_create_all`;
    - `test_current_theses_table_passes`, after
      `Base.metadata.create_all`;
    - `test_init_db_rejects_theses_without_closed_at`: create `theses`
      by SQL without `closed_at`, expect `ThesisSchemaError`, and check
      the message contains `"theses is missing closed_at"`,
      `"alembic upgrade head"`, and `"alembic stamp 0007"`.
  - In `tests/test_lifespan_cors.py`, `isolated_startup` also stubs
    `require_thesis_closed_at_column`. The startup test asserts it was
    called once with `engine`.

- [ ] **Step 2: Run the tests to verify they fail.**
  Run: `.venv/bin/pytest tests/test_init_db.py tests/test_lifespan_cors.py -q`
  Expected: FAIL with an ImportError or AttributeError.

- [ ] **Step 3: Implement.** The check follows
  `require_company_instrument_columns`. Message, verbatim:
  ``"theses is missing closed_at. An Alembic-managed database runs `alembic upgrade head`. A database created by an older startup create_all is first stamped with the Alembic head of the version that created it (`alembic stamp 0007` for a database created on or after 2026-10-22), then runs `alembic upgrade head`."``

  Doc edits:
  - `CompanySchemaError`: its last sentence says the fresh `create_all`
    database is one built by this version. Keep the phrase
    `alembic stamp head`, which `tests/test_init_db.py` pins.
  - The 0005 docstring, the README bullets, and `docs/api-demo.md` say
    that `alembic stamp head` is only for a database the current
    version built.
  - `docs/RUN_DEMO.md` Troubleshooting: a demo file kept with `--keep`
    from before 0008 refuses to start. Run without `--keep`.
  - `test_operator_docs_do_not_offer_adding_columns_by_hand` must stay
    green.

- [ ] **Step 4: Run the tests to verify they pass.**
  Run the Step 2 command. Expected: PASS.

- [ ] **Step 5: Commit.**
  `git commit -m "feat: stop startup on a theses table without closed_at"`

### Task 3: Failed inserts become `ResearchStorageError`

**Files:**
- Modify: `app/repositories/research_store.py`,
  `app/repositories/note_repository.py`,
  `app/repositories/thesis_repository.py` (the `create` methods)
- Test: `tests/research_cases.py`

**Interfaces:**
- Produces: `NoteRepository.create` and `ThesisRepository.create` raise
  only `CompanyNotFoundError` or `ResearchStorageError`, and the
  session is usable afterwards.
- The mapped block covers:
  - the existence check;
  - the commit;
  - the refresh.

- [ ] **Step 1: Write the failing tests.**
  - Replace `test_unexpected_integrity_error_is_reraised_and_session_recovers`
    with
    `test_unexpected_integrity_error_on_create_is_a_storage_error_and_session_recovers`.
    Keep its trigger:

```python
with pytest.raises(ResearchStorageError) as caught:
    ...  # the existing always-failing commit
monkeypatch.undo()
assert str(caught.value) == "Note or thesis could not be stored"
assert caught.value.__cause__ is None
assert caught.value.__context__ is None
assert NoteRepository(session).create(company.id, NoteCreate(body="ok"))
```

  - Add `test_operational_error_on_create_is_a_storage_error_and_session_recovers`:
    - parametrize over the note and the thesis repository, and over
      the patched step (`session.commit` and `session.refresh`);
    - each raises `OperationalError("stmt", {}, Exception("database is
      locked"))` once;
    - the same four assertions follow.

- [ ] **Step 2: Run the tests to verify they fail.**
  Run: `.venv/bin/pytest tests/test_research_notes.py -q -k storage_error`
  Expected: FAIL. The raw driver error escapes.

- [ ] **Step 3: Implement.**
  - On any `SQLAlchemyError`, roll back.
  - A missing company stays `CompanyNotFoundError`. Everything else
    becomes `ResearchStorageError`.
  - Raise after the `except` block, the way the module already does.
  - Update the `ResearchStorageError` and `commit_company_scoped`
    docstrings.

- [ ] **Step 4: Run the tests to verify they pass.**
  Run: `.venv/bin/pytest tests/test_research_notes.py -q`
  Expected: PASS.

- [ ] **Step 5: Commit.**
  `git commit -m "fix: map failed note and thesis inserts to ResearchStorageError"`

### Task 4: JSON API for notes and theses

**Files:**
- Create: `app/api/research.py`, `tests/test_research_api.py`
- Modify: `main.py` (include both routers under `settings.API_V1_STR`)

**Interfaces:**
- Consumes: Task 1 `Thesis.closed_at`, and Task 3 typed errors.
- Produces:
  - `notes_router = APIRouter(prefix="/instruments", tags=["notes"])`;
  - `theses_router = APIRouter(prefix="/instruments", tags=["theses"])`;
  - `ItemId = Annotated[int, Path(gt=0, le=2**63 - 1)]`, for
    `instrument_id`, `note_id`, and `thesis_id`.
- Fixed details: `"Instrument not found"`, `"Note not found"`,
  `"Thesis not found"`, `"Note or thesis could not be stored"`.
- Routes, as in the spec table:
  - lists return `list[Note]` / `list[Thesis]` in repository order
    (`updated_at` desc, then `id` desc);
  - `POST` is 201;
  - `PUT` is a partial update through `update()`, including `status`,
    200;
  - `DELETE` is 204;
  - `GET /theses` takes `status: ThesisStatus | None = None`.
- Order of checks in every route:
  1. the instrument (`CompanyRepository(db).get_by_id`), else 404;
  2. the repository call;
  3. `None` or `False` means the item 404;
  4. `CompanyNotFoundError` means the instrument 404;
  5. `ResearchStorageError` means the 500, raised after the `except`
     block (`app/api/watchlist.py`).

- [ ] **Step 1: Write the failing tests** in `tests/test_research_api.py`
  (the `client` fixture; seed companies the way `tests/test_watchlist.py`
  does):
  - `test_note_crud_round_trip`:
    - POST gives 201 with `id`, `company_id`, `body`, and aware
      timestamps;
    - GET list and GET one work;
    - PUT `{"body": "b2"}` gives 200;
    - PUT `{}` gives 200 with `updated_at` unchanged;
    - DELETE gives 204, and a repeat gives 404 `Note not found`.
  - `test_thesis_crud_close_and_reopen`:
    - POST gives `status == "active"` and `closed_at is None`;
    - PUT `{"status": "closed"}` gives a `closed_at`;
    - `?status=closed` lists it, and `?status=active` does not;
    - PUT `{}` leaves the thesis unchanged;
    - PUT `{"status": "active"}` gives `closed_at is None`;
    - DELETE gives 204.
  - `test_lists_use_repository_order`: with pinned `updated_at`, the
    newest edit comes first.
  - `test_unknown_instrument_is_checked_first`: for instrument 999, GET
    list, POST, GET one, PUT, and DELETE on notes and on theses all give
    404 `Instrument not found`, never an empty list.
  - `test_item_of_another_instrument_is_404`: a note of company A read
    through company B is 404 `Note not found`. The same for a thesis.
  - `test_ids_are_bounded` (parametrize over `0`, `-1`, `abc`, `2**63`):
    422 on every path. `2**63 - 1` gives 404.
  - `test_status_filter_rejects_other_values`: `?status=open` is 422.
  - `test_lengths_and_text_rules`:
    - the boundaries pass and fail at title 200/201, body 10000/10001,
      breakers 5000/5001, and note body 10000/10001, with
      `string_too_long`;
    - `"a\r\nb"` is stored as `"a\nb"`;
    - a blank body gives 422 with `ctx.error.code == "blank"`;
    - an unknown key gives 422 `extra_forbidden`.
  - `test_storage_failure_is_a_fixed_500`: patch `NoteRepository.create`
    and `ThesisRepository.update` to raise `ResearchStorageError()`.
    POST and PUT give 500 `{"detail": "Note or thesis could not be
    stored"}`.
  - `test_openapi_lists_notes_and_theses`: `/api/v1/openapi.json` has
    both tags, and `maxLength` 10000 on `NoteCreate.body` and 200 on
    `ThesisCreate.title`.

- [ ] **Step 2: Run the tests to verify they fail.**
  Run: `.venv/bin/pytest tests/test_research_api.py -q`
  Expected: FAIL with 404 on every route.

- [ ] **Step 3: Implement** `app/api/research.py` and wire it in
  `main.py`.

- [ ] **Step 4: Run the tests to verify they pass.**
  Run: `.venv/bin/pytest tests/test_research_api.py tests/test_root_api.py -q`
  Expected: PASS.

- [ ] **Step 5: Commit.**
  `git commit -m "feat: add the notes and theses API"`

### Task 5: Polish-time formatters

**Files:**
- Modify: `app/ui/formatting.py`, `app/ui/templating.py` (render context)
- Test: `tests/test_ui_formatting.py`

**Interfaces:**
- Produces:
  - `DISPLAY_TIMEZONE = ZoneInfo("Europe/Warsaw")`;
  - `format_local_datetime(value, language) -> str | None`;
  - `format_local_date(value, language) -> str | None`.
- Both take an aware or naive UTC `datetime`, through `as_utc`. Any
  other value returns `None`. Both are in `render`'s context.

- [ ] **Step 1: Write the failing tests:**

```python
def test_local_datetime_uses_warsaw_time():
    winter = datetime(2026, 10, 28, 13, 5, tzinfo=timezone.utc)
    summer = datetime(2026, 7, 1, 12, 5, tzinfo=timezone.utc)
    assert format_local_datetime(winter, "pl") == "28.10.2026, 14:05"
    assert format_local_datetime(winter, "en") == "Oct 28, 2026, 14:05"
    assert format_local_datetime(summer, "pl") == "01.07.2026, 14:05"
    assert format_local_datetime(winter.replace(tzinfo=None), "pl") == (
        "28.10.2026, 14:05"
    )
    assert format_local_datetime(None, "pl") is None


def test_local_date_crosses_midnight_in_warsaw():
    late = datetime(2026, 10, 28, 23, 30, tzinfo=timezone.utc)
    assert format_local_date(late, "pl") == "29.10.2026"
    assert format_local_date(late, "en") == "Oct 29, 2026"
```

- [ ] **Step 2: Run the tests to verify they fail.**
  Run: `.venv/bin/pytest tests/test_ui_formatting.py -q`
  Expected: FAIL with an ImportError.

- [ ] **Step 3: Implement.** Reuse `_ENGLISH_MONTHS`.

- [ ] **Step 4: Run the tests to verify they pass.** Same command.
  Expected: PASS.

- [ ] **Step 5: Commit.**
  `git commit -m "feat: format note and thesis times in Polish time"`

### Task 6: HTMX swaps 422; links fall back; stale autofocus is cleared

**Files:**
- Modify: `app/ui/templates/base.html` (the `htmx-config` meta),
  `static/ui.js`
- Create: `tests/test_ui_js.py`
- Test: `tests/test_ui_templates.py` (the pinned marker),
  `tests/test_ui_pages.py`, `tests/test_ui_watchlist.py`

**Interfaces:**
- Produces:
  1. HTMX swaps a 422 without `htmx:responseError`. Every other 4xx and
     5xx behaves as today.
  2. `[data-plain-fallback]` on an `A` element makes `ui.js` call
     `window.location.assign(element.href)` on `htmx:responseError` and
     `htmx:sendError`. Forms keep `form.submit()`.
  3. On `htmx:afterSettle`, `ui.js` removes `autofocus` from every
     element inside `event.target`. HTMX focuses `[autofocus]` in the
     settle tasks, before that event. Without the cleanup, a preserved
     element would carry a stale `autofocus` into the next swap.

- [ ] **Step 1: Write the failing tests.**
  - The marker in `test_htmx_config_disables_the_indicator_style`
    becomes, verbatim:

```html
<meta name="htmx-config" content='{"includeIndicatorStyles":false,"allowEval":false,"allowScriptTags":false,"responseHandling":[{"code":"204","swap":false},{"code":"[23]..","swap":true},{"code":"422","swap":true},{"code":"[45]..","swap":false,"error":true}]}'>
```

    HTMX 2.0.10 merges the meta shallowly, so this list replaces the
    default (`204`, `[23]..`, `[45]..`). It is that default with `422`
    inserted before `[45]..`. The first match wins.
  - `test_pages_render_in_polish_by_default` also asserts
    `'{"code":"422","swap":true}' in page.text`.
  - `tests/test_ui_js.py`, `test_ui_js_repeats_marked_requests`:
    - skip when `shutil.which("node")` is None;
    - write a small harness to `tmp_path` that stubs
      `document.addEventListener`, `window.location.assign`, and
      `querySelectorAll`, then loads `static/ui.js`;
    - dispatch `htmx:responseError` and `htmx:sendError` with
      `detail.elt` set to a marked FORM, a marked A, and an unmarked
      element;
    - expect `submit()` twice, `assign(href)` twice, and nothing for the
      unmarked one;
    - dispatch `htmx:afterSettle`, and expect every `autofocus` removed.

- [ ] **Step 2: Run the tests to verify they fail.**
  Run: `.venv/bin/pytest tests/test_ui_templates.py tests/test_ui_pages.py tests/test_ui_js.py -q`
  Expected: FAIL on the marker, the substring, and the link and
  autofocus cases.

- [ ] **Step 3: Implement.**
  - First confirm that no HTMX request reaches FastAPI's JSON 422:
    - `grep -rn "status_code=422" app/ui`;
    - every HTMX-reachable `/ui` route takes `str` ids and defaulted
      form fields.

    Note the result in the commit message.
  - Update the meta, and extend `ui.js` (rename the handler to
    `repeatWithoutHtmx`).

- [ ] **Step 4: Run the tests to verify they pass.**
  Run the Step 2 command plus `tests/test_ui_watchlist.py`.
  Expected: PASS.

- [ ] **Step 5: Commit.**
  `git commit -m "feat: let HTMX swap 422, fall back on links, clear stale autofocus"`

### Task 7: The panel: button, view model, and read-only display

**Files:**
- Create:
  - `app/ui/research_view.py`;
  - `app/ui/research_forms.py` (router and the panel GET);
  - `app/ui/templates/partials/research_toggle.html`;
  - `app/ui/templates/partials/research_panel.html`;
  - `tests/test_ui_research.py`.
- Modify:
  - `app/ui/router.py` (a shared `detail_page`, the `research` query);
  - `app/ui/templates/instrument_detail.html`;
  - `app/ui/catalog.py`;
  - `static/ui.css`;
  - `main.py`.
- Modify tests: `tests/ui_html.py` (move `_FormInParagraph` there from
  `tests/test_ui_watchlist.py`), `tests/test_ui_watchlist.py`

**Interfaces:**
- Consumes: Task 5 formatters, and Task 1 `closed_at`.
- Produces (`app/ui/research_view.py`):

```python
@dataclass(frozen=True)
class PanelForm:
    kind: str  # "note_edit", "note_delete", "thesis_new",
               # "thesis_edit", "thesis_delete"
    item_id: int | None = None
    values: dict[str, str] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)  # field -> key
    form_error: str | None = None  # catalog key

@dataclass(frozen=True)
class NewNote:
    body: str = ""
    errors: dict[str, str] = field(default_factory=dict)
    form_error: str | None = None
    preserve: bool = True  # False only for its own add and its own 422

@dataclass(frozen=True)
class ResearchPanel:
    company_id: int
    notes: list[Note]            # created_at desc, then id desc
    active_theses: list[Thesis]  # created_at desc, then id desc
    closed_theses: list[Thesis]  # closed_at desc (None last), id desc
    form: PanelForm | None
    new_note: NewNote
    show_closed: bool            # <details open>
    focus: str | None            # id of the one element with autofocus
    state_path: str              # GET URL of this state, for PL/EN

    @property
    def count(self) -> int: ...  # notes + all theses

def research_count(db: Session, company_id: int) -> int: ...
def build_panel(db: Session, company_id: int, *, form=None,
                new_note=None, show_closed=False, focus=None,
                state_path=None) -> ResearchPanel: ...
```

- `app/ui/router.py`:
  - `detail_page(request, db, instrument, *, research_panel=None,
    status_code=200)` renders `instrument_detail.html` with today's
    context plus `research_panel`, `research_count`, and
    `research_open`;
  - `instrument_detail` takes `research: str = ""`. `"open"` builds the
    panel.
- `app/ui/research_forms.py`:
  - `router = APIRouter(prefix="/ui", tags=["ui"],
    dependencies=[Depends(require_same_origin)])`;
  - `GET /companies/{company_id}/research`:
    - `research` defaults to `"open"`, and `"closed"` gives the empty
      panel;
    - `focus` is accepted only if it matches `^(note|thesis)-[0-9]+$`;
      otherwise it is ignored.
  - `_panel_response(request, db, company, panel, *, status_code=200)`
    answers in two ways:
    - HTMX: the panel partial, plus out of band the whole
      `<form id="research-toggle" hx-swap-oob="true">` and both
      `language-next-pl` and `language-next-en` inputs set to
      `panel.state_path`. Use the same markup as
      `partials/instrument_results.html`;
    - plain: `detail_page(...)`.
- Markup the tests pin:
  - `research-toggle` form:
    - `method="get"`, `action="/ui/instruments/{id}#research"`;
    - hidden `research=open` or `closed` (the next state);
    - `hx-get="/ui/companies/{id}/research"`, `hx-target="#research"`,
      `hx-swap="outerHTML"`;
    - `hx-sync="#research:drop"` and `data-plain-fallback`.
  - Its button is `research-toggle-button`, with `aria-expanded`,
    `aria-controls="research"`, and the accessible name
    `research.toggle_count`. The visible count sits next to the icon.
  - The open panel is `<section id="research" hx-sync="this:drop">`
    with the heading `research-title` (`tabindex="-1"`). The closed
    panel is `<div id="research"></div>`.
  - Ids:
    - items `note-{id}` and `thesis-{id}`, both `tabindex="-1"`;
    - fields `{prefix}-{field}`, with prefix `note-new`, `note-{id}`,
      `thesis-new`, or `thesis-{id}`;
    - field errors `{prefix}-{field}-error`;
    - the form summary `{prefix}-errors`.
  - Body and breakers: `<p class="research-text">{{ value }}</p>`, flush.
    The title element has class `thesis-title`.
- Catalog keys (PL / EN):

| Key | PL | EN |
|---|---|---|
| `research.toggle` | Notatki i tezy | Notes and theses |
| `research.toggle_count` | Notatki i tezy ({count}) | Notes and theses ({count}) |
| `research.theses` | Tezy | Theses |
| `research.notes` | Notatki | Notes |
| `research.no_theses` | Brak tez. | No theses yet. |
| `research.no_active_theses` | Brak aktywnych tez. | No active theses. |
| `research.no_notes` | Brak notatek. | No notes yet. |
| `research.edited` | edytowano {datetime} | edited {datetime} |
| `research.since` | od {date} | since {date} |
| `research.closed_on` | zamknięta {date} | closed {date} |
| `research.status_active` | aktywna | active |
| `research.status_closed` | zamknięta | closed |
| `research.closed_theses` | Zamknięte tezy ({count}) | Closed theses ({count}) |
| `field.thesis_body` | Dlaczego kupiłem | Why I bought |
| `field.thesis_breakers` | Kiedy sprzedam / co złamie tezę | When I sell / what breaks the thesis |

- [ ] **Step 1: Write the failing tests** in `tests/test_ui_research.py`.
  - Seed through the repositories on
    `client.app.state.testing_session_local()`.
  - For a row that was not edited, pin `created_at` and `updated_at` to
    the same value. Pin every timestamp that a test asserts.
  - Tests:
  - `test_toggle_sits_beside_the_heart`:
    - inside `.instrument-name`, after the heart;
    - every toggle attribute listed above;
    - with 2 notes and 1 thesis: the name "Notatki i tezy (3)" and a
      visible "3";
    - with nothing stored: "Notatki i tezy" and no number;
    - the page has `<div id="research"></div>`, and no `hx-swap-oob`
      anywhere.
  - `test_open_panel_lists_theses_then_notes`, with `?research=open`
    and `GET /ui/companies/{id}/research` without parameters:
    - `aria-expanded="true"` and hidden `research=closed`;
    - inside `id="research"`, the "Tezy" heading comes before
      "Notatki";
    - active theses are newest created first;
    - two closed theses sit inside `<details>` "Zamknięte tezy (2)",
      newest `closed_at` first;
    - notes are newest created first, and editing an old note does not
      move it;
    - "edytowano 29.10.2026, 10:00" (for `09:00Z`) appears only inside
      the edited note's element;
    - empty breakers show "brak danych";
    - with only closed theses: "Brak aktywnych tez.";
    - with no theses: "Brak tez." and no `<details>`;
    - with no notes: "Brak notatek.".
  - `test_dates_use_polish_time`:
    - a note created at `13:05Z` shows "28.10.2026, 14:05";
    - a thesis created and closed at `2026-10-28T23:30Z` shows
      "od 29.10.2026" and "zamknięta 29.10.2026".
  - `test_panel_fragment_and_closing`:
    - HTMX GET open gives 200, no `<html`, the panel, and one
      `hx-swap-oob` element, which is `form id="research-toggle"`. It
      has hidden `research=closed` and `aria-expanded="true"`;
    - both language inputs carry `/ui/instruments/{id}?research=open`;
    - HTMX GET `research=closed` gives `<div id="research"></div>`, the
      form with `research=open` and `aria-expanded="false"`, and
      language inputs `/ui/instruments/{id}`;
    - the open panel has `hx-sync="this:drop"`;
    - the fragment has no `autofocus`;
    - the UI headers are present.
  - `test_script_payload_is_escaped_in_the_panel`: `_SCRIPT` in a note
    body, a thesis title, a body, and breakers shows as `&lt;script&gt;`
    in the page and in the HTMX fragment. `<script>alert` never
    appears.
  - `test_research_text_keeps_breaks_and_wraps`:
    - store `"line1\nline2"`;
    - `class="research-text">line1\nline2</p>` appears verbatim for the
      note body, the thesis body, and the breakers;
    - `static/ui.css` gives `.research-text` both `white-space: pre-wrap`
      and `overflow-wrap: anywhere`, and gives `.thesis-title`
      `overflow-wrap: anywhere`;
    - a 200-character title without spaces renders inside
      `.thesis-title`.
  - `test_panel_in_english`: with the `ui_lang=en` cookie: "Notes and
    theses", "Theses", "Why I bought", and "Oct 28, 2026, 14:05".
  - `test_unknown_company_panel_is_the_instrument_404`: `abc`, `01`,
    and `999999` give 404 HTML for both plain and HTMX.
  - Layout, with notes and theses present:
    - the heart id appears once;
    - `_FormInParagraph` (now in `tests/ui_html.py`) finds no form
      inside a `<p>`;
    - no `style=`.

- [ ] **Step 2: Run the tests to verify they fail.**
  Run: `.venv/bin/pytest tests/test_ui_research.py -q`
  Expected: FAIL. There is no toggle, and the route is 404.

- [ ] **Step 3: Implement.**
  - The panel goes right after `.instrument-name`.
  - The icon is an inline SVG with `stroke="currentColor"` and a class.
  - The toggle reuses the `.watchlist-heart` inline-form rules.
  - A note counts as edited when `updated_at > created_at`.

- [ ] **Step 4: Run the tests to verify they pass.**
  Run: `.venv/bin/pytest tests/test_ui_research.py tests/test_ui_pages.py tests/test_ui_templates.py tests/test_ui_catalog.py tests/test_ui_watchlist.py -q`
  Expected: PASS.

- [ ] **Step 5: Commit.**
  `git commit -m "feat: open notes and theses in a panel on the company page"`

### Task 8: Note forms in the panel

**Files:**
- Modify:
  - `app/ui/research_forms.py`;
  - `app/ui/research_view.py`;
  - `app/ui/templates/partials/research_panel.html`;
  - `app/ui/templating.py` (`_get_form_for_post`);
  - `app/ui/catalog.py`.
- Create: `app/ui/templates/research_not_found.html`
- Test: `tests/test_ui_research.py`, `tests/test_ui_pages.py`,
  `tests/ui_html.py` (move `_FormParser`, `_parse_form`, and
  `_assert_labeled` there as `assert_labeled`), `tests/test_ui_forms.py`
  (import them back)

**Interfaces:**
- Consumes: Task 7 `build_panel`, `PanelForm`, `NewNote`, and
  `_panel_response`. Task 6 makes a 422 swap.
- Produces:
  - `validate_note(values: dict, *, update: bool) -> tuple[NoteCreate |
    NoteUpdate | None, dict[str, str], str | None]`.
  - `research_error_key(error: dict) -> str`, mapping:
    - `missing` → `error.required`;
    - `string_too_long` → `error.max_{ctx["max_length"]}` for 200,
      5000, and 10000, else `error.too_long`;
    - `value_error` whose `ctx["error"]` is a `TextValidationError`
      with code `blank` → `error.required`;
    - every other case → `error.invalid`.
  - `_research_not_found(request, company)`: 404 with
    `research_not_found.html`.
  - `_changed(request, db, company, panel)`: HTMX gets a 200 panel.
    Plain gets a 303 to `/ui/instruments/{id}?research=open#research`.
- Routes:
  - `company_id` and `note_id` are `str`, and `body` is `Form("")`;
  - `POST /companies/{company_id}/notes`;
  - `GET` and `POST /companies/{company_id}/notes/{note_id}/edit`;
  - `GET` and `POST /companies/{company_id}/notes/{note_id}/delete`.
- Saving an edit whose validated body equals the stored body skips
  `update()`.
- Every `<form>` and every `<a hx-get>` inside `#research` has:
  - `data-plain-fallback`;
  - `hx-target="#research"`;
  - `hx-swap="outerHTML"`.
- "Anuluj" is
  `GET /ui/companies/{id}/research?focus=note-{id}`.
- `panel.state_path`, which the language switch opens, is the GET URL
  of the state shown:
  - an inline form or question uses its own GET (`.../notes/{id}/edit`,
    `.../notes/{id}/delete`);
  - every other answer uses `/ui/instruments/{id}?research=open`.

  Task 9 applies the same rule to `.../theses/new`, `.../edit`, and
  `.../delete`.
- The draft wrapper is
  `<div id="note-new-field" hx-preserve="true">`. It holds the textarea
  and its field error. The attribute is left out for the add's own
  success and its own 422.
- Item actions are labelled with `research.edit_note_named` and
  `research.delete_note_named` (in `aria-label`).
- Focus, one `autofocus` per answer at most:

| After | `panel.focus` |
|---|---|
| add (HTMX success) | `note-new-body` |
| a 422 on add or edit | `note-new-errors` or `note-{id}-errors` (`tabindex="-1"`) |
| edit form opened | `note-{id}-body` |
| delete question | `note-{id}-delete-question` (`tabindex="-1"`), never the button |
| save, or "Anuluj" | `note-{id}` |
| delete | the next note, else the previous one, else `research-title` |

- `_get_form_for_post`, exact values:
  - `POST /ui/companies/7/notes` → `/ui/companies/7/research`;
  - `POST /ui/companies/7/notes/3/edit` →
    `/ui/companies/7/notes/3/edit`;
  - `POST /ui/companies/7/notes/3/delete` →
    `/ui/companies/7/notes/3/delete`.
- New catalog keys:

| Key | PL | EN |
|---|---|---|
| `research.new_note` | Nowa notatka | New note |
| `field.note_body` | Treść notatki | Note text |
| `action.add_note` | Dodaj notatkę | Add note |
| `action.edit` | Edytuj | Edit |
| `action.delete` | Usuń | Delete |
| `research.edit_note_named` | Edytuj notatkę z {datetime} | Edit the note from {datetime} |
| `research.delete_note_named` | Usuń notatkę z {datetime} | Delete the note from {datetime} |
| `delete.note_question` | Usunąć tę notatkę? | Delete this note? |
| `error.max_200` | Najwyżej 200 znaków. | At most 200 characters. |
| `error.max_5000` | Najwyżej 5000 znaków. | At most 5,000 characters. |
| `error.max_10000` | Najwyżej 10 000 znaków. | At most 10,000 characters. |
| `error.storage` | Nie udało się zapisać. Spróbuj ponownie. | Could not save. Try again. |
| `research_not_found.title` | Nie znaleziono notatki ani tezy | Note or thesis not found |
| `research_not_found.back` | Wróć do notatek i tez | Back to notes and theses |

- [ ] **Step 1: Write the failing tests.** Use `_post` with
  `origin: http://127.0.0.1` and `hx-request: true` for HTMX, as in
  `tests/test_ui_watchlist.py`.
  - `test_add_note_plain_and_htmx`:
    - plain POST gives 303 to `/ui/instruments/{id}?research=open#research`;
    - HTMX gives 200 with the note;
    - `note-new-body` is empty, has no `hx-preserve` wrapper, and holds
      the only `autofocus`;
    - the out-of-band form shows "(1)".
  - `test_crlf_note_at_the_limit_is_saved`:
    - `"a" * 4999 + "\r\n" + "a" * 5000` (10001 raw) gives 303, and the
      stored body has 10000 characters, one `"\n"`, and no `"\r"`;
    - `"a" * 5000 + "\r\n" + "a" * 5000` gives 422 with
      "Najwyżej 10 000 znaków." and the text kept.
  - `test_invalid_note_is_422_and_keeps_the_text`, for plain and HTMX:
    - blank gives 422 "To pole jest wymagane.";
    - `aria-invalid="true"`, and `assert_labeled` passes;
    - the summary links to `#note-new-body`, and `note-new-errors` has
      the only `autofocus`;
    - the typed text is kept;
    - with `"</textarea>" + _SCRIPT`: neither `"</textarea><script>"`
      nor `_SCRIPT` appears raw, and `&lt;/textarea&gt;&lt;script&gt;`
      does;
    - the plain 422 is the full page with the panel open.
  - `test_invalid_note_edit_keeps_the_text`: the 422 re-renders the
    inline form. The summary links to `#note-{id}-body`.
  - `test_draft_survives_other_actions`: the HTMX answers for panel
    open, note edit GET, note delete GET, and "Anuluj" carry
    `<div id="note-new-field" hx-preserve="true">`.
  - `test_edit_note_inline`:
    - HTMX GET `.../edit` gives the inline form with the text, focused;
    - a plain GET gives the full page in that state;
    - POST gives 303, or 200 with "edytowano";
    - opening a second edit leaves one inline form;
    - a save with unchanged text does not add "edytowano".
  - `test_delete_note_asks_inline_then_deletes`:
    - the question "Usunąć tę notatkę?" has the `autofocus`, and the
      "Usuń" button does not;
    - POST deletes the note, then answers 303 or 200.
  - `test_note_focus_rules`: with three notes, every row of the focus
    table, including all three delete cases.
  - `test_note_actions_fall_back_and_are_named`:
    - every form and `a[hx-get]` in `#research` has the three
      attributes;
    - the edit and delete actions carry
      "Edytuj notatkę z 28.10.2026, 14:05" and
      "Usuń notatkę z 28.10.2026, 14:05".
  - `test_saving_a_deleted_note_is_the_research_404`:
    - delete through the repository, then POST `.../edit`;
    - 404, "Nie znaleziono notatki ani tezy", and a link to
      `/ui/instruments/{id}?research=open#research`.
  - `test_note_404s`:
    - another company's note is the research 404;
    - an unknown company is the instrument 404;
    - `.../notes/abc/edit` is the HTML 404 for plain and HTMX, not JSON.
  - `test_cross_origin_note_post_is_403`: nothing is stored.
  - `test_storage_failure_keeps_the_text`:
    - patch `NoteRepository.create`, then `NoteRepository.update`, to
      raise `ResearchStorageError()`;
    - plain gives 500 with "Nie udało się zapisać. Spróbuj ponownie."
      and the typed text;
    - HTMX gives 500.
  - `test_language_next_path_for_research_posts` in
    `tests/test_ui_pages.py`: the three exact mappings above.

- [ ] **Step 2: Run the tests to verify they fail.**
  Run: `.venv/bin/pytest tests/test_ui_research.py tests/test_ui_pages.py -q`
  Expected: FAIL on the new tests (405 or 404 on the routes).

- [ ] **Step 3: Implement** the routes, the validation, the 404 template,
  and the panel markup.

- [ ] **Step 4: Run the tests to verify they pass.**
  Run: `.venv/bin/pytest tests/test_ui_research.py tests/test_ui_pages.py tests/test_ui_forms.py tests/test_ui_catalog.py tests/test_ui_templates.py -q`
  Expected: PASS.

- [ ] **Step 5: Commit.**
  `git commit -m "feat: add, edit, and delete notes in the panel"`

### Task 9: Thesis forms in the panel

**Files:**
- Modify:
  - `app/ui/research_forms.py`;
  - `app/ui/research_view.py`;
  - `app/ui/templates/partials/research_panel.html`;
  - `app/ui/templating.py`;
  - `app/ui/catalog.py`.
- Test: `tests/test_ui_research.py`, `tests/test_ui_pages.py`

**Interfaces:**
- Consumes: the Task 8 helpers and rules: fallback attributes, the
  draft wrapper, named actions, and the same-text skip.
- Produces: `validate_thesis(values: dict, *, update: bool)`, with the
  `validate_note` shape. Field order: `title`, `body`,
  `thesis_breakers`. It never sets `status`.
- Routes, with `str` ids and `Form("")` fields:
  - `GET /companies/{company_id}/theses/new`;
  - `POST /companies/{company_id}/theses`;
  - `GET` and `POST .../theses/{thesis_id}/edit`;
  - `POST .../theses/{thesis_id}/close` and `.../reopen`, through
    `set_status`, which is repeat-safe;
  - `GET` and `POST .../theses/{thesis_id}/delete`.
- `show_closed=True` whenever the action concerned a closed thesis.
- The close and reopen buttons share one id, `thesis-{id}-status`, so
  HTMX's id restore keeps focus on them. They need no `autofocus`.
- Focus otherwise:

| After | `panel.focus` |
|---|---|
| new form | `thesis-new-title` |
| add | `thesis-{new id}` |
| a 422 | `thesis-new-errors` or `thesis-{id}-errors` |
| edit form opened | `thesis-{id}-title` |
| save, or "Anuluj" | `thesis-{id}` |
| delete question | `thesis-{id}-delete-question`, never the button |
| delete | the next thesis in the same list, else the previous one, else `research-title` |

- `_get_form_for_post`, exact values:
  - `POST /ui/companies/7/theses` → `/ui/companies/7/theses/new`;
  - `POST /ui/companies/7/theses/4/close` → `/ui/companies/7/research`;
  - `POST /ui/companies/7/theses/4/reopen` → `/ui/companies/7/research`;
  - `POST /ui/companies/7/theses/4/edit` →
    `/ui/companies/7/theses/4/edit`;
  - `POST /ui/companies/7/theses/4/delete` →
    `/ui/companies/7/theses/4/delete`.
- New catalog keys:

| Key | PL | EN |
|---|---|---|
| `action.new_thesis` | + Nowa teza | + New thesis |
| `action.close_thesis` | Zamknij tezę | Close thesis |
| `action.reopen_thesis` | Otwórz ponownie | Reopen |
| `field.thesis_title` | Tytuł | Title |
| `research.edit_thesis_named` | Edytuj tezę „{title}” | Edit the thesis "{title}" |
| `research.delete_thesis_named` | Usuń tezę „{title}” | Delete the thesis "{title}" |
| `research.close_thesis_named` | Zamknij tezę „{title}” | Close the thesis "{title}" |
| `research.reopen_thesis_named` | Otwórz ponownie tezę „{title}” | Reopen the thesis "{title}" |
| `delete.thesis_question` | Usunąć tę tezę? | Delete this thesis? |

- [ ] **Step 1: Write the failing tests:**
  - `test_add_thesis_plain_and_htmx`:
    - the HTMX GET `new` form has three labelled fields and
      `thesis-new-title` focused;
    - POST gives 303, or 200 with an "aktywna" card that is focused;
    - the out-of-band count goes up.
  - `test_invalid_thesis_is_422`:
    - a blank title gives "To pole jest wymagane.";
    - the title `"a\nb"` gives "Ta wartość jest nieprawidłowa.";
    - title 201 gives "Najwyżej 200 znaków.", body 10001 gives
      "Najwyżej 10 000 znaków.", and breakers 5001 give
      "Najwyżej 5000 znaków.";
    - 200, 10000, and 5000 save;
    - the values are kept;
    - `_SCRIPT` is escaped, including inside `<input value>`;
    - the summary has the only `autofocus`.
  - `test_close_and_reopen`:
    - `close` gives status `closed` and a `closed_at`;
    - the card is inside `<details open>`;
    - `thesis-{id}-status` now reads "Otwórz ponownie", and the answer
      has no `autofocus`;
    - a second `close` changes nothing and answers 303 or 200;
    - `reopen` gives `active` and `closed_at is None`.
  - `test_edit_thesis_keeps_status`: editing a closed thesis keeps it
    closed and keeps `closed_at`. Unchanged values do not move
    `updated_at`.
  - `test_delete_thesis_asks_inline`: the question has the focus, not
    the button. Then the thesis is gone.
  - `test_thesis_focus_rules`: every row of the table above, with
    three active theses.
  - `test_thesis_draft_and_fallback`:
    - the answers for close, reopen, new, and edit keep the
      `note-new-field` wrapper with `hx-preserve`;
    - every new thesis form and link has the three attributes and its
      named label.
  - `test_thesis_storage_failure`: patch `ThesisRepository.create` and
    `ThesisRepository.set_status`. Plain gives 500 with
    `error.storage` and the typed values. HTMX gives 500.
  - `test_thesis_404s`:
    - another company's thesis and a deleted one give the research 404;
    - an unknown company gives the instrument 404;
    - `abc` ids give the HTML 404.
  - `test_language_next_path_for_thesis_posts`: the five exact mappings.

- [ ] **Step 2: Run the tests to verify they fail.**
  Run: `.venv/bin/pytest tests/test_ui_research.py tests/test_ui_pages.py -q`
  Expected: FAIL on the new tests.

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Run the tests to verify they pass.**
  Run the Task 8 Step 4 command. Expected: PASS.

- [ ] **Step 5: Commit.**
  `git commit -m "feat: add, edit, close, reopen, and delete theses in the panel"`

### Task 10: Delete warning, persistence, docs, browser check, review

**Files:**
- Modify:
  - `app/ui/catalog.py` (`delete.company_warning`);
  - `README.md` (API list);
  - `docs/api-demo.md` (a notes and theses section with curl);
  - `docs/RUN_DEMO.md` ("What you will see");
  - `docs/work-state.md`, `docs/development-journal.md`,
    `docs/HANDOFF.md`.
- Test: `tests/test_ui_research.py`, `tests/test_research_api.py`

**Interfaces:** none new.

- [ ] **Step 1: Write the failing tests:**
  - `test_company_delete_warns_about_notes_and_theses`: the confirm
    page says:
    - PL: "Usunięcie tej spółki usuwa także jej wskaźniki finansowe,
      notatki i tezy."
    - EN: "Deleting this company also deletes its financial metrics,
      notes, and theses."
  - `test_notes_survive_data_and_price_refresh`:
    - fetch-company `DEMO_PL_TECH` with the fake collector
      (`client.app.dependency_overrides[get_collector]`, as in
      `tests/test_data_collection_api.py`);
    - add a note and a thesis through the API;
    - fetch the company again, and POST
      `/api/v1/instruments/{id}/prices/refresh`;
    - both are still listed, unchanged.
  - `test_notes_survive_a_new_engine_on_the_same_file(tmp_path)`:
    - write through the repositories on `sqlite:///{tmp_path}/r.db`,
      and dispose the engine;
    - a new engine reads both rows.

- [ ] **Step 2: Run the tests.**
  Run: `.venv/bin/pytest tests/test_ui_research.py tests/test_research_api.py -q`
  Expected:
  - the warning test fails;
  - the two persistence tests pass at once. They pin behaviour that
    already holds; say so in the journal.

- [ ] **Step 3: Implement the copy, then the docs.**
  - `docs/api-demo.md`: one curl per route.
  - README: two endpoint lines.
  - `docs/RUN_DEMO.md`: the sticky note, the panel, and that the demo
    starts with no notes.
  - `docs/work-state.md`: replace the #96 section with this branch's
    state.
  - `docs/HANDOFF.md`:
    - state as of 2026-10-28;
    - #96 merged, #33 on this branch;
    - #102 (code review agent, priority high) and #103 (trade comments)
      in the queue.
  - The journal entry: scope, decisions, verification, model, and time.

- [ ] **Step 4: Full verification.**
  - The CI command:
    `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`.
    Expected: everything passes except the two known SQLite 3.54
    failures.
  - `black --check`, `isort --check-only`, and `flake8` on the changed
    Python files.
  - Chrome, on `python -m scripts.run_demo`, with the claude-in-chrome
    tools, using the mouse and the keyboard:
    - every browser item in the spec's "Done when";
    - `document.activeElement.id` after open, add, a 422, edit, delete,
      close, and reopen, compared with the focus tables;
    - a 422 on add, then open an edit form: the draft and its error
      are still together;
    - the 404 fallback through the stale-tab case: open an edit form,
      delete that note (one created in this check) in a second tab,
      then press "Zapisz";
    - a network error by stopping the server;
    - the console rule from the spec.
  - Final whole-branch review with superpowers:requesting-code-review.
    Fix the Critical and Important findings, each with a test written
    first.

- [ ] **Step 5: Commit.**
  `git commit -m "docs: record notes and theses (#33)"`
