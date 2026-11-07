# Current Work State

## Security-audit skill (#125): 2026-11-07

- Branch `chore/security-audit-skill`. Published head at the start
  of this session was `ee12345af9f59f183570f6dbf5ad81d934319246`.
  This session adds documentation on top of that commit. It does
  not rebase, amend, merge master, or force-push. Owner approval
  to rewrite published history was not given.
- Live `origin/master`, fetched 2026-11-07, is
  `c051ced1d909278cb2c0aee897e9c72e1e909ef1`. GitHub shows #107
  merged (`25af8c20786724caf2dc86503496b15e792584ce`, 2026-11-07)
  and #104 merged (`c051ced`, 2026-11-07). #125 is open. At
  `ee12345` GitHub reported `mergeable: CONFLICTING`. A local
  `git merge-tree` against that master conflicted in
  `docs/development-journal.md`. After this documentation update,
  `docs/work-state.md` conflicts as well, because master has its
  own copy of this file. `AGENTS.md` does not.
- Completed: confirmed the skills.sh Snyk page label (Warn,
  MEDIUM, one issue, W011, third-party content exposure /
  indirect prompt injection, evidence score text 0.30). Confirmed
  the 20 installed skill files match upstream
  `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8` byte for byte.
  Production validator self-tests: 34 pass and 31 pass on Node
  v22.23.4. `AGENTS.md` now keeps this skill in guidance mode
  unless the owner explicitly requests a full audit or pen-test,
  requires a real usage reading before that audit, and explains
  the Windows `core.symlinks=false` checkout of
  `.claude/skills/security-audit`. Skill files and the lock hash
  were not changed.
- Not done: no pull-request comment was posted. The draft is
  held outside the repository, pending the owner's decision.
  The skills CLI hash was not recomputed. `npx skills` was not
  re-run. The full pytest suite was not run. No Windows checkout
  was executed; the symlink note follows Git's `core.symlinks`
  documentation and https://gitforwindows.org/symbolic-links.
- Residual risk, left as documentation: W011 names exposure to
  content the skill reads. That includes this repository's own
  files, not only a different tree. It is not a malware or CVE
  finding by itself. No code change was made to clear the label.
- Tests and unrun checks: validator self-tests above. The
  personal-path `git grep` exited 1 with no matches. That result
  is in the 2026-11-07 journal entry. No live market-data calls.
  No secrets read. The full pytest suite was not run.
- Active agents: none on this pull request. The security
  investigation supplied with the task was checked against the
  sources above and was not treated as proof. #124 was not
  edited.
- Account usage meter: not available in this session. The owner
  reported 36.3% at the start, gate 80%. That figure was not
  re-read from a meter. Work continued because the reported
  figure is under the gate. No percentage was invented.
- Blocker: the branch still conflicts with `origin/master`
  `c051ced`. Cleaning that up needs a rebase, which rewrites
  published history. Waiting for the owner. Code review approved
  the docs delta at `42d8dd7` only. Integration and merge are
  not approved.
- Next action: owner decides on the draft comment and on a
  rebase onto `c051ced`. After that rebase, keep master's
  journal and work-state entries and keep the 2026-11-07 #125
  notes. Then #124. The agent does not merge and does not post
  the comment.

## Notes and theses (#33): 2026-10-30, PR #104 in review

