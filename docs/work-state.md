# Current Work State

## Notes and theses (#33): 2026-10-29, work in progress

- Branch `feat/notes-theses-33`, from `master` `3c40413`. Not pushed;
  no pull request yet.
- Design: `docs/superpowers/specs/2026-10-28-notes-theses-design.md`.
  Plan: `docs/superpowers/plans/2026-10-28-notes-theses.md`, 10 tasks,
  run with subagent-driven development. The per-task ledger (rulings,
  deferred review findings, status) is the git-ignored
  `.superpowers/sdd/2026-10-28-notes-theses/progress.md`.
- Completed, each task reviewed (`15b5afb`..`d320dd0`):
  - Task 1: `theses.closed_at` (revision `0008`);
  - Task 2: startup refuses a `theses` table without `closed_at` and
    names the Alembic commands;
  - Task 3: a failed note or thesis insert is `ResearchStorageError`;
  - Task 4: the JSON API under `/api/v1/instruments/{id}/notes` and
    `/theses`;
  - Task 5: note and thesis times in Polish time (`Europe/Warsaw`);
  - Task 6: HTMX swaps a 422, marked links fall back to a plain
    request, and a stale `autofocus` is cleared;
  - Task 7: the sticky-note button and the read-only panel on
    `/ui/instruments/{id}`.
- Incomplete: Task 8 (note forms), Task 9 (thesis forms), Task 10
  (company delete warning, persistence tests, docs, Chrome check),
  then the final whole-branch review and the pull request.
- Tests: after Task 7 the CI command gives 1937 passed and the 3 known
  local failures, coverage 96.53%. The known failures are the two
  `0006` float boundary tests on local SQLite 3.54, and
  `tests/test_run_demo.py::test_child_process_does_not_inherit_dotenv_database`,
  which fails because a local git-ignored `demo/` directory exists.
  Not run: the PostgreSQL job (no local server) and GitHub Actions.
- Checkpoint reason: on 2026-10-29 the controlling session lost its
  terminal view in IntelliJ while its process kept running. A new
  session took over from the ledger at Task 7. The old process is idle
  and does no work.
- Active agents: none at this checkpoint. Blockers: none. Account
  usage was not available in this session.
- Next action: Task 8, note forms in the panel.

## Company name on `clean_text` (#86 remainder): 2026-10-30

- Branch `cursor/ui-company-name-clean-text-86`, rebased onto
  `origin/master` `67974c5`. Pull request #106 is in review.
  Refs #86. Not merged. #86 stays open. See the #86 bullet under
  Open work elsewhere.
- #108 merged on `67974c5`: the watchlist page loads companies and
  prices in a batch, and the ticker-index `SAWarning` is a scoped
  ignore in the autogenerate tests. Details are in the section
  below.
- Completed: `normalized_company_name` in `app/ui/form_fields.py`
  calls `app.validation.text.clean_text` with `COMPANY_NAME_MAX`
  (255). The form maps `exc.code` to catalog keys that already
  exist in Polish and English: `blank` is `error.required`,
  `too_long` is `error.too_long`, and `control_char`, `bidi`, and
  `surrogate` are `error.invalid`. No template or CSS changes. No
  new catalog key. The HTTP API still reports a too-long company
  name as Pydantic `string_too_long`.
- Decision: a name made only of combining marks (Mn U+0301, Mc
  U+093E, Me U+20DD) is blank. That check is step 3 of `clean_text`,
  after surrogate, bidi, and control, and before the length check.
  The form and the API both reject it. A letter keeps its mark.
  Watchlist labels and note or thesis text share the checker, so a
  marks-only label is stored as null and a marks-only note is blank.
- Not in this slice: `instrument_type_for_payload` still rejects
  ASCII controls (code points below 32, and DEL) on its own.
  Exchange, country, sector, industry, website, and description are
  not on `clean_text`.
- QA on `33a70a5`: behaviour items 1-5 passed. One Medium: the
  length tests multiplied `COMPANY_NAME_MAX`, so a wrong constant
  still passed. Fixed on this branch with literal tests: `'a' * 255`
  is stored (form 303, API 201) and `'a' * 256` is form
  `error.too_long` in Polish and English and API 422
  `string_too_long` with `ctx.max_length == 255`. Mutating the
  constant to 254 and to 256 made both new tests fail; the
  mutation was not committed. Readable `ids=` were added. A
  surrogate still cannot be rendered: the HTML response cannot
  encode U+D800, so that case locks the catalog sentence for
  `error.invalid` instead of a form POST.
- Tests: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset. CI
  command on local SQLite 3.45.1 after the rebase and the review
  lows: 1921 passed, 225 deselected, coverage 96.47%. The known
  `0006` float failures show up on SQLite 3.54; this machine is
  3.45.1, so those two tests passed. No local PostgreSQL.
  GitHub Actions runs both jobs. No live market-data calls.
  black, isort, and flake8 passed on the changed Python files.
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Review lows, tests only: a stored name with U+200F still
  renders on the detail page and the edit form, and the edit
  POST is 422 `error.invalid`. A 422 whose name is
  `<script>x</script>` plus U+202E escapes the tag. No production
  behaviour change in that commit. The edit block for an
  already-stored bidi mark is the behaviour from the `clean_text`
  move, recorded above.
- Next action: GitHub Actions on the rebased head, SQLite and
  PostgreSQL, both green. Raul merges with "Rebase and merge".
  The agent does not merge. #106 stays in review. #108 is merged.

## Watchlist N+1 and ticker-index SAWarning (#108, merged)

- Merged in #108 at `67974c5`. Branch was
  `cursor/watchlist-nplus1-sawarnings`, from `3c40413`. Refs, no
  closing keyword (there is no issue).
