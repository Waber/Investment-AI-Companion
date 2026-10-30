# Current Work State

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
  those and the price-bar follow-ups. Rendered HTML is unchanged.
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
    `_remember_skip`.
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
  integration suite: 232 passed, 1893 deselected. No live
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
- #33: notes and theses backend is on master (revision `0005`).
  The `/ui` forms and HTTP API are PR #104 (`feat/notes-theses-33`).
  This branch did not edit that work.
- #32: the watchlist backend, the `/ui` page, and the batch read
  (#108) are on master. #96 merged as PR #101 on 2026-10-28.
  Named lists are #99. The on-demand summary is #100.
- #98 review nits still open (see the section above): truncated
  422 keys in `app/core/validation.py`, copying `exc.errors()`
  before editing, docs for surrogate keys and the watchlist
  `too_long` gate, and a 201 test for an extra surrogate key.
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