- Branch `feat/notes-theses-33`, rebased onto `origin/master`
  `25af8c2` (#107 is on master). Pull request #104 is open and
  in review. Not merged. The rebase conflicts were only in
  `docs/work-state.md` and `docs/development-journal.md`. Both
  sides stayed. Thesis labels and the N1/N2 panel fixes stayed.
  The head before the review fixes below was `43fb9c8`; both
  GitHub Actions jobs (SQLite and PostgreSQL) succeeded on it.
- Design: `docs/superpowers/specs/2026-10-28-notes-theses-design.md`.
  Plan: `docs/superpowers/plans/2026-10-28-notes-theses.md`, 10 tasks,
  run with subagent-driven development. The per-task ledger (rulings,
  deferred review findings, status) is the git-ignored
  `.superpowers/sdd/2026-10-28-notes-theses/progress.md`.
- Completed, each task reviewed: Tasks 1 to 9, and Task 10 in
  `d74ba7f` and `7c5f99b` (the rebase onto `da6579d` rewrote the
  earlier SHAs; `git log` has the current ones):
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
    `/ui/instruments/{id}`;
  - Task 8: add, edit, and delete notes in the panel;
  - Task 9: add, edit, close, reopen, and delete theses in the panel;
  - Task 10: the company delete warning names notes and theses, two
    persistence tests, the EN "Close thesis" label, the new-thesis
    "Anuluj" link lands on the panel without JavaScript, the docs, and
    the Chrome check on the demo.
- The final whole-branch review (four lenses, 2026-10-30) said "With
  fixes": no Critical or Important finding, and five Minor fixes
  before the pull request. The fix wave made them in five commits
  (SHAs after the rebase onto `da6579d`):
  - F1 `0f332fc`: "Anuluj" for a note or thesis deleted in another
    tab now puts the focus on the panel heading, not on the page;
  - F5 `fb14390`: "Najwyżej 10 000 znaków." keeps a no-break space
    between 10 and 000;
  - F2 `ea850a8`: a test pins that a thesis update with the stored
    texts still moves `updated_at`;
  - F3 `7cf0f4e`: docstrings and `docs/api-demo.md` that contradicted
    the code;
  - F4 `f17bb4b`: this file and the journal.
- Code review on #104, fixed on this branch (frontend only):
  - M1 `0dc4bff`: the note add and the new-thesis post are not
    repeated after a failed HTMX request. A storage 500 swaps into
    `#research` only when it carries `HX-Research-Panel: 1`;
  - L4 `94e6c33`: each text-validation code has its own panel
    message;
  - nits `3e1976a`: `dir="auto"` on user text, the shared UI
    helpers are public, and the HTMX list keeps its catch-all.
- Incomplete: filing FU1 to FU7 (FU5 is done for the panel; the
  company name still uses `error.invalid`). GitHub Actions on
  this review-fix head follows the push.
- Tests: CI command on local SQLite 3.45.1 after the rebase onto
  `25af8c2`: 2060 passed, 252 deselected, coverage 97.00%. This
  SQLite is 3.45.1, so the two `0006` float boundary tests passed
  (they fail on SQLite 3.54). No local `demo/` directory, so the
  `run_demo` dotenv test passed. No local PostgreSQL. No live
  market-data calls. black, isort, and flake8 passed on the Python
  files this branch changes. Master's older API files still fail
  isort and flake8; they were not edited.
- Proposed follow-up issues, not filed yet. Filing publishes outside
  this repository, so it waits for the owner's approval:
  - FU1, required by the Task 8 ruling: stop SQLite from reusing
    deleted row ids, so a stale form cannot edit or delete a newer
    note, thesis or company (`AUTOINCREMENT` plus one migration, or a
    row token on forms that can go stale).
  - FU2, required by the Task 9 ruling: in `ui.js`, focus the clicked
    control before an HTMX request, so the id restore works after a
    mouse click in Safari and Firefox. Until then, after a mouse close
    or reopen in those browsers on macOS, the focus is expected to
    fall to the page (expected from those browsers' click-focus
    behaviour; not driven, only Chrome was).
  - FU3: serve `ui.css` and `ui.js` with `Cache-Control` or versioned
    file names, so a cached copy does not hide an update.
  - FU4: tighten the `alembic stamp` advice for old `create_all`
    databases: the `0002` and `0004` docstrings, the "before
    2026-10-21 19:35" sentence, and a database stamped `0008` without
    `closed_at`.
  - FU5: done for notes and theses (L4 above). The company name
    form still says "Ta wartość jest nieprawidłowa." for a control
    character, a bidi character, or a surrogate.
  - FU6: let Cmd, Ctrl or Shift-click on panel links open a new tab
    instead of swapping in place.
  - FU7: fail the SQLite CI job when node is missing
    (`REQUIRE_NODE=1`), instead of skipping `tests/test_ui_js.py`, and
    say so in the README.
- Stop reason: the #104 review fixes are on this branch. Filing
  the follow-ups still waits for the owner. The agent does not
  merge.
- Active agents: none. The Developer who was going to update the
  stale docs is paused; those doc fixes are in this section.
  Blockers: none. Account usage was not available in this session.
- Next action: GitHub Actions on the rebase onto `25af8c2`,
  SQLite and PostgreSQL. #104 stays in review. Do not merge.
  Do not file FU1 to FU7 until the owner asks. The pull request
  body is the owner's to update.

## Price-bar repository follow-ups (#95): 2026-10-30

- Branch `cursor/price-bar-followups-95-ce0a`, rebased onto
  `origin/master` `da6579d`. Pull request #107 to `master`.
  **Refs #95**. Item 1 is deferred, so #95 stays open. In review.
  Not merged. No Alembic revision; head stays `0007`. `app/ui`,
  `templates/`, and `static/` were not edited. PR #104 was not
  touched. #106 and #108 are merged.
- PR #108 is merged on that master. It added
  `PriceBarRepository.recent_closes_for`,
  `WatchlistRepository.list_items(with_company=True)`, and a
  scoped ignore of the `uq_companies_ticker` reflection
  SAWarning (`upgrade_head_over_create_all`). This branch keeps
  those and the price-bar follow-ups. `_pick_default` is the one
  tie rule for `_default_source` and `_default_sources_for`.
  The batch path is locked with a stand-in whose SQL order
  would pick `[IAC-DEMO-V2]`; `recent_closes_for` still
  returns `fake`. Rendered HTML is unchanged.
- Fixed:
  - Item 2. `upsert_many` keeps the last bar when one batch
    repeats `(date, source)`. Equal prices leave one row. Unequal
    prices leave the last bar. The returned list has one row per
    key (refresh `bar_count` counts keys). A later failure rolls
    the whole batch back, so a row that was already stored keeps
    its previous values.
  - Item 3. `_default_source` is one `GROUP BY source` plus
    Python `max` of the names at the newest `retrieved_at`. The
    second query that read every bar at that instant is gone.
    `fake` still beats `[IAC-DEMO-V2]`.
  - Item 4. The per-process skip logs are insertion-ordered dicts
    capped at 1024. The oldest id is dropped and may log once
    more. The repository and `app/api/prices.py` share
    `remember_skip`. The update is under one `threading.Lock`,
    so a full dict cannot make two threads pop the same oldest id.
  - Item 5. The repository rejects a currency that is not exactly
    three letters before flush, on SQLite and PostgreSQL.
    `ValueError`: `currency must be exactly three letters`. No new
    row. `usd` is stored as `USD`. `GBp` stays `GBp`.
- Deferred:
  - Item 1, skipped-bar visibility. GET still returns 200 and the
    shorter list. No count, no header, no response-shape change.
    Server phase #93.
  - #98 review nits, still open. They do not live in
    `app/validation/text.py`, so they stayed out of this pull
    request: (a) `app/core/validation.py` `_truncate_error_input`
    slices dict keys to 100 characters, and two keys that share
    that prefix collapse to one key in the 422 body; (b)
    `_limit_error_context` edits the dicts from `exc.errors()`
    in place instead of copying them; (c) `docs/api-demo.md`
    does not yet say that surrogate characters in dict keys are
    escaped, or that `WatchlistRepository.add` rejects a label
    longer than 80 with `too_long` when the HTTP model is
    bypassed; (d) no test that a valid body plus an extra
    surrogate key returns 201.
- Decisions are in the journal entry for this date. Last-wins is
  checked only on the winning bar: a discarded earlier copy with
  a bad currency is not an error when the last copy is valid.
  QA on `f4bf55b` did not approve the test locks. The behaviour
  stayed. The follow-up commit pins the literal cap 1024, refresh
  `bar_count` against a collector that repeats a day, and a
  Python-max tie that SQL would order the other way. `ZAc` is
  kept next to `GBp`. Currency samples are one pytest case each.
- Tests: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset. This
  machine's SQLite is 3.45.1, not 3.54, so the two known `0006`
  float-boundary failures did not appear. CI command after the
  QA fixes: 1893 passed, 232 deselected, coverage 96.42%. Two
  pre-existing SAWarnings on the autogenerate tests (expression
  index `uq_companies_ticker`). Local PostgreSQL 16.15,
  `REQUIRE_POSTGRES=1`, DSN
  `postgresql://postgres:postgres@127.0.0.1:5432/investment_test`,
  integration suite after the rebase and `_pick_default`:
  233 passed, 1899 deselected. SQLite CI command on this head:
  1899 passed, 233 deselected, coverage 96.46%. No live
  market-data calls. black, isort, and flake8 passed on
  the changed Python files. Mutation checks, each reverted:
  cap 1025 fails `assert 1025 == 1024`; cap 1023 fails
  `assert 1023 == 1024`; `bar_count=len(payload)` fails
  `assert 2 == 1`; `_default_source` without Python `max`
  returns `[IAC-DEMO-V2]` instead of `fake`.
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Next action: both GitHub Actions jobs green on this head, then
  QA. Raul merges with "Rebase and merge". Do not merge from
  the agent. #95 stays open until skipped-bar visibility (#93)
  is done.

## Company name on `clean_text` (#86 remainder, #106 merged)

- Merged in #106 at `da6579d`. Branch was
  `cursor/ui-company-name-clean-text-86`, rebased onto
  `67974c5`. Refs #86. #86 stays open for the items under
  Open work elsewhere.
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
- Not in that slice: `instrument_type_for_payload` still rejects
  ASCII controls (code points below 32, and DEL) on its own.
  Exchange, country, sector, industry, website, and description are
  not on `clean_text`.
- QA on `33a70a5`: behaviour items 1-5 passed. One Medium: the
  length tests multiplied `COMPANY_NAME_MAX`, so a wrong constant
  still passed. Fixed with literal tests: `'a' * 255` is stored
  (form 303, API 201) and `'a' * 256` is form `error.too_long` in
  Polish and English and API 422 `string_too_long` with
  `ctx.max_length == 255`. Review lows, tests only: a stored name
  with U+200F still renders on the detail page and the edit form,
  and the edit POST is 422 `error.invalid`. A 422 whose name is
  `<script>x</script>` plus U+202E escapes the tag.

## Watchlist N+1 and ticker-index SAWarning (#108, merged)

- Merged in #108 at `67974c5`. Branch was
  `cursor/watchlist-nplus1-sawarnings`, from `3c40413`. Refs, no
  closing keyword (there is no issue).
- Completed: `GET /ui/watchlist` no longer runs one price query and
  one company query per row. `list_items(with_company=True)` uses
  `joinedload`. New `PriceBarRepository.recent_closes_for` loads
  default sources, the two newest closes, and the sparkline window
  in at most three queries for the whole list. Rendered HTML is
  unchanged. Templates and static files were not edited.
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

## Open work elsewhere

- #106 is merged. The `/ui` company name uses `clean_text`.
  #86 stays open: when the ticker and the ISIN are both
  duplicates, report both; `watchlist_stale_price_days` still
  has no `ge=1` check. Stripping Cf characters at the edges stays
  undone on purpose: a format character beside a letter is kept,
  including at an edge.
- #108 is merged. `recent_closes_for` and
  `list_items(with_company=True)` are on master. The
  `uq_companies_ticker` reflection warning is a scoped ignore,
  not an open fix.
- #107 is in review (this branch). Refs #95. Item 1 stays deferred.
- #33: the notes and theses tables and repositories are on master
  (revision `0005`). The API and the `/ui` panel are on
  `feat/notes-theses-33` (above). Pull request #104.
- #32: the watchlist backend, the `/ui` page, and the batch read
  (#108) are on master. #96 merged as PR #101 on 2026-10-28.
  Named lists are #99. The on-demand summary is #100.
- #98 review nits still open (see the section above): truncated
  422 keys in `app/core/validation.py`, copying `exc.errors()`
  before editing, docs for surrogate keys and the watchlist
  `too_long` gate, and a 201 test for an extra surrogate key.
- #102: the Code Reviewer agent, priority high, is next after #33.
- #103: comments on buy and sell transactions, deferred until #57
  brings transactions.
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
- #95 stays open. Items 2–5 are this branch. Item 1
  (skipped-bar visibility) waits for the server phase (#93).
  The GET body stays a list of bars. #94 merged on 2026-10-22
  (revision `0006`).
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