- Completed: `GET /ui/watchlist` no longer runs one price query and
  one company query per row. `list_items(with_company=True)` uses
  `joinedload`. New `PriceBarRepository.recent_closes_for` loads
  default sources, the two newest closes, and the sparkline window
  in at most three queries for the whole list. `recent_closes` and
  `_default_source` are unchanged (PR #107 edits those). Rendered
  HTML is unchanged. Templates and static files were not edited.
- Query counts on SQLite, every row with two closes: 1 row was 6
  statements and 10 rows were 51 (`5N+1`). Both are now 4 statements.
- SAWarning: CI on `3c40413` printed
  `Skipped unsupported reflection of expression-based index
  uq_companies_ticker` from
  `test_autogenerate_against_sqlite_notes_is_empty` and
  `test_autogenerate_against_sqlite_watchlist_is_empty`. Cause:
  those tests `create_all` (the expression index already exists),
  then revision 0006 batch-alters `price_bars` and reflects
  `companies` through the foreign key. SQLAlchemy 2.0.23 cannot
  reflect `upper(ticker)`. This is a scoped ignore, not a fix:
  `upgrade_head_over_create_all` ignores that one message and turns
  any other `SAWarning` into an error. `upgrade_head` on a
  `create_all` database still emits it. No Alembic revision.
  `-W error::DeprecationWarning` is unchanged.
- Decisions: batch method is new, not a rewrite of `recent_closes`.
  Company eager-load is opt-in so the watchlist API query stays a
  plain list. Default source is still latest `retrieved_at`, then
  the source name that sorts last in Python (`fake` beats
  `[IAC-DEMO-V2]`).
- QA Lows on #108, tests and docs only. A long series inserted
  out of date order must match `recent_closes`. Empty page is 1
  statement, a barless row is 2, a priced page is 4 on SQLite and
  5 on PostgreSQL (`SET TIME ZONE`). The warning wording is
  scoped ignore.
- Tests on that branch: no `.env`, `DATABASE_URL` unset. CI command
  on local SQLite 3.45.1 before the QA tests: 1880 passed, 222
  deselected, coverage 96.40%.

## Open work elsewhere

- #33: the notes and theses tables and repositories are on master
  (revision `0005`). The API and the `/ui` panel are on
  `feat/notes-theses-33` (above).
- #32: the watchlist backend is on master (revision `0004`).
  The `/ui` page from #96 is on master. The N+1 follow-up merged
  in #108.
- #8 and #10: the instrument Alembic baseline is still open,
  and `init_db` still uses `create_all`.
- #54: the real Yahoo adapter, and the case where a Yahoo HTTP
  failure looks like "no data", stay on #54. Post-demo work
  runs from #54 through #58.
- #26: instrument type and ISIN are on master. Master's
  work-state still records that the shipped `/ui` used
  lowercase `stock` and did not show `isin` before the later
  form work.
- #34: company and financial-metrics forms. ETF/ETC attribute
  forms stay on #28. A `source=manual` column and a synthetic
  marker that survives a description edit are still open there.
- Demo-v1 price profiles: `run_demo` loads demo-v2, and the
  manual `seed_demo` steps stay demo-v1 unless
  `--fixture demo-v2`. The fake collector still serves demo-v1
  price profiles. The `/ui` synthetic badge labels
  `[IAC-DEMO-V1]` as `demo-v1` and `[IAC-DEMO-V2]` as `demo-v2`
  (`demo_source_label` in `app/ui/view_models.py`).
- #99: named watchlists (several lists per company).
- #100: on-demand AI summary of recent moves in a watchlist row.
- #86 stays open. The `/ui` company name now uses `clean_text`
  (branch `cursor/ui-company-name-clean-text-86`). Still open:
  when the ticker and the ISIN are both duplicates, report both;
  `watchlist_stale_price_days` still has no `ge=1` check. Stripping
  Cf characters at the edges stays undone on purpose: a format
  character beside a letter is kept, including at an edge.
- #28: ETF/ETC attribute columns, fund attributes, and the
  attribute forms. Yahoo still does not implement
  `FundAttributes`.
- Local SQLite 3.54 casts a float to text with more digits than
  the SQLite in CI. Two `0006` boundary tests fail locally on
  `master` for that reason. Not tracked in an issue yet.
- #57, #58, and #65 are open post-demo issues. #57 is
  portfolio holdings (model, manual or CSV import, privacy).
  #58 is the market scanner and buy, sell, and opportunity
  signals. #65 is the AI Portfolio, after real portfolios and
  signals. None of them is on this branch.
- #27 is still open. PR #83 merged on 2026-10-21 and its body
  says Refs #27. Price-bar storage and the demo-v2 fixture
  landed in that pull request. ETF and ETC attribute columns
  stay on #28, which is still open, so #83 did not close #27.
- #95 is open. It lists follow-ups for #94: skipped bars, a
  duplicate `(date, source)` inside one batch, a lighter tie
  query, an optional cap on the log-once sets, and currency
  length on SQLite. #94 merged on 2026-10-22 (revision
  `0006`).
- Tooling: `.github/workflows/tests.yml` runs the two pytest
  jobs only. The workflow says neither job lints, so CI does
  not run black, isort, or flake8. `setup_database.py` fails
  flake8: unused `Session` (line 14) and unused `engine`
  (line 19), and E402 on lines 19 and 20 because those
  imports follow the `sys.path` change.
- Dependencies: `google-genai` is not pinned. It waits for
  the Gemini adapter (README and product requirements). PyPI
  `google-genai` 2.32.0, checked 2026-10-22, requires
  `websockets<17.0,>=13.0.0`. `requirements-dev.lock` pins
  `websockets==17.2`, so installing `google-genai` would
  downgrade `websockets`. `jinja2` is already pinned at
  3.1.6.
