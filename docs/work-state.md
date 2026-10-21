# Current Work State

## Code review and rebase onto price bars (PR #87): 2026-10-21

- Branch `cursor/ticker-unique-and-alembic-0e9d`, rebased onto
  `origin/master` `192c521`. Not merged. Alembic head is `0003`.
  `0003_companies_ticker_unique.py` has `down_revision` `0002`
  (`price_bars`). Pull request #90 may take `0003` first. This
  branch stays on `0003` until then, then it is re-chained to the
  next free number.
- Completed: database URL errors exit 1 with a fixed line and do
  not echo the URL. `DATABASE_URL` is the preferred input.
  `normalize_name` rejects category `Cc` anywhere after strip.
  The preflight trims space, tab, CR, and LF on SQLite and
  PostgreSQL. The ticker index is `op.create_index`. A SQLite
  upgrade with foreign keys on keeps `price_bars` and
  `financial_metrics` rows. `CompanyDB` keeps `price_bars` and
  `uq_companies_ticker`. `app/ui/forms.py` was not edited.
- Incomplete: #8's instrument baseline and the rest of #86.
  Re-chaining waits until another revision takes `0003`.
- Tests: no `.env`. SQLite CI command: 1556 passed, 139
  deselected, coverage 96.10%. PostgreSQL `-m integration` with
  `REQUIRE_POSTGRES=1`: 139 passed, 1556 deselected. PostgreSQL
  16.15. GitHub Actions for this head is not in this file.
- Active agents: none. Blockers: none for this head. Account
  usage was not available in this session.
- Next action: push with `--force-with-lease` and confirm both
  GitHub Actions jobs on the new head. The owner reviews pull
  request #87. Agents do not merge.

## QA follow-up on the ticker preflight (PR #87): 2026-10-21

- Branch `cursor/ticker-unique-and-alembic-0e9d`, rebased onto
  `origin/master` `192c521`. The ticker revision is `0003` with
  `down_revision` `0002` (`price_bars`). Pull request #90 may
  take `0003` first. This branch is re-chained to the next free
  number after whatever merges ahead of it.
- Completed: the migration and `scripts.check_duplicate_tickers`
  group by `UPPER(TRIM(ticker))`. `aapl` and `AAPL ` fail the
  preflight. The message quotes the stored rows. Nothing is
  rewritten. `OperationalError` prints one line to stderr and
  exits 1. `ScriptDirectory.get_heads()` is asserted to have
  length 1. SQLite and PostgreSQL both cover the collision.
- Incomplete: #8's instrument baseline and the rest of #86, as
  in the section below. Pull request #90 may take revision
  `0003`; re-chain this branch after that.
- Tests: no `.env`. The counts for the rebased head are in the
  section above once that run is recorded.
- Active agents: none. Blockers: none until another pull request
  takes revision `0003`. Account usage was not available in this
  session.
- Next action: see the section above. Agents do not merge.

## Ticker uniqueness, shared names, Alembic (#79, #8, #86): 2026-10-21

- Branch `cursor/ticker-unique-and-alembic-0e9d`, from
  `origin/master` `6d45f01`. Not merged. The pull request says
  Closes #79, Refs #8, and Refs #86.
- Completed: `normalize_name` rejects a stripped name with no
  character outside whitespace and Unicode category C*. Create
  and update allow the same name on a different ticker. Revision
  `0003` checks for duplicate tickers, then adds unique index
  `uq_companies_ticker`. The model matches. Autogenerate is empty.
  Upgrade, downgrade, and upgrade again were run on SQLite and
  PostgreSQL. A supplied Alembic connection does not read
  `settings.DATABASE_URL`. Autogenerate imports `UTCDateTime`.
  README and `docs/api-demo.md` spell out why columns must not be
  added by hand. Migration tests call
  `require_company_instrument_columns` after `upgrade_head`.
  `templates/`, `static/`, and `app/ui/` were not edited. `/ui`
  now saves a shared name because it uses the repository.
- Incomplete: #8's `0001_baseline.py` for instruments, prices, and
  ETF/ETC attributes. Those tables are not on master. `init_db`
  still uses `create_all` (#10). #86's bidi ban, combining-mark
  ban, and moving the form helper onto `normalize_name` are not
  in this pull request. Money columns stay `Float`.
- Tests: no `.env`. SQLite CI command on this code: 1481 passed,
  127 deselected, coverage 95.96%. PostgreSQL `-m integration`
  with `REQUIRE_POSTGRES=1`: 127 passed, 1481 deselected.
  PostgreSQL 16.15. Earlier commits on this branch also passed
  both locally (1465/124 and 1467/124). GitHub Actions is
  recorded on the pull request.
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Next action: the owner reviews the pull request and merges with
  "Rebase and merge". Agents do not merge.

## Code review round 1 on price bars (PR #83): 2026-10-21

- Branch `cursor/pricebar-demo-v2-203d`, parent `e346725`.
  [PR #83](https://github.com/Waber/Investment-AI-Companion/pull/83)
  says Refs #27. Not merged. The issue stays open.
- Completed: `volume` is BIGINT in `PriceBarDB` and Alembic
  `0002`, and the write model rejects a volume above `2**63 - 1`.
  PostgreSQL stores 3,000,000,000. `GET /prices` without `source`
  returns one series: latest `retrieved_at`, then the source name
  that sorts last. `source` selects the other series. The seeder
  asks for `[IAC-DEMO-V2]`. An `IntegrityError` that leaves no
  inserted row is "Price bar could not be stored", raised outside
  the handler. A collector `ValidationError` is HTTP 502
  "Data provider error" and does not echo the value. Company
  delete uses `ON DELETE CASCADE` and `passive_deletes=True`.
  `ix_price_bars_id` and `ix_price_bars_instrument_id` are not
  created. The migrated table matches the model on SQLite and
  PostgreSQL. The fixture test asserts 1777 bars. The journal
  records the green run for `e346725`
  ([run 39563741560](https://github.com/Waber/Investment-AI-Companion/actions/runs/39563741560)).
- Incomplete: the `/ui` synthetic badge still matches only
  `[IAC-DEMO-V1]`. `templates/`, `static/`, and `app/ui/` were
  not edited. ETF/ETC attributes stay on #28. Float prices stay.
  Code Reviewer approval of #27 is still open.
- Tests: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset. SQLite
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1510 passed, 134 deselected, coverage 96.30%. PostgreSQL
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`
  with `REQUIRE_POSTGRES=1`: 134 passed, 1510 deselected.
  Scoped black, isort, and flake8 passed. No live market-data
  calls. This commit is the one push for the review. There will
  be no later commit whose only job is to record Actions.
- Active agents: none. Blockers: none for this pull request.
  Account usage was not available in this session.
- Next action: the owner reviews PR #83 again and merges it with
  "Rebase and merge" when the review is accepted. Agents do not
  merge. The Frontend Developer still owns the `/ui` badge.
  ETF and ETC attributes stay on #28.

## QA round 1 on price bars (PR #83): 2026-10-21

- Branch `cursor/pricebar-demo-v2-203d`. Code head `03952d9`.
  [PR #83](https://github.com/Waber/Investment-AI-Companion/pull/83)
  says Refs #27. Not merged. The issue stays open.
- Completed on top of `93c676c`: `PriceBarCreate` checks the
  candle when values are present (high at least the open and the
  close, low at most the open and the close, high at least the
  low, volume at least zero). The same six named checks are on
  `PriceBarDB` and in Alembic `0002`. A null price still stores.
  A flat bar and volume zero still store. Parametrized API tests
  expect 422 for each violation. Parametrized migration tests
  expect the named check to reject the row, on SQLite and on
  PostgreSQL, and downgrade still drops the table. The
  duplicate-bar `ValueError` is raised after the handler;
  `__context__` is `None`. The product-requirements PriceBar row
  says the demo fixture is weekly (Mondays). The journal's
  PostgreSQL command matches CI and has no `--cov-fail-under`.
- Incomplete: the `/ui` synthetic badge (M2) still matches only
  `[IAC-DEMO-V1]`. `templates/`, `static/`, and `app/ui/` were
  not edited. ETF/ETC attributes stay on #28. Float prices stay.
  Code Reviewer approval of #27 is still open.
- Tests: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset. SQLite
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1503 passed, 131 deselected, coverage 96.30%. PostgreSQL
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`
  with `REQUIRE_POSTGRES=1`: 131 passed, 1503 deselected.
  Scoped black, isort, and flake8 passed. No live market-data
  calls. GitHub Actions on `03952d9` succeeded
  ([run 39563380255](https://github.com/Waber/Investment-AI-Companion/actions/runs/39563380255)):
  SQLite job 119099695642 (1503 passed, 131 deselected, coverage
  96.30%) and PostgreSQL job 119099695294 (131 passed, 1503
  deselected).
- Active agents: none. Blockers: none for this pull request.
  Account usage was not available in this session.
- Next action: the owner reviews PR #83 and merges it with
  "Rebase and merge". Agents do not merge. The Frontend
  Developer still owns the `/ui` badge for `[IAC-DEMO-V2]`.
  ETF and ETC attributes stay on #28.


## Price bars and demo-v2 (#27): 2026-10-21

- Branch `cursor/pricebar-demo-v2-203d`, based on `origin/master`
  `6d45f01`. Head `533e2bd`.
  [PR #83](https://github.com/Waber/Investment-AI-Companion/pull/83)
  says Refs #27. Not merged. The issue stays open.
- Completed: `price_bars` table (Alembic `0002`), `PriceBar`
  models, repository range query and upsert, `GET` and `POST`
  `/api/v1/instruments/{id}/prices`, and `POST .../prices/refresh`.
  `fixtures/demo-v2.json` (10 companies, 20 metrics, 1777 weekly
  bars). `seed_demo --fixture demo-v2` and `scripts/run_demo.py`
  load it. Every seeded company description and every fixture
  price source is `[IAC-DEMO-V2]`. The fixture test checks a
  missing series (`DEMO_PL_EMPTY`), a stale series
  (`DEMO_JP_STABLE`), and mixed currencies. Refreshing twice from
  `FakeCollector` does not insert a second bar for the same
  instrument, date, and source. `docs/demo-data.md` and
  `docs/RUN_DEMO.md` describe the split: `run_demo` is demo-v2,
  and the manual `seed_demo` steps stay demo-v1 unless
  `--fixture demo-v2`.
- Incomplete, and not in this change: ETF/ETC attribute columns
  (#28). The `/ui` synthetic badge still matches only
  `[IAC-DEMO-V1]` (`app/ui/view_models.py`). That file was not
  edited. The Frontend Developer owns `templates/`, `static/`,
  and `app/ui/`. Code Reviewer approval of #27 is still open.
  The fake collector still serves demo-v1 price profiles.
  `scripts/smoke_demo.py` was not changed. It is a generic CRUD
  smoke. The in-process `run_demo` smoke covers demo-v2 prices.
- Tests: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset. SQLite
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1491 passed, 124 deselected, coverage 96.26%. PostgreSQL
  with `REQUIRE_POSTGRES=1`: 124 passed, 1491 deselected.
  Scoped black, isort, and flake8 passed. No live market-data
  calls. GitHub Actions on `533e2bd` succeeded
  ([run 39560060518](https://github.com/Waber/Investment-AI-Companion/actions/runs/39560060518)):
  SQLite job 119088883697 (1491 passed, 124 deselected, coverage
  96.26%) and PostgreSQL job 119088883999 (124 passed, 1491
  deselected).
- Active agents: none. Blockers: none for this pull request.
  Account usage was not available in this session.
- Next action: the owner reviews PR #83 and merges it with
  "Rebase and merge". Agents do not merge. The Frontend
  Developer still owns the `/ui` badge for `[IAC-DEMO-V2]`.
  ETF and ETC attributes stay on #28.

## Instrument type on the company forms (#34, part): 2026-10-21

- Branch `cursor/ui-instrument-type-select`, based on
  `origin/master` `a21d912`. PR #87 has not merged, so the
  rebase had no doc conflict. Not merged. Refs #34. Does
  not close the issue.
  [PR #89](https://github.com/Waber/Investment-AI-Companion/pull/89).
- Completed: an instrument-type select on the company create
  and edit forms. Options are the existing `InstrumentType`
  values. Labels are PL/EN catalog strings, Polish by
  default. Edit preselects the stored type. An unknown value
  is HTML 422 on that field with `aria-invalid`. A blank
  post uses the create default `STOCK` and leaves an edited
  row's type unchanged. `to_instrument` reads
  `CompanyDB.instrument_type` and maps `STOCK`/`ETF`/`ETC`
  to `stock`/`etf`/`etc`. The list and the detail page show
  that label. A cross-origin create that posts a type is
  still HTML 403. QA on `ce730e8`: a failed edit that omits
  the type puts the stored type back into the re-rendered
  values, so an ETF does not become STOCK when the ticker
  is fixed. A control character is rejected before `strip`
  (`ETF\n` is 422 and inserts nothing). `etf` and ` ETF `
  store ETF. Spaces are omitted. The unreachable missing-data
  branch for the type was removed from the detail page and
  the list. Models, schema, migrations, repositories,
  services, collectors, scoring, and AI adapters were not
  changed.
- Incomplete, and not part of this pull request: ETF/ETC
  attribute forms (#28), a `source=manual` column, a
  synthetic marker that survives a description edit, and
  cascades past financial metrics. Open PR #83 (price bars)
  is not a dependency of this select.
- Tests: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1500 passed, 124 deselected, coverage 96.07%. Scoped
  black, isort, and flake8 passed. PostgreSQL was not run
  locally. The two bug tests failed before the fix.
- Active agents: none. Blockers: none for this pull request.
  Account usage was not readable as a percentage in this
  session.
- Next action: PR #89 carries the QA commit. Wait for both
  GitHub Actions jobs, then the owner reviews. Agents do
  not merge.

## Synthetic badge source token: 2026-10-21

- Branch `cursor/ui-demo-badge-prefix-dc6c`, based on
  `origin/master` `6d45f01`.
  [PR #84](https://github.com/Waber/Investment-AI-Companion/pull/84)
  is the same pull request. QA asked for this low fix before
  code review. Independent of
  [PR #83](https://github.com/Waber/Investment-AI-Companion/pull/83).
  Either pull request can merge first. Not merged.
- Completed: the badge check is unchanged. The source is the
  token between `[IAC-DEMO-` and the next `]`, lowercased, when
  that token is 1 to 16 ASCII letters or digits.
  `[IAC-DEMO-V1]` is `demo-v1`, V2 is `demo-v2`, and V3 is
  `demo-v3`. A malformed token falls back to `demo` and still
  shows the badge. Typing `[IAC-DEMO-` into a description shows
  the badge. That is a misleading label, not a bypass of the
  seeder, and it is acceptable for the local demo. The note is
  in `docs/demo-data.md`. Models and fixtures were not changed.
- Incomplete: none for this pull request. PostgreSQL was not
  run locally.
- Tests: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1468 passed, 124 deselected, coverage 96.07%. Scoped
  black, isort, and flake8 passed on the touched Python.
  GitHub Actions
  [run 39565019024](https://github.com/Waber/Investment-AI-Companion/actions/runs/39565019024)
  on `c85f287` succeeded. SQLite job `119105110715`: 1468
  passed, 124 deselected, coverage 96.07%. PostgreSQL job
  `119105110896`: 124 passed, 1468 deselected.
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Next action: the owner sends PR #84 to the Code Reviewer.
  Agents do not merge.

## Duplicate codes and company-name alignment (#80, remainder): 2026-10-21

- Base: `origin/master` `6d45f01` is the merge of
  [PR #81](https://github.com/Waber/Investment-AI-Companion/pull/81)
  (Refs #80), merged 2026-10-21.
  [PR #75](https://github.com/Waber/Investment-AI-Companion/pull/75)
  is merged as `f7e90bf`.
  [PR #78](https://github.com/Waber/Investment-AI-Companion/pull/78)
  is merged as `d772409`. The work-state section below is the
  text #81 put on master. It still says PR #81 is not merged.
  That sentence was already stale when `6d45f01` landed.
- Branch `cursor/ui-duplicate-codes-name-align-fec9`.
  [PR #82](https://github.com/Waber/Investment-AI-Companion/pull/82)
  says Refs #80. Not merged. This docs commit marks it ready
  for review. GitHub Actions on this head is not recorded yet.
- Completed: company create and edit map `DuplicateTickerError.code`
  (`duplicate_ticker`) and `DuplicateIsinError.code`
  (`duplicate_isin`) to the localized field sentences. The branch
  is the class or `.code`, never the message text. The ticker row
  lookup and the TODO in `_company_save_failed` are gone. A
  duplicate name is still a plain `ValueError` with no code, so
  that case still looks up another row. A name the form accepts
  is exactly what `normalize_name` returns. The form still rejects
  a bidi control, any Cc character left after ``normalize_name``
  (including NUL or DEL at either end), and a name made only of
  invisible characters or marks. The create and edit forms
  include ISIN. A blank ISIN is null. The detail page shows that
  ISIN after the ticker, with the localized label, and the same
  missing-data sentence as the other fields when it is null.
  A duplicate of both ticker and ISIN marks only the ticker.
  Invisible Cf characters at the edges stay for a follow-up.
  Instrument type is not on the form. Models, schema,
  migrations, repositories, and services were not changed.
  `Secure` on the language cookie stays deferred
  (#56).
- Tests: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset. CI
  command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1480 passed, 124 deselected, coverage 96.06%. Scoped black,
  isort, and flake8 passed. PostgreSQL was not run locally (no
  `TEST_POSTGRES_DSN`). Browser on `127.0.0.1:8000`, fake
  collector, throwaway SQLite: Hindi name stored; Polish ticker
  and ISIN field errors; English ISIN error and English ticker
  error on edit; Persian ZWNJ stored as U+200C.
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Next action: both GitHub Actions jobs on this docs head, then
  the owner reviews PR #82 and merges with "Rebase and merge".
  Agents do not merge. #80 stays open until QA, Security, and
  Code Review approve, and until the HTTPS cookie in #56.

## UI forms follow-up (#80, part): 2026-10-20

- Branch `cursor/ui-issue-80-forms-origin-5105`, rebased onto
  `origin/master` `f7e90bf` (#75 and #78).
  [PR #81](https://github.com/Waber/Investment-AI-Companion/pull/81)
  says Refs #80. Not merged.
- Completed: one form-layer helper, `normalized_company_name`, used
  by company create and edit. It strips whitespace, Cf, and Cc from
  both ends. Empty, whitespace-only, Cf-only, and other invisible
  names are a localized 422. A name made only of marks is 422, and
  every M* category counts (Mn, Mc, and Me). A letter with a mark
  is kept. A NUL or other control anywhere inside the name is 422.
  A bidi override or isolate (U+202A–U+202E, U+2066–U+2069)
  anywhere, including at an end, is 422. A zero-width mark between
  two letters is kept. Code review on PR #81: `safe_next` unquotes
  the path repeatedly, then rejects a `.` or `..` segment, so
  `/ui/./language/pl` and `/ui/%2e/language/pl` return `/ui`. The
  PL and EN controls are same-origin forms with a hidden `next`.
  `POST /ui/language/{code}` sets the cookie and is covered by
  `require_same_origin`. `GET /ui/language/{code}` does not set
  the cookie: a known code redirects to `safe_next`, so an old
  bookmark is not a 403, and an unknown code stays HTML 404.
  An HTMX filter sends the new list URL out of band into the
  hidden `next` inputs. A page rendered from a POST names the
  GET form (`/ui/companies/new`, `.../metrics/new`, or the same
  edit/delete path). Switching language loads that GET, so
  unsaved form input is dropped. Other GETs are still not
  checked. `Secure` on the language
  cookie is deferred until HTTPS (#56). Models, schema,
  migrations, repositories, and the API were not changed.
- Incomplete, and not part of this pull request: map
  `duplicate_ticker` and `duplicate_isin` from `error.code`.
  Those classes are on master in
  `app.repositories.company_errors`. The form still decides a
  duplicate by a row lookup. TODO in
  `app/ui/forms.py` `_company_save_failed`. Aligning
  `normalized_company_name` with `normalize_name` is the same
  separate pull request. That model helper strips whitespace
  and rejects a Cf-only name. It keeps a format character
  beside a letter.
- Tests: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset. CI
  command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1465 passed, 124 deselected, coverage 96.05% on the
  rebased tip. Each rebased code commit passed the same command
  (1459 through 1465 passed, coverage 95.96% to 96.05%). Scoped
  black, isort, and flake8 passed on this branch's Python.
  PostgreSQL was not run locally (no `TEST_POSTGRES_DSN`).
  GitHub Actions for the rebased head is not recorded yet.
- Active agents: none. Blockers: none for this pull request.
  The `error.code` mapping and the name-helper alignment are a
  separate pull request. Account usage was not available in
  this session.
- Next action: push with `--force-with-lease` and wait for both
  GitHub Actions jobs. The owner then reviews PR #81 and merges
  it with "Rebase and merge". Agents do not merge.

## Rebase onto master after PR #78: 2026-10-21

- Branch `cursor/instrument-type-isin-1db6`, rebased onto
  `origin/master` `d772409`.
  [PR #75](https://github.com/Waber/Investment-AI-Companion/pull/75)
  is approved. Not merged. The body says Closes #16 and Refs #26.
- Completed: `CompanyCreate` and `CompanyUpdate` keep
  `name` `min_length=1` and `max_length=255`, and `ticker`
  `max_length=TICKER_MAX_LENGTH` with `pattern=TICKER_PATTERN`.
  `normalize_name`, ISIN, `instrument_type`, and the `isascii`
  currency check remain. Journal and work-state keep both the
  collector entries and the instrument-type entries.
- Tests: every rebased commit passed SQLite and PostgreSQL
  locally (`REQUIRE_POSTGRES=1`). Tip before this note,
  `9d4c0e9`: SQLite 1458 passed, 124 deselected, coverage
  95.90%. PostgreSQL 124 passed, 1458 deselected.
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Next action: push with `--force-with-lease`, wait for both
  GitHub Actions jobs, then the owner merges PR #75 with
  "Rebase and merge". Agents do not merge.

## Code review round 1 on #75: 2026-10-20

- Branch `cursor/instrument-type-isin-1db6`, based on
  `origin/master` `9d26948`.
  [PR #75](https://github.com/Waber/Investment-AI-Companion/pull/75)
  is ready for review. The body says Closes #16 and Refs #26.
  Not merged. Code head `03d8d43`.
- Completed: startup fails when `companies` lacks
  `instrument_type` or `isin`, with the Alembic command in the
  message. README and `docs/api-demo.md` document upgrade versus
  stamp. Duplicate errors are raised after the integrity handler.
  A format-only name is rejected. The ISIN country prefix is
  documented as unchecked. `test_duplicate_ticker_create_returns_400`
  is a passing test in `tests/test_known_defects.py`.
- Tests: SQLite on `03d8d43`: 1416 passed, 124 deselected,
  coverage 96.13%. PostgreSQL: 124 passed, 1416 deselected.
  GitHub Actions
  [run 39485556256](https://github.com/Waber/Investment-AI-Companion/actions/runs/39485556256)
  succeeded. SQLite job `118844913556` and PostgreSQL job
  `118844913923`. Earlier commits in this round also succeeded:
  `6190e85` run
  [39484912819](https://github.com/Waber/Investment-AI-Companion/actions/runs/39484912819),
  `bdffb76` run
  [39485111338](https://github.com/Waber/Investment-AI-Companion/actions/runs/39485111338),
  `93771eb` run
  [39485323078](https://github.com/Waber/Investment-AI-Companion/actions/runs/39485323078).
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Next action: the owner reviews PR #75 and merges with
  "Rebase and merge". Agents do not merge. A named unique
  constraint on ticker alone remains a follow-up. The next
  rebase against PR #78 keeps `name` `min_length=1` and ticker
  `max_length`.

## Generic update error drops the SQL text: 2026-10-20

- Branch `cursor/instrument-type-isin-1db6`, based on
  `origin/master` `9d26948`.
  [PR #75](https://github.com/Waber/Investment-AI-Companion/pull/75)
  is a draft. The body says Closes #16 and Refs #26. Not merged.
- Completed: the generic update sentence is raised after the
  `IntegrityError` handler ends, with `from None`.
  `__context__` and `__cause__` are both `None`, so the SQL text
  is not chained. The same session can still update the row.
- Tests: SQLite CI command: 1411 passed, 123 deselected,
  coverage 96.15%. PostgreSQL `-m integration`: 123 passed,
  1411 deselected. GitHub Actions on this commit is not recorded
  in this file; the session report names the run.
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Next action: the owner reviews PR #75 and merges with
  "Rebase and merge". Agents do not merge. A named unique
  constraint on ticker alone remains a follow-up. The next
  rebase against PR #78 keeps `name` `min_length=1` and ticker
  `max_length`.

## Dotted ticker duplicate on #75: 2026-10-20

- Branch `cursor/instrument-type-isin-1db6`, rebased onto
  `origin/master` `9d26948`.
  [PR #75](https://github.com/Waber/Investment-AI-Companion/pull/75)
  is a draft. The body says Closes #16 and Refs #26. Not merged.
  Head `0188f53` is pushed.
- Completed: a second create of the same name and `BRK.B` is
  `DuplicateTickerError` and HTTP 400
  `{"detail": "A company with this ticker already exists", "code": "duplicate_ticker"}`
  on SQLite and PostgreSQL. The pre-insert lookup and the
  lookup after rollback both do that. The driver text is not
  read. `name` keeps `min_length=1`. PR #78's ticker
  `max_length` is not on this branch.
- Tests: SQLite CI command: 1411 passed, 123 deselected,
  coverage 96.15%. PostgreSQL `-m integration`: 123 passed,
  1411 deselected. GitHub Actions
  [run 39478793637](https://github.com/Waber/Investment-AI-Companion/actions/runs/39478793637)
  on `0188f53` succeeded. SQLite job `118821628878` and
  PostgreSQL job `118821628158` both concluded success.
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Next action: the owner reviews PR #75 and merges with
  "Rebase and merge". Agents do not merge. A named unique
  constraint on ticker alone remains a follow-up. The next
  rebase against PR #78 keeps `name` `min_length=1` and ticker
  `max_length`.

## QA round 1 on #75: 2026-10-20

- Branch `cursor/instrument-type-isin-1db6`, still based on
  `origin/master` `1f1678f`.
  [PR #75](https://github.com/Waber/Investment-AI-Companion/pull/75)
  is a draft. The body says Closes #16 and Refs #26. Not merged.
- Completed: a stored `instrument_type` outside `STOCK`/`ETF`/`ETC`
  is null on read, with the value's class name in the log. Create
  and update share one duplicate sentence. The 400 body is
  `{"detail": "<sentence>", "code": "duplicate_ticker"}` or
  `"duplicate_isin"`. The exceptions are
  `app.repositories.company_errors.DuplicateTickerError` and
  `DuplicateIsinError`, subclasses of `DuplicateCompanyError`
  (`ValueError`), each with a `code` attribute. A blank name after
  strip is 422. `docs/api-demo.md` mentions `instrument_type` and
  `isin`. Explicit `instrument_type: null` on update was already
  422 from security round 1.
- Tests: SQLite CI command on `79b6bc6`: 1346 passed, 122
  deselected, coverage 96.12%. PostgreSQL `-m integration`: 122
  passed, 1346 deselected. GitHub Actions, both jobs success:
  `77d54f8` run
  [39467269111](https://github.com/Waber/Investment-AI-Companion/actions/runs/39467269111),
  `61300c9` run
  [39467492356](https://github.com/Waber/Investment-AI-Companion/actions/runs/39467492356),
  `79b6bc6` run
  [39467716661](https://github.com/Waber/Investment-AI-Companion/actions/runs/39467716661)
  (SQLite job `118783362013`, PostgreSQL job `118783361167`).
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Next action: the owner reviews PR #75 and merges with
  "Rebase and merge". Agents do not merge. A named unique
  constraint on ticker alone remains a follow-up.

## Security round 1 on #75: 2026-10-20

- Branch `cursor/instrument-type-isin-1db6`, still based on
  `origin/master` `1f1678f`.
  [PR #75](https://github.com/Waber/Investment-AI-Companion/pull/75)
  remains a draft (Refs #26, Refs #16). Not merged.
- Completed: `update()` maps a duplicate ticker or ISIN to the
  same fixed sentences as `create`, and leaves every other
  integrity error on the generic sentence. The unused `as e` is
  gone. `uq_companies_isin` is a unique index in the model and in
  revision `0001`, and a test compares those two schemas. An
  explicit `instrument_type: null` on update is HTTP 422.
- Follow-up, not in this pull request: a named unique constraint
  on ticker alone. The column is already unique.
- Tests: local SQLite CI command on the security head: 1341
  passed, 122 deselected, coverage 96.05%. PostgreSQL
  `-m integration`: 122 passed, 1341 deselected, 0 xfailed.
  Each commit is green on both GitHub Actions jobs:
  `add849e` run
  [39464829393](https://github.com/Waber/Investment-AI-Companion/actions/runs/39464829393),
  `65bd0b2` run
  [39465048567](https://github.com/Waber/Investment-AI-Companion/actions/runs/39465048567),
  `a81e646` run
  [39465272356](https://github.com/Waber/Investment-AI-Companion/actions/runs/39465272356)
  (SQLite job `118774915084`, PostgreSQL job `118774915673`).
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Next action: the owner reviews PR #75. QA findings may follow.
  Agents do not merge.

## Instrument type and ISIN (#26) with duplicate ticker 400 (#16): 2026-10-20

- Branch `cursor/instrument-type-isin-1db6`, based on
  `origin/master` `1f1678f` (PR #74 merged).
  [PR #75](https://github.com/Waber/Investment-AI-Companion/pull/75)
  is a draft (Refs #26, Refs #16). Not merged.
- Completed: `instrument_type` (`STOCK` / `ETF` / `ETC`, default
  `STOCK`) and nullable unique `isin` on the company ORM,
  Pydantic write and read models, repository, and
  `/api/v1/companies/` responses. Existing response fields are
  unchanged. Revision `0001` adds both columns with
  `ALTER TABLE` (no batch rebuild). ISIN format and checksum are
  checked before insert. A duplicate ticker or ISIN is HTTP 400
  with a fixed sentence on SQLite and PostgreSQL. The driver
  text is not in the body. An integrity error that is not one of
  those two duplicates stays a generic 500.
- Incomplete: no rename to Instrument, no `/api/v1/instruments/`,
  no unique `(ticker, exchange)`, no list filters, metrics are
  not limited to stocks, and #8 (Alembic baseline) is still
  open. `app/ui/`, `templates/`, and `static/` were not edited.
  The shipped `/ui` still uses lowercase `stock` and catalog key
  `type.stock`, and it does not show `isin`.
- Tests: `.venv` Python 3.12, no `.env`, `DATABASE_URL` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1337 passed, 121 deselected, coverage 96.01%.
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`
  and `pytest -m integration` -> 121 passed, 1337 deselected,
  0 xfailed. GitHub Actions
  [run 39462037357](https://github.com/Waber/Investment-AI-Companion/actions/runs/39462037357)
  on `04aaeeb` succeeded. SQLite job `118763701814` and PostgreSQL
  job `118763702685` both concluded success (1337 passed / 96.01%
  coverage, and 121 passed). The earlier run
  [39460651955](https://github.com/Waber/Investment-AI-Companion/actions/runs/39460651955)
  succeeded on `07f7983` only (checksum helper).
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Next action: the owner reviews PR #75 and merges with
  "Rebase and merge". Agents do not merge.

## Collector hardening (#76): 2026-10-20

- Branch `cursor/collector-hardening-76-fe8d`, rebased onto
  `origin/master` `9d26948` (PR #77 is merged). Refs #76. Not
  merged. PR #70 stays closed. The old head `30b6f11` was not
  rebased; the behavior was ported onto the guard from PR #72.
  Issue #75 is still open, so ISIN, instrument type, and
  `normalize_name` were not added.
- QA round 1: `__context__` is followed only for a `ProviderError`
  wrapper (a `KeyError` on that link fails after one call). `raise X
  from Y` sets `__suppress_context__` even when Y is not `None`, so
  the kept wrapper test still retries. A retry shares the original
  deadline. The gitleaks allowlist is `condition = "AND"`.
- Security round 1: the in-flight permit is taken before the
  rate-limit wait, so a rejected call does not sleep or record a
  token. A second request for a key that is already being fetched
  fails at once instead of waiting. Yahoo `session.get` and
  `session.post` use the capped timeout. A ticker made only of dots
  is rejected.
- Code review round 1: an empty Yahoo result after a spent deadline
  is `TransientProviderError` (HTTP 502, not cached). The session
  cap marker follows a replaced session. A failed leader frees its
  key. De-dup is off when the TTL is 0 or the key cannot be hashed.
- Completed: one deadline for waits and retries, an in-flight
  semaphore taken before the rate-limit wait (default 4), a
  normalized cache key with the raw ticker still sent upstream,
  fail-fast for a duplicate in-flight key, retry when a
  transient error is on `__context__` only for a `ProviderError`
  wrapper, unexpected collector errors
  as HTTP 502 with the class name only, Yahoo ticker normalization
  before `yf.Ticker`, rejection of `.` and `..`, an explicit 10 s
  HTTP timeout that shrinks to the time left on the deadline,
  redaction of `yfinance` logs, `isascii()` before the currency
  check, and a gitleaks allowlist for the pytest placeholder on
  `tests/conftest.py` line 7. The 5 s wait cap, the autouse
  collector reset, and zero retries were already on master and
  were not duplicated. Templates, static files, and `app/ui/`
  were not edited.
- Incomplete: mapping yfinance errors to `TransientProviderError`
  stays in R1 #54. QA, Security, and Code Review of this branch
  are not done. The optional demo port race was not part of this
  change.
- Tests: no `.env`, `DATABASE_URL` unset, Python 3.12.3,
  `requirements-dev.lock`. CI command -> 1405 passed, 121
  deselected, coverage 95.62%. PostgreSQL was not run locally.
  GitHub Actions is the PostgreSQL run.
- Active agents: none. Blockers: none.
- Stop reason: code review round 1 is implemented locally, on top of
  the rebase onto `9d26948`. Account usage was not available in this
  session. The pull request stays ready for review. Agents do not
  merge.
- Next action: wait for both GitHub Actions jobs on this commit, add
  the code-review table to the pull request, and record the run id.
  After the owner rebases and merges, #26 together with #16.

## Company and financial-metrics forms (#34, part): 2026-10-20

- Branch `cursor/d5-company-metric-forms-cfb0`, based on
  `origin/master` `1f1678f`.
  [PR #77](https://github.com/Waber/Investment-AI-Companion/pull/77)
  says Refs #34 and leaves the issue open. Merged as `9d26948`.
- Completed: create, edit, and delete forms for a company, and the
  same three actions for that company's financial metrics, under
  `/ui`. New files: `app/ui/forms.py`, `app/ui/form_fields.py`,
  `app/ui/origin.py`, and the form templates. Small edits to the
  list and detail templates, `view_models.py` (`metrics_id`), the
  catalogs, `router.py`, `main.py`, and `static/ui.css`.
  `queries.py` was not edited. Models, schema, migrations, services,
  collectors, scoring, and the API were not edited.
- CSRF: no token. Unsafe `/ui` methods accept `Origin` (or `Referer`
  when `Origin` is missing) only when scheme, host, and port match
  this request. Otherwise HTML 403. `Referrer-Policy` is
  `same-origin` so Chrome sends a real `Origin` on a form POST.
  CSP `form-action 'self'` and `SameSite=lax` stay.
- Deferred: instrument type and ISIN (#26), ETF/ETC attribute forms
  (#28), `source=manual` and a synthetic-marker column (backend ask;
  none exists), cascades past financial metrics. Edit time uses the
  existing `updated_at`.
- QA on PR #77, not merged: a duplicate ticker is decided by a
  query for another row with that ticker (`==` on the normalized
  value), not by the repository sentence. A blank or whitespace-only
  name is 422 from the form layer. A test records that editing the
  description drops the `[IAC-DEMO-V1]` badge. A wrong method on
  `/ui` is an HTML 405 with the `/ui` security headers; API 405
  stays JSON.
- Review on PR #77, not merged: `python-multipart` floor is
  `>=0.0.32` (GHSA-5rvq-cxj2-64vf / CVE-2026-53539, fixed in
  0.0.30). Regenerating both locks left the pin and hashes at
  0.0.32. The form strips surrounding whitespace from the name and
  rejects a name with no visible character (nbsp, ideographic
  space, zero-width-only). The origin docstring says the check
  relies on `TrustedHostMiddleware`, so `ALLOWED_HOSTS` must stay
  loopback-only. Disclaimer-banner asserts added on this branch
  were removed. The shipped banner and the tests that predate
  this pull request stay.
- Tests: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset. CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1363 passed, 121 deselected, coverage 95.83% after
  removing the banner asserts this branch added. Scoped black,
  isort, and flake8 passed. `pip-audit` on both locks: no known
  vulnerabilities. `python-multipart` 0.0.32 with hashes.
  PostgreSQL was not run locally (no `TEST_POSTGRES_DSN`).
  GitHub Actions
  [run 39466655138](https://github.com/Waber/Investment-AI-Companion/actions/runs/39466655138)
  on `5602504` succeeded. SQLite job `118779699006` and PostgreSQL
  job `118779699318` both concluded success. The earlier run
  [39462413658](https://github.com/Waber/Investment-AI-Companion/actions/runs/39462413658)
  on `76367fc` also succeeded.
- Browser: create, inline validation, metrics create, edit, and
  delete confirmation exercised on `127.0.0.1:8000` in PL and EN
  before these QA notes. The notes are covered by pytest.
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Next action: the owner reviews the pull request and merges it with
  "Rebase and merge". Agents do not merge.

## Local venv and IDE interpreter setup: 2026-10-20

- Branch `chore/local-venv-setup`, based on `origin/master` `ba15c33`.
  [PR #74](https://github.com/Waber/Investment-AI-Companion/pull/74)
  (Refs #73), not merged.
- Completed: `.gitignore` excludes `.venv/` (README asked for `.venv`,
  but only `venv/` was ignored). README step 1 creates the venv with
  `python3.12`. `docs/ide-startup.md` explains the per-machine venv and
  selecting it in PyCharm, IntelliJ IDEA and Cursor, plus two
  troubleshooting entries. A persistent `.venv` exists in this checkout
  (Homebrew Python 3.12.15, installed by the owner on 2026-10-20).
  Issue [#73](https://github.com/Waber/Investment-AI-Companion/issues/73)
  records the move to Python 3.14 with the probe results.
- Tests: in `.venv`, no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command: 1300 passed, 121 deselected, coverage 95.80%.
  `-m integration`: 105 passed, 16 skipped (no PostgreSQL).
- Local fix: `~/.local/bin/python3.12` was a link into an old session
  scratchpad whose standard library had been cleaned up (`No module
  named 'encodings'`), and it came first on `PATH`. Removed on
  2026-10-20 at the owner's request; `python3.12` now resolves to
  `/opt/homebrew/bin/python3.12` (3.12.15). The link was outside the
  repository, so no repository file changed for it.
- Active agents: none. Blockers: none. Account usage was not available
  in this session.
- Next action: the owner reviews the pull request and merges it with
  "Rebase and merge". Then #26 together with #16.

## One-command offline demo (#25): 2026-10-15

- Branch `cursor/one-command-offline-demo-64f5`, rebased on
  2026-10-19 onto `origin/master` `922bdfe` (PR #72 merged).
  [PR #71](https://github.com/Waber/Investment-AI-Companion/pull/71)
  (Closes #25) merged on 2026-10-19; #25 is closed.
- Completed: `python -m scripts.run_demo` creates a fresh SQLite file
  at `demo/investment_demo.db`, seeds `demo-v1`, forces the fake
  collector and loopback hosts, always generates a fresh in-process
  `SECRET_KEY` (a shell or `.env` key is not reused), and starts
  uvicorn with `host="127.0.0.1"`. The URL printed is `/ui`.
  `--keep` reuses the file; `--reset` is the default. The guard
  refuses `postgresql://`, any path that is not that demo file, and
  a symlink at `demo/`, at the database file, or at a parent still
  inside the checkout. The port is checked before the file is
  deleted, so a busy port leaves the live database unchanged. A
  personal `DATABASE_URL` in `.env` or the shell is not used. Tests
  cover settings, the uvicorn host, the guard, the symlink and busy
  port, and an in-process smoke of `/docs`, the seeded API, and
  `/ui`. The network guard stayed on. Templates, static files,
  `app/data_collectors/`, and the currency code were not edited.
  The rebase onto PR #72 conflicted only at the top of this file
  and of the journal; both entries were kept, newest first.
- Incomplete: none for #25. #26 and #16 are not started.
- Tests: no `.env`, `DATABASE_URL` unset. The CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1175 passed, 121 deselected, total coverage 95.41%. Scoped
  black, isort, and flake8 passed on `scripts/run_demo.py` and
  `tests/test_run_demo.py`. PostgreSQL was not run locally.
  GitHub Actions
  [run 38705460114](https://github.com/Waber/Investment-AI-Companion/actions/runs/38705460114)
  on `4449053` succeeded. SQLite job `116323646312` and PostgreSQL
  job `116323646645` both concluded success. The earlier run
  [38703046058](https://github.com/Waber/Investment-AI-Companion/actions/runs/38703046058)
  on `8cde777` also succeeded.
  After the rebase (2026-10-19, fresh Python 3.12.15 venv from
  `requirements-dev.lock`, no `.env`, `DATABASE_URL` unset): the CI
  command gives 1300 passed, 121 deselected, coverage 95.80%;
  `-m integration` gives 105 passed, 16 skipped (no PostgreSQL).
- Active agents: none. Blockers: none.
- Next action: none for #25. Then #26 together with #16.

## Collector guard, part 2 of #24: 2026-10-14

- Branch `feature/collector-guard-24`, based on `origin/master`
  `107adf0`. Pushed on 2026-10-15 as
  [PR #72](https://github.com/Waber/Investment-AI-Companion/pull/72),
  merged on 2026-10-19 with "Rebase and merge" (head `922bdfe`).
  #24 is closed.
  [Spec](superpowers/specs/2026-10-13-collector-guard-design.md),
  [plan](superpowers/plans/2026-10-13-collector-guard.md).
- Completed: the guard (cache, rate limit, retries) in front of Yahoo,
  twelve `COLLECTOR_*` settings, currency in uppercase except `GBp`
  and `ZAc`, docs, task reviews, the final review and its fix wave.
  The re-review says ready to merge. CI command: 1259 passed, 121
  deselected, coverage 95.68%. `-m integration`: 105 passed, 16
  skipped. The PostgreSQL tests were not run locally (no
  `TEST_POSTGRES_DSN`).
- Incomplete: mapping yfinance errors to `TransientProviderError` (R1
  #54); storing `retrieved_at`; mypy typing of the guarded class; then
  #25. With this branch, every item of #24 is done (part 1 in PR #68).
- Overlapping pull requests:
  - PR #70 (Cursor Agent) implemented the same part 2 of #24. PR #72
    was chosen; PR #70 is closed without merging.
  - PR #69 (docs) merged on 2026-10-19 without conflicts.
- Active agents: none. Blockers: none.
- Next action: none for #24.

## Collector interface, part 1 of #24: 2026-10-12

- Branch `feature/collector-interface-24`, rebased on 2026-10-13 onto
  `114c93a` (PR #67).
  [PR #68](https://github.com/Waber/Investment-AI-Companion/pull/68)
  (Refs #24, part 1) merged on 2026-10-13 as merge commit `107adf0`.
  The merge closed #24 by mistake, so #24 was reopened for part 2
  ([comment](https://github.com/Waber/Investment-AI-Companion/issues/24#issuecomment-6146030726)).
  R1 hand-offs posted on
  [#54](https://github.com/Waber/Investment-AI-Companion/issues/54#issuecomment-6127198668).
- Completed: contracts, `FakeCollector`, Yahoo collector on the
  contracts, `DATA_COLLECTOR` setting with `get_collector()`, test
  network guard, docs, review fixes (final wave included). The final
  whole-branch review's re-review says ready to merge. After the
  rebase: full suite 1134 passed, coverage 95.24%; `-m integration`
  105 passed, 16 skipped; `-m ''` 1239 passed, 16 skipped. The
  PostgreSQL tests were not run locally (no `TEST_POSTGRES_DSN`; the
  16 skips). CI passed on PR #68, SQLite and PostgreSQL.
  [Plan](superpowers/plans/2026-10-12-collector-interface.md).
- Incomplete: part 2 of #24 (cache, rate limit, backoff, currency
  normalization), then #25. Provenance is not yet stored or returned.
  Under yfinance `hide_exceptions` a Yahoo HTTP failure can look like
  "no data" instead of a `ProviderError` (fix in R1 #54). Fund key
  metrics from the fake bars, and a fake P/E consistent with P/B and
  ROE, belong to I2 #27 and I3 #28. The guard cannot see libpq or
  libcurl.
- Active agents: none. Blockers: none. The session worktrees and the
  merged local branches are removed. The remote branches
  `feature/collector-interface-24` and `fix/pagination-bounds-19` and
  two local `backup/collector-24-*` refs are left for the owner to
  delete.
- Stop reason: part 1 is merged; part 2 is not started. Account usage
  was not available in this session.
- Next action: part 2 of #24 (the cache, rate limit and backoff
  wrapper, and currency normalization) on a new branch from
  `origin/master`, then #25.

## Pagination bounds (#19): 2026-10-12

- Branch `fix/pagination-bounds-19`, based on `25e7eba`.
  [PR #67](https://github.com/Waber/Investment-AI-Companion/pull/67)
  (Closes #19), merged on 2026-10-13 as merge commit `114c93a`; #19
  is closed. [Plan](superpowers/plans/2026-10-12-pagination-bounds.md).
- Completed: `0 <= skip <= 2**63 - 1` and `1 <= limit <= 1000` on
  the three list endpoints, shared in `app/api/pagination.py`. New
  tests in `tests/test_pagination_bounds.py`. Code Reviewer
  approved after one fix round, including the skip upper bound.
- Incomplete: none. The owner merged PR #67 with
  `MAX_PAGE_LIMIT = 1000`.
- Tests: new file 32 passed. Full CI command 1051 passed, 119
  deselected, coverage 94.78%. `-m integration` without
  PostgreSQL: 103 passed, 16 skipped.
- Active agents: none.
- Blockers: none.
- Next action: none for #19. `feature/collector-interface-24`
  (PR #68) is rebased onto it.

## Portfolio issue numbers: 2026-10-10

- Branch `docs/record-portfolio-issue-numbers`, based on
  `origin/master` `34f462a` (PR #64, squash-merged).
  [PR #66](https://github.com/Waber/Investment-AI-Companion/pull/66).
- Completed: PR #64 is on `origin/master`. Issue
  [#57](https://github.com/Waber/Investment-AI-Companion/issues/57)
  now includes several portfolios, holding edits, total value,
  the type split and gain/loss. Issue
  [#58](https://github.com/Waber/Investment-AI-Companion/issues/58)
  allows buy and sell signals from the application and an agent,
  without a not-advice notice. New issue
  [#65](https://github.com/Waber/Investment-AI-Companion/issues/65)
  is the AI Portfolio. All three stay `deferred`.
- Incomplete: implementation of #24, #19, #25, #26, then later
  #57, #58 and #65. The shipped `/ui` disclaimer banner is
  unchanged.
- Tests: `test_tracked_files_have_no_personal_machine_paths`
  passed (1). The UI suite was not run.
- Active agents: none.
- Blockers: none.
- Next action: review this short documentation pull request.
  Do not start #57, #58 or #65 before the demo queue. The next
  implementation item remains #24, then #19, #25, and #26
  (with #16).

## Portfolio, signals, and AI Portfolio docs: 2026-10-10

- Branch `docs/portfolio-signals-ai-portfolio`, based on
  `origin/master` after PR #63. Documentation only.
  [PR #64](https://github.com/Waber/Investment-AI-Companion/pull/64)
  is merged on `origin/master` as `34f462a`.
- Completed: product requirements draft v0.4. Several real
  portfolios with add/edit/remove, total value, type split, and
  gain/loss. Buy and sell signals may be issued by the
  application together with an agent, and a "not investment
  advice" notice is not required. Later experimental AI
  Portfolio (section 12.6), now #65. The shipped `/ui`
  disclaimer banner is unchanged.
- Incomplete: implementation of #24, #19, #25, #26, #57, #58
  and #65.
- Tests: `test_tracked_files_have_no_personal_machine_paths`
  after the v0.4 edits. The UI suite was not run.
- Active agents: none.
- Blockers: none.
- Next action when this section was written: review PR #64.
  That review is done. The live next action is the section
  above.

## /ui instrument list and detail: 2026-10-08

- Branch `cursor/ui-skeleton-htmx-aa8b`, rebased onto
  `origin/master` `8ee15e3` (PR #61 merged; earlier base was
  `d7f6798`, PR #60).
  [PR #63](https://github.com/Waber/Investment-AI-Companion/pull/63).
  Refs #29. The demo steps are in `docs/RUN_DEMO.md`.
- Completed: server-rendered `/ui` list and detail over the current
  company rows. Polish by default, English by cookie. Search plus
  type, exchange, and currency filters. The type options are the
  distinct view-model types (stock) with catalog labels, plus an
  all-types option. An unknown type returns an empty list.
  Skip link, list-header `scope="col"`, and a `:focus-visible`
  outline. Synthetic-data badge, disclaimer in both languages,
  missing values as "brak danych" / "no data".
  Website strings become links only for http/https, in the
  view-model. HTMX 2.0.10 and CSS are local. `jinja2` 3.1.6 is
  pinned in the hashed locks. PR #60 did not change the requirement
  files, so the locks were not regenerated. `python-multipart` is
  not added. `--database-url` seeds a gitignored sqlite file for
  the demo. `docs/demo-data.md` has the exact commands. The UI
  tests are not `integration` tests, so the PostgreSQL job does
  not run them and the zero-skip guard does not count them.
  QA follow-up on the same branch: history restore returns the
  full page and `/ui` sends `Vary: HX-Request`; `..` cannot leave
  `/ui`; a non-integer instrument id is an HTML 404; `/ui`
  responses send the local CSP, frame denial, nosniff, and
  referrer policy. Seed tests use the neutral postgres URL. The
  vendored htmx sha256 is in `static/vendor/README.txt`.
  An instrument id is an ASCII digit string of at most 19
  characters, with no leading zero when longer than one
  character, and at most `2**63 - 1`. Longer strings are rejected
  before `int`. Unicode digits, `01`, and `007` are the HTML 404.
  `/ui` sends `Cache-Control: no-store`. Website links reject
  format characters and DEL. The htmx config meta tag turns off
  the indicator style, `allowEval`, and `allowScriptTags`.
  `docs/demo-data.md` was not rewritten for #61.
- Incomplete: #26 (instrument model, type/country/ISIN filters,
  ETF/ETC detail), #27 (demo-v2 prices), #28 (ETF/ETC attributes),
  and #25 (one-command demo). PR #61 is merged. The demo seed
  and uvicorn need `SECRET_KEY` of at least 32 characters.
  `docs/demo-data.md` points at `docs/RUN_DEMO.md` and the bind
  is `127.0.0.1`.
- Tests: no `.env`, `DATABASE_URL` unset. The CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  after the rebase onto `d7f6798`: dependency commit 846 passed,
  119 deselected, exact 92.58%; feature commit 892 passed,
  119 deselected, exact 94.79%; docs commit repeats 892 passed,
  119 deselected, exact 94.79%. The type-filter follow-up:
  892 passed, 119 deselected, exact 94.81%. The QA follow-up:
  896 passed, 119 deselected, exact 94.89%. The id and htmx
  config follow-up: 898 passed, 119 deselected, exact 94.91%.
  The review follow-up: 900 passed, 119 deselected, exact
  94.95%. After the rebase onto `8ee15e3`: dependency commit
  965 passed, 119 deselected, exact 92.79%; feature commit
  1011 passed, 119 deselected, exact 94.61%; type-filter commit
  1011 passed, 119 deselected, exact 94.63%; history-restore
  commit 1015 passed, 119 deselected, exact 94.71%; ASCII-id
  commit 1017 passed, 119 deselected, exact 94.72%; review
  commit 1019 passed, 119 deselected, exact 94.76%. Docs
  commits repeat the Python result of the commit they follow.
  `-m integration`
  with no `TEST_POSTGRES_DSN`, after this rebase: 103 passed,
  16 skipped, 1019 deselected. The 16 skips need PostgreSQL.
  The UI tests are deselected.
- Active agents: none.
- Blockers: none.
- Next action: review pull request #63 (Refs #29). Do not start
  #26, #27, #28, or #25 on this branch. After it merges, the next
  items are #24, #19, #25, and #26 (with #16 and #17). Demo
  issues #24 through #40 use the `demo` label. Post-demo work
  is #54 through #58.

## Secure defaults, neutral paths, and provider hygiene: 2026-10-08

- Branch `cursor/secure-config-provider-hygiene-c91c`, based on
  master `d7f6798`.
  [PR #61](https://github.com/Waber/Investment-AI-Companion/pull/61).
- Completed: #45, #47, and #50, plus the blank-ticker cases from
  #17. Security signed off, so the pull request closes #50.
  `DEBUG` defaults to false. `SECRET_KEY` is required, rejects
  the two known placeholders in any letter case, and must be at
  least 32 characters. `ALLOWED_HOSTS` is enforced
  with `TrustedHostMiddleware` (default `localhost`, `127.0.0.1`).
  `python main.py` binds `127.0.0.1`. `BACKEND_CORS_ORIGINS` is a
  string plus a validator that accepts a comma-separated list and
  a JSON list. pydantic-settings stays at 2.1.0 and both locks are
  unchanged. `DATABASE_URL` defaults to
  `postgresql://investment_ai@localhost:5432/investment_ai`.
  Operator guides name `~/IdeaProjects/Investment-AI-Companion`.
  Older notes use `~/projects/Investment-AI-Companion` and
  `$TMPDIR`. A `git grep` test fails if a personal home-directory
  prefix, the old temporary-directory prefix, or the previous
  local account name comes back. Tickers match
  `^[A-Z0-9._\-^=]{1,20}$` after control characters are rejected
  and the value is stripped and uppercased. The pattern is wider
  than the issue's 15-character example because the demo fixture
  uses underscores and `DEMO_DE_INDUSTRY` is 16 characters, while
  the column is `String(20)`. Provider `ValidationError` on
  fetch-company is HTTP 502 with `Provider returned invalid company
  data`, logged without the provider input. Uniqueness stays HTTP
  400. A missing company on update stays HTTP 500 and is now
  logged. Ticker logs use `%r`. `/api/v1/test-config` stays
  registered and returns 403 when DEBUG is off.
- Review follow-up, still on this branch, on top of `b36f7da`:
  settings errors hide other secrets, `SECRET_KEY` is at least 32
  characters, `ALLOWED_HOSTS` parses like CORS, name and provider
  error logs use `%r`, non-ASCII tickers are rejected, 422 bodies
  truncate long `input` values, descriptions are capped at 5000
  characters on write, CORS origins are bare http(s) URLs, the
  handler does not uppercase a ticker twice, the demo `DATABASE_URL`
  expands `$TMPDIR`, `GBp` is stored unchanged, and the read model
  does not apply write-time ticker rules. A provider description
  longer than 5000 characters is cut to the first 5000 in
  fetch-company, with no ellipsis; user create and update still
  return 422. The read model keeps `website` as plain text so a
  stored non-URL still lists. Security and QA approved
  `f1072cc`. The next action below is unchanged.
- Code Reviewer round 1, on top of the rebase onto `d7f6798`:
  `period_type` length stays on create only, so a stored
  25-character value still lists. A missing `SECRET_KEY` defaults
  to empty and the error names `token_urlsafe(32)`. The
  integration check that the code-default secret is absent skips
  an empty default, because that string is in every line. The
  harness key is still required in the output.
  `ALLOWED_HOSTS` entries are lowercased, and whitespace or
  control characters are rejected. The personal-path guard
  requires `git grep` exit 1. The PostgreSQL `dup` expected
  failure records the #16 unique-index 500, because the ticker
  is uppercased. Operator docs name the shared checkout and the
  unknown-Host 400. The next action below is unchanged.
- Incomplete: the queue in the next-action line is still open.
  Alembic (#8) stays later.
  `fetch-financial-metrics` is still a placeholder. It validates
  the ticker and does not map provider `ValidationError` to 502.
  isort and flake8 still report the previous unused-import and
  E402 findings in `setup_database.py`. CI runs the SQLite suite
  and the PostgreSQL integration job. It does not run black,
  isort, or flake8.
- Tests: no `.env`, `DATABASE_URL` unset, fresh Python 3.12.3 venv,
  `pip install --require-hashes -r requirements-dev.lock`. The CI
  command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  on the test commit `e352413`: 865 passed, 51 xfailed, 14.91s,
  exact 92.93%. On the fix commit `849b08a`: 918 passed, 1
  xfailed, 14.44s, exact 93.41%. Docs tree: 919 passed in
  14.56s, no xfailed, exact 93.41%. The provider-description
  truncation commit: 951 passed in 15.42s, exact 92.63% (1143
  statements, 78 missed, 254 branches, 15 partial). After the
  website, CORS, and currency follow-ups: 954 passed, exact
  92.77% (1143 statements, 77 missed, 254 branches, 14 partial).
  After the Code Reviewer round: 965 passed, 119 deselected,
  exact 92.79% (1145 statements, 77 missed, 256 branches, 14
  partial). DSN, isolation, and skip-guard integration tests:
  103 passed. The PostgreSQL API tests were not run locally.
  `black --check`
  passed on the touched Python files.
- Active agents: none.
- Blockers: none.
- Next action when this section was written: #24, the collector interface by capability plus a
  deterministic offline fake collector selected by config
  (`DATA_COLLECTOR=fake|yahoo`). Include the QA follow-ups in the
  issue body: `debt_to_assets` from the balance sheet for equities
  and `None` for ETFs/ETCs (the full Yahoo adapter stays #54);
  keep the NaN/infinity guard that is already on master; define
  cache, rate-limit, and backoff hooks and test them with the fake
  and a fake clock; separate "no data" (HTTP 404) from a provider
  error (typed `ProviderError`, HTTP 502, fixed detail, logged).
  yfinance is already >=1.7, so the "without upgrading yfinance"
  line in #24 is outdated. Then #19, #25, and #26 (with #16).

## PostgreSQL integration harness: 2026-10-08

- Branch `cursor/postgres-integration-harness-fc54`, rebased onto
  `origin/master` `f66f26b` (#59). Code Reviewer approved the
  pre-rebase head `4960a42`. This push adds the three review nits:
  the PostgreSQL job fails if any test is skipped while
  `REQUIRE_POSTGRES=1`; the case-collision expected failure cites
  PRD question 10 and I1 #26; those tests create `DUP` in the
  body and add the strict xfail marker only after that create
  succeeds. Left for later: the private pytest frame walk in
  `env_isolation`, and `PGPORT` in the denylist identity.
  [run 37840094330](https://github.com/Waber/Investment-AI-Companion/actions/runs/37840094330)
  was green on `4960a42` before this rebase.
  [run 37841966780](https://github.com/Waber/Investment-AI-Companion/actions/runs/37841966780)
  is green on `135bc59`. SQLite 846 passed, 116 deselected.
  PostgreSQL 114 passed, 2 xfailed, 0 skipped. QA approved
  docs head `5aa1ccf`. A follow-up records module-level
  `pytest.skip` collection reports in the zero-skip guard and
  names the first skipped node ids in the banner.
- Completed: issue #9. SQLite stays the default. `python -m pytest`
  deselects the `integration` marker and still reports 846 passed.
  `TEST_POSTGRES_DSN` opts in. An unset variable skips. The DSN
  allowlist refuses a name that does not contain `test` as its
  own word, and a host that is not loopback or a Unix socket,
  unless `TEST_POSTGRES_ALLOW_REMOTE=1`. `PGHOSTADDR` must be
  loopback and `PGSERVICE` is refused even when the URL names a
  host, because libpq still applies them. `PGHOST` is checked
  only when the URL has no host. The application database
  is still refused after those checks, including the code default
  (database name `investment_ai` on localhost). CI pins
  `postgres:16.15@sha256:ca0bd484cb98bf4b24eb1010e73fb3fcbd6714d240fbc1a10eea5b7dbecb641d`
  and database `investment_test`. The SQLite job is unchanged,
  including `--cov-fail-under=80`, `persist-credentials: false`,
  and the hashed `requirements-dev.lock` install. Tables come
  from `Base.metadata.create_all`. Selecting the integration
  marker imports the application from an empty directory, so a
  stray `.env` is not applied. The duplicate-instant check from
  #20 runs on PostgreSQL. #16 is recorded (exact duplicate
  `DUP` is 500, then `OTHER` shows the session recovered). A
  strict xfail records the #16 target (400 or 409, one row). A
  second strict xfail records case collision as PRD question
  10 / I1 #26. `tests/conftest.py` was not modified.
  The PM dropped the disposable cluster runner. The README
  documents the pinned image.
- Incomplete: Alembic baseline #8, including upgrade/downgrade on
  PostgreSQL. #16 is not fixed. #20 stays open until review
  accepts the PostgreSQL run. The queue in the next-action line
  is still open. The disposable runner is not remaining work.
  Later, not in this push: the private pytest frame walk in
  `env_isolation`, and `PGPORT` in the denylist identity.
- Tests: no `.env`, `DATABASE_URL` unset, Python 3.12.3, the CI
  command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 846 passed, 119 deselected in 12.43s, no warnings summary,
  TOTAL 92% (exact 92.58%).
  `REQUIRE_POSTGRES=1` and
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`
  with `-m integration` -> 117 passed, 2 xfailed, 846 deselected
  in 4.15s, exit 0. Of the 119 integration tests, 103 do not
  open PostgreSQL and 16 hit the database (14 passed, 2 xfailed).
  The two expected failures
  create `DUP` first; without the DSN they skip (2 skipped),
  and with `REQUIRE_POSTGRES=1` and no DSN they error (exit 1).
  A node id without
  `-m integration` -> 1 deselected, exit 5. GitHub Actions
  [run 37836507848](https://github.com/Waber/Investment-AI-Companion/actions/runs/37836507848)
  on `c9b7302`: SQLite 846 passed, 68 deselected in 17.49s,
  TOTAL 93%. PostgreSQL 67 passed, 1 xfailed in 2.68s.
  [run 37837340255](https://github.com/Waber/Investment-AI-Companion/actions/runs/37837340255)
  on `1fc4edb`: SQLite 846 passed, 68 deselected in 16.98s.
  PostgreSQL 67 passed, 1 xfailed in 2.86s.
  [run 37838815029](https://github.com/Waber/Investment-AI-Companion/actions/runs/37838815029)
  on `64acc52`: SQLite 846 passed, 108 deselected in 18.22s.
  PostgreSQL 106 passed, 2 xfailed, 846 deselected in 2.96s.
  `postgres_client` uses `http://127.0.0.1`. The integration
  import sets a 34-character `SECRET_KEY` when the marker is
  selected. Query parameters cannot redirect the connection.
  The harness is merged. Older sections below are snapshots
  from before it.
- Active agents: none.
- Blockers: none.
- Next action when this section was written: #45 and #47 together
  (secure config defaults and neutral defaults, one pull request),
  with #50 if that fix stays small. Then #24, #19, #25, and #26
  (with #16 and #17). The live next action is in the /ui section
  above.

## Security dependencies and hashed lock: 2026-10-08

- Branch `cursor/security-deps-hashed-lock-79f1`, based on
  `origin/master` `7120577`.
  [PR #51](https://github.com/Waber/Investment-AI-Companion/pull/51).
- Completed: the security/deps part of #11, plus #46 because the
  workflow changed. FastAPI 0.143.0 and Starlette 1.7.0 replace
  FastAPI 0.104.1 and Starlette 0.27.0. Pydantic stays on v2
  (2.13.5). `requests` 2.34.2, `python-dotenv` 1.2.4, `black` 26.10.0,
  `pytest` 9.1.1, and `pytest-asyncio` 1.4.0 are the locked installs.
  `yfinance` is 1.7.0. Unused direct pins are removed. Runtime and
  dev requirements are split. `requirements.lock` and
  `requirements-dev.lock` are hashed. CI installs the dev lock with
  `--require-hashes`. `actions/checkout` and `actions/setup-python`
  are pinned to commit SHAs. `google-genai`, `jinja2`, and
  `python-multipart` are not pinned.
- One pull request. The FastAPI jump did not need a Pydantic major
  bump or a broad code rewrite. The test that compares ordinary 422
  bodies calls `errors(include_url=False)`, which is how FastAPI
  0.143 builds those errors. Black 26 reformats are a separate
  commit.
- Incomplete: the queue in the next-action line is still open.
  Alembic (#8) stays later.
  `google-genai` waits for the Gemini adapter. A dry-run of
  `google-genai` 2.29.0 against this set installs, and it would
  downgrade `websockets` from 17.2 to 16.1.1 because that release
  requires `websockets<17`. `jinja2` and `python-multipart` wait for
  the UI. isort and flake8 still report the previous import and
  line-length findings. CI runs pytest only.
- Tests: no `.env`, `DATABASE_URL` unset, fresh Python 3.12.3 venv,
  `pip install --require-hashes -r requirements-dev.lock` (started
  from pip 24.0). The CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 846 passed in 12.42s, no warnings summary, TOTAL 92% (exact
  92.58%). `black --check` on `app`, `main.py`, `setup_database.py`,
  and `tests` passed. `pip-audit -r requirements.lock` and
  `pip-audit -r requirements-dev.lock` both reported no known
  vulnerabilities. The runtime lock installs the same way.
  `--strip-extras` does not change the runtime lock's pins or
  hashes. It changes the dev lock from `coverage[toml]==7.16.2`
  to `coverage==7.16.2` with the same hashes. Each commit passes
  the CI pytest command in a venv installed from that commit's
  lock (same lock blob `9b70931`): `a585a01` 846 passed in 12.75s,
  `912c12b` 846 passed in 12.57s, `3bbea71` 846 passed in 12.79s,
  and this docs tree 846 passed in 12.92s. Exact coverage 92.58%
  on every run. CI does not run black, isort, or flake8.
- Active agents: none.
- Blockers: none.
- Next action when this section was written: #45 and #47 together
  (secure config defaults and neutral defaults, one pull request),
  with #50 if that fix stays small. Then #24, #19, #25, and #26
  (with #16 and #17).

## Fetch-company 500 detail and debt_to_assets: 2026-10-08

- Branch `cursor/fetch-company-500-debt-to-assets-9f95`, based on
  `origin/master` `a03ca24`.
  [PR #49](https://github.com/Waber/Investment-AI-Companion/pull/49).
- Completed: bug #18 and bug #21.
  `POST /api/v1/data-collection/fetch-company` returns HTTP 500 with
  the fixed detail `Error fetching company data`. The exception is
  logged with the ticker through `logger.exception`. 404 (no provider
  data) and 400 (`ValueError`) are unchanged. There is no global
  exception middleware.
  `debt_to_assets` is `totalDebt / totalAssets` when both values are
  real numbers already on the Yahoo `info` dict. Otherwise it is
  `None`. Booleans are not treated as numbers. NaN, infinity,
  negative debt, and a non-positive asset total are `None`. A huge
  int that would raise `OverflowError` is `None` and does not drop
  the other metrics. NumPy reals are accepted. The mapping never
  reads `totalDebtPerShare` and makes no extra provider call. No
  other Yahoo field changed.
- Incomplete: the queue in the next-action line is still open.
  Alembic (#8) stays later.
- Tests: no `.env`, `DATABASE_URL` unset, the CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 838 passed in 15.33s, no warnings summary, TOTAL 92% (exact
  92.70%) before the reviewer nits. After the isfinite, sign, and
  overflow guards: 846 passed in 15.09s, exact 92.75%. On
  `6a7f533`, the two strict xfails were `2 xfailed`
  (both `AssertionError` under `--runxfail`). On `a06ca28` the
  further behaviour tests were `8 failed` at assertion level. The
  404/400 pin already passed on that commit.
- Active agents: none.
- Blockers: none.
- Next action when this section was written: #11, the security/deps
  part. That work is the section at the top of this file. The
  detail below is the priority as it stood before that work: the
  FastAPI and Starlette CVE upgrade, `requests`, `python-dotenv`,
  `black`, `pytest`, removing unused pins, `yfinance>=1.7`, and a
  lock file with hashes. On 2026-10-08 the Project Manager moved this
  security/deps part ahead of the demo after the Security Engineer's
  review found CVEs: `fastapi==0.104.1` forces `starlette==0.27.0`
  (CVE-2024-24762, CVE-2024-47874, CVE-2025-54121), and
  `requests==2.31.0` is also affected. This overrides
  `docs/product-requirements.md` around line 254, which at that
  moment still listed #11 after the demo. That requirements file
  was unchanged when this section was written. The section at the
  top records the update. After #11
  come #45 and #47 together (secure config defaults and neutral
  defaults, one pull request), then #24, #19, #25 and #26 (with #16
  and #17). #46 (pin Actions to SHAs) goes into any pull request
  that touches CI.

## SQLite UTC timestamps and foreign keys: 2026-10-08

- Branch `cursor/sqlite-utc-timestamps-foreign-keys-feb1`, rebased
  onto `origin/master` `f8266ea`.
  [PR #22](https://github.com/Waber/Investment-AI-Companion/pull/22)
  is merged as `778735e`.
  [PR #41](https://github.com/Waber/Investment-AI-Companion/pull/41)
  is merged as `07c30f6`.
  [PR #43](https://github.com/Waber/Investment-AI-Companion/pull/43)
  is merged as `f8266ea`. Demo slice D1 (issue #23) and bug #20.
- Completed: `UTCDateTime` normalizes every `DateTime(timezone=True)`
  column to UTC. SQLite stores the UTC wall clock and reads come back
  timezone-aware UTC. PostgreSQL still receives an aware datetime.
  `period_end` is normalized to aware UTC before the uniqueness
  pre-check on create and update. Naive `period_end` input is treated
  as UTC and stored as that instant. The API returns it with a `Z`
  suffix. On PostgreSQL, naive `period_end` input used to be
  interpreted in the session time zone and is now UTC. Responses now
  always use the `Z` suffix. The PUT OpenAPI schema shows `period_end`
  as a non-nullable date-time. The app engine enables SQLite foreign
  keys, and the tests reuse that hook. A PostgreSQL `create_db_engine`
  call attaches no SQLite listener and opens no connection.
  `python scripts/seed_demo.py --apply` succeeds twice on a fresh
  SQLite file and does not insert duplicate rows. `PUT` can move
  `period_end`. An explicit null is a 422 from the update model.
  Omitting the field leaves the stored instant unchanged. Moving onto
  an existing company, period, and type is 400.
- Incomplete: the formal PostgreSQL harness is still #9. QA verified
  #20 on PostgreSQL 16 (Europe/Warsaw) at the application level: the
  same instant with `+02:00`, `Z`, or naive returns 400, and readback
  has no double shift. Alembic (#8), the instrument model (#26), and
  bugs #18, #19, and #21 are not in this branch.
- Tests: no `.env`, the CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 825 passed in 15.31s, no warnings summary, TOTAL 92% (exact
  92.35%). The head `dbcfaa5` was 823 passed, exact 92.41%. The
  rebased head `c3c8911` was 822 passed, exact 92.36%. Before the fix,
  `tests/test_known_defects.py` was `1 xfailed` and
  `tests/test_sqlite_utc_timestamps.py` was `8 failed`. On master,
  `PUT {"period_end": null}` returned 200 and the value was ignored.
  At `c3c8911` that request was 400 `constraint violation`. It is now
  422.
- Active agents: none.
- Blockers: none for bugs #18 and #21.
- Next action when this section was written: bugs #18 and #21, then
  #24. Bug #19 could be slotted in. Bugs #18 and #21 are done in the
  section above. This list is history.

## Product requirements and research: 2026-10-08

- Branch `cursor/product-requirements-research-301f`. Docs only. Adds
  `docs/product-requirements.md` (draft v0.2) plus
  `docs/research/market-data-sources.md` and
  `docs/research/llm-comparison.md`. No `.py`, workflow, or config edits.
  `docs/product-requirements.md` matches the PM's updated copy
  (2026-10-08), which fixes the research paths and makes N1 optional for
  A1.
- Completed: those three files are on this branch. Demo issue links to
  `docs/product-requirements.md` resolve here. The research notes are
  under `docs/research/`, which is the relative path the requirements
  file already uses.
- Incomplete: Demo v1 issues #23–#40 are not started. QA bugs #16–#21
  are still open. PR #13 is merged as `a10e196`. PR #15 is merged as
  `b2541d7`. PR #22 is merged as `778735e`. This branch is rebased onto
  that master.
- Tests: after the rebase, the 80% gate command passed: 813 passed in
  11.50s, no warnings summary, TOTAL 92% (exact 91.77%). The earlier
  docs-only run was 758 passed. GitHub Actions Tests on `8ba25ee`
  (https://github.com/Waber/Investment-AI-Companion/actions/runs/37756800118)
  is from before this rebase. The final run on `973330b` succeeded:
  https://github.com/Waber/Investment-AI-Companion/actions/runs/37758000432
  Job `pytest (Python 3.12, SQLite)` completed with conclusion success.
  Rebase-merge recorded that commit on master as `07c30f6`.
- Active agents: none.
- Blockers: none for starting Demo v1.
- Next action when this section was written: Demo v1 issue
  [#23](https://github.com/Waber/Investment-AI-Companion/issues/23)
  together with bug
  [#20](https://github.com/Waber/Investment-AI-Companion/issues/20)
  first, then bugs
  [#18](https://github.com/Waber/Investment-AI-Companion/issues/18)
  and
  [#21](https://github.com/Waber/Investment-AI-Companion/issues/21),
  then
  [#24](https://github.com/Waber/Investment-AI-Companion/issues/24),
  then
  [#25](https://github.com/Waber/Investment-AI-Companion/issues/25),
  then
  [#26](https://github.com/Waber/Investment-AI-Companion/issues/26).
  Issues #8, #9, and #10 come after the demo. Issue #23 and bug #20
  are done in the SQLite UTC section above. Bugs #18 and #21 are done
  in the section at the top of this file. This list is history.

## Coverage Gate: 2026-10-08

- Branch `cursor/coverage-threshold-80-c3a6`, based on `origin/master`
  `b2541d7` (PR #15, tooling config, rebase-merged). QA's two commits are
  applied with `git am` and keep their author. No production `.py` edits.
  A later commit on this branch adjusts tests and the README only.
  QA's commits are not rewritten. The 80% gate is unchanged. Code
  Reviewer approved `63822cd`. PR #22 is merged as `778735e`.
- `--cov-fail-under=80` is enforced in `.github/workflows/tests.yml` and
  the README test command. The gate reads TOTAL for `app`, `main`, and
  `scripts`, statements plus branches. JUnit XML and the `MIN_TESTS` gate
  are still not enabled. Raul chose this 80% threshold on 2026-10-08 at
  10:48 Warsaw time, overriding the earlier 70% recommendation. The
  Project Manager relayed that decision.
- Local Python 3.12.3, pytest 7.4.3, no `.env`, no network route:
  `813 passed in 11.89s`, no warnings summary, TOTAL `92%` (exact
  `91.77%`). Random-order seeds 7, 21, and 42 passed the same way. The
  same command on master `b2541d7` is `758 passed`, exact total `76.08%`,
  and the gate fails.
- PR #13 is merged as `a10e196`. PR #14 is merged as `db0cc12`. PR #15
  is merged as `b2541d7`. Lines below that still tell the story of those
  pull requests being opened are history; the sentences that called them
  open or awaiting review are corrected.
- Reviewer nits from PRs #14 and #15 are in PR #43
  (`cursor/reviewer-nits-minimal-c3a6`). PR #22 is merged as `778735e`.
  PR #41 is merged as `07c30f6`.
- Review follow-up: missing test-config settings are isolated from the
  shell, statement keys are a subset, and company-shaped pins are marked
  `see #26`. `NEWS_API_KEY=x` no longer fails
  `test_test_config_marks_missing_settings`.
- The live next action is the section at the top of this file.
- Account usage was not available in this session. Stop reason: coverage
  gate delivered, not quota.

## Tooling Config Slice: 2026-10-07

- Branch `cursor/tooling-config-black-isort-flake8-pytest-48d8`, rebased onto
  `origin/master` `db0cc12` (PR #14, minimal CI, rebase-merged).
  Config and docs only (`pyproject.toml`, `.flake8`, README lint section,
  this note, and a short journal entry). No `.py` edits and no workflow edits.
- Black 79 / target py312, isort profile black at 79, flake8 max line length
  79 with no `extend-ignore`. pytest registers `integration`, uses
  `--strict-markers`, and the default run passes `-m "not integration"`.
  `pyproject.toml` does not pin pytest or set `filterwarnings`.
- `pytest -q` on `a10e196` before this config, no `.env`: 758 passed, no
  warnings summary. After this config, including CI's
  `-W error::DeprecationWarning`, `-p no:cacheprovider`, and coverage flags:
  758 passed, no warnings summary, coverage total 76%.
  `pytest --markers` lists `integration`.
- `tests/test_model_config_compatibility.py` passes the configured checks.
  `tests/test_company_update_conflicts.py` still fails isort. The five
  production files from the cleanup still have the same pre-existing
  Black/flake8 debt; isort still fails only `app/api/data_collection.py`
  among them. None were reformatted.
- [PR #15](https://github.com/Waber/Investment-AI-Companion/pull/15)
  is merged as `b2541d7`. The next-action line that said to review it
  was the state when this snapshot was written. The live next action
  is the section at the top of this file.
- The Resume Instructions section immediately below is the merged
  minimal-CI note from PR #14, not the deprecation cleanup. The
  deprecation record follows that CI note.

## Resume Instructions

Minimal pytest CI (issue #5) is merged as
[PR #14](https://github.com/Waber/Investment-AI-Companion/pull/14)
on `origin/master` `db0cc12`. Workflow is `.github/workflows/tests.yml`.
Local suite on Python 3.12.3 with no `.env` and
`-W error::DeprecationWarning`: `758 passed in 13.56s`, no warnings
summary, coverage total `76%`. The draft QA spec is applied.
The coverage threshold is now `--cov-fail-under=80` (Coverage Gate
section, third in this file). JUnit XML and the `MIN_TESTS` gate are
still not enabled. Red demo run
[37681557386](https://github.com/Waber/Investment-AI-Companion/actions/runs/37681557386)
failed on purpose. Commit `806faef` was dropped before merge, so that SHA
is not on master. Lint and format stay out of this workflow (issue #6).
Deprecation cleanup is on master and is also recorded below.

Deprecation cleanup (GitHub issue #4) is on `origin/master` as `a10e196`
(rebase merge of [PR #13](https://github.com/Waber/Investment-AI-Companion/pull/13)).
The bullets below are that delivery's record.

Latest earlier delivery is the 2026-10-07 rebase workflow rule (docs only; see
the journal). No production code changed in that delivery. Account usage from
the previous ChatGPT tooling was not available in that Cursor session.

- Base: `origin/master` `a58dc8a` (PR #3, rebase workflow, rebase-merged).
  PR #2 is merged as `b10d06e`.
- Change: `declarative_base` now comes from `sqlalchemy.orm`. Response models
  use `ConfigDict` with `from_attributes=True`. Financial metrics still set
  `allow_inf_nan=False`. `FetchCompanyRequest` still documents ticker `AAPL`.
- Baseline before the edit: 742 passed, 4 warnings. After the change and
  the review follow-ups: 758 passed, no pytest warnings summary. The
  warning check fails on the pre-cleanup sources and passes here. Its child
  uses a temporary directory and checks that directory is not the project
  root. The test does not write into the repo.
- Verification used a clean environment and pinned `requirements.txt`
  (`pydantic==2.6.1`, `sqlalchemy==2.0.23`). No private `.env`, live
  provider, or dependency upgrade.
- Style: the new test file passes Black 79, isort, and flake8. Production
  files still have pre-existing Black/flake8 debt; isort fails only
  `app/api/data_collection.py` among the edited files. `git diff --check`
  passed. Repo-wide lint was not run.
- [PR #13](https://github.com/Waber/Investment-AI-Companion/pull/13)
  is merged as `a10e196`. The next-action line that said to re-review it
  was the state when this snapshot was written. Tooling config (issue #6,
  PR #15, `b2541d7`) and minimal CI (issue #5, PR #14, `db0cc12`) are
  merged too. The live next action is the section at the top of this
  file. Editable profiles and source-aware AI stay later.
- Account usage was not available in this Cursor session. Stop reason:
  bounded cleanup completed, not quota.

## Previous Iteration: 2026-10-07 rebase workflow rule

Documentation only. Now on `origin/master` as `a58dc8a` (rebase merge of
PR #3). Wording below that said the rebase pull request was left unmerged
was true when that pull request was opened. It is merged. No production code
changed in that pull request. Account usage was not available in that Cursor
session. This cleanup and that pull request both edit the journal and
work-state; both entries are kept.

## Previous Iteration: 2026-10-07 lifespan and CORS

Historical delivery, now on `origin/master` as merge commit `b10d06e`. The
review/merge next-action line below was the state when this snapshot was written.

- Branch `fix/startup-lifespan-cors`, worktree `$TMPDIR/investment-metric-updates`.
- Scope and delivery gates: [lifespan/CORS plan](superpowers/plans/2026-10-07-lifespan-cors.md).
- User authorized implementation, push and PR, not merge. Five previous local
  commits from `569a89e` through `cc54057` are included in this branch.
- Implementation complete: lifespan calls existing init_db, startup errors
  propagate, initialization can be disabled and CORS matches exact browser origins.
- 25 new cases, full suite 742 passed / four existing deprecation warnings.
  Scoped Black (79 columns), isort, flake8 and diff whitespace checks passed.
- Carver independently approved code/tests and ancestor integration scan, and
  ran the 25 focused cases. No real database/provider or service checks performed.
- Published as [PR #2](https://github.com/Waber/Investment-AI-Companion/pull/2)
  against master; implementation commit `5bd286c`. No merge. Agents closed.
  Stop reason: approved bounded scope completed, not quota. Final usage 40%
  five-hour / 6% weekly. Follow-up at that time: review the pull request before subsequent development.
- Older entries below are historical, not active workers or current service state.

## Historical Delivery Checkpoint: 2026-10-04

- All work below is complete through the JSON overflow slice on
  `fix/json-overflow-validation` in `$TMPDIR/investment-metric-updates`.
- This session: `d9e56ce` metric creation conflicts (6 cases), `2374acf` collector
  refresh (6 cases), plus JSON-safe validation fix (9 cases). Earlier ancestors
  `569a89e` and `0008b0c` remain included. Local commits only, no push/merge.
- Final full suite717 passed, six legacy warnings. Scoped new-file Black/isort/
  flake8 and independent reviews passed. JSON overflow reproduced500 before fix,
  now422 without writes. Reviewer independently ran9 focused tests successfully.
- Agents closed at delivery. No services, real providers, private DBs or reset
  credits touched. Account77% at final review; wrap up now to leave a buffer before
  user90% session limit. Stop reason: three completed slices, no partial code.
- Next bounded work: lifespan/startup failure propagation and CORS fixes from
  September Task1; migrations/PostgreSQL, profiles/AI remain later. Check usage
  and branch publication status before starting. Earlier active/pause entries
  below are historical progress notes, not unfinished workers.

## Active Slice: JSON Overflow Validation

- Branch `fix/json-overflow-validation`, base completed collector `2374acf`.
- User-approved continuation; usage50% five-hour on starting. Stop near90%.
- Reproduce raw JSON numeric overflow500 and return JSON-safe422 instead. Minimal
  RequestValidationError handler; no lifecycle/CORS/dependency edits in this slice.
- Developer owns handler, registration and tests; coordinator docs/review/checkpoint.

## Active Slice: Collector Refresh

- Branch `test/collector-refresh-regressions`, base metric-creation commit `d9e56ce`.
  Same worktree. Fake-provider refresh/not-found tests in progress; no live calls.
- Metric creation conflict/rollback stage completed and committed. Current session
  threshold90% remains; check usage before choosing any subsequent work.
- Collector complete:6 new cases, full708 passed/six warnings. Epicurus approved
  spec/quality; coordinator Black/isort/flake8 passed. No production changes.
  Both developer/reviewer closed. Next candidate: JSON overflow validation errors.

## Resumed Session: Metric Creation And Collector Coverage

- User reset usage and authorized continuation with a90% threshold for this session;
  default80% remains for future sessions unless overridden. Initial account usage0%.
- Branch `test/metric-creation-conflicts` based on `0008b0c`, same worktree.
- Helmholtz owns metric creation conflict/rollback tests. Coordinator handles docs,
  full tests and independent review. Then proceed to fake-collector refresh coverage
  only after this slice is committed and usage permits. No live providers or DBs.
- Earlier pause statements below are historical. Previous completed slices remain
  local ancestors; no automatic push/merge. Start wrapping up before90%.
- Metric creation slice completed:6 new cases, full702 passed/six existing warnings;
  Poincare approved spec and quality. Coordinator corrected import grouping using
  worktree-local isort. No production changes. Usage20% at verification.

## Active Slice: Company Update Conflicts

- Branch `test/company-update-conflicts`, based on completed `569a89e`, same
  `$TMPDIR/investment-metric-updates` worktree. Start usage60% five-hour.
- Kant implements narrow duplicate-name/ticker and same-session rollback tests.
  Completed3 cases; full696 tests passed with six existing warnings. Raman approved
  specification and quality. No production changes. Developer scoped format/lint
  checks passed. Saved as local commit, no push/merge.
- Last usage82% five-hour/13% weekly, crossing80% between checks. Pausing after
  checkpoint; wait for user reset/continuation. No reset redeemed. Agents closed.
- Previous metric slice below is complete. Collector and metric-creation
  uniqueness/rollback remain separate follow-up work. Stop at80% consumption.

## Active Slice: 2026-10-04 Metric Updates

- PR1 merged as `1e05ab1`; older sections below describe historical states.
- Branch `test/financial-metric-updates`, `$TMPDIR/investment-metric-updates`.
- Scope: partial metric updates, explicit null, zero, omission and invalid payloads.
  [Slice plan](superpowers/plans/2026-10-04-metric-updates.md). Hubble owns tests;
  coordinator handles docs/full tests. Completed:82 new cases, full693 passed
  with six existing warnings. Black/isort/flake8 passed for the new file;
  Aristotle approved spec and quality. No production changes needed.
- Start usage29% five-hour/4% weekly; preparation35%/5%. User requires closing
  work at80% consumed, then notification and waiting for continuation; no reset
  without authorization. Policy recorded in AGENTS.
- No live database/runtime/provider changes; preserve primary checkout/user files.
- Next after this slice: uniqueness/rollback and fake-collector regressions.
- Completed slice saved locally; no automatic push/merge. Agents closed at delivery.
  Usage at verification50% five-hour/8% weekly; no reset needed. Stop reason:
  bounded slice complete with review/commit, not reaching the80% limit.

## 2026-10-04 Recovery And Publication

- Current branch: `docs/demo-and-ide-delivery`; recovered committed base `69258b9`
  into `$TMPDIR/investment-pr-delivery` for the user-requested commit/push/PR.
- The former temporary worktree was emptied; uncommitted IDE documentation was
  lost after both agents hit the usage limit. The guide is reconstructed with
  explicit database prerequisites and without assuming the old runtime survives.
- The September runtime/process statements below are historical, not current
  service status. No database or service was restarted during recovery.
- Primary checkout has a user-selected branch and untracked `.python-version`;
  neither was changed. PR targets `master`; no merge is authorized in this task.
- Verified:611 tests passed, six existing warnings; independent documentation
  review approved without findings. Push and PR target `master`, not a merge.
  Next development work starts from this PR branch after checking its GitHub
  status. Development backlog below remains outside this publication task.

## Historical September Snapshot

- Date: 2026-09-26. User requested continuation and reusable test data for API/future frontend testing.
- Current branch: `feature/reusable-demo-fixtures`, based on demo documentation commit `83940ea`. Tooling worktree: `$TMPDIR/investment-demo-fixtures`. Running application remains in `$TMPDIR/investment-api-demo`; no restart needed for HTTP-based seeding.
- Primary repo remains `~/projects/Investment-AI-Companion`; its `master` and untracked `.python-version` are untouched.
- Demo: `http://127.0.0.1:8081/docs`, API on port8081 loopback only, no authentication. Never expose publicly.
- PostgreSQL14.19: fresh cluster `$TMPDIR/iac-demo.h7TbGw/data`, private socket directory `$TMPDIR/iac-demo.h7TbGw`, port15432, no TCP listener, role `demo`, database `investment_demo`.
- API runs detached with PID in `$TMPDIR/iac-demo.h7TbGw/api.pid`, log `api.log`; database log `postgres.log` in the same directory. These are intentional demo services, not unfinished test processes. Stop/restart commands are in [the demo guide](api-demo.md).
- Environment is isolated, DEBUG=False, no private `.env` or API keys. Existing installed interpreter used; no dependency upgrade or user DB migration.
- Synthetic sample company `DEMO` and metrics were created successfully (initial IDs both1). No real market/provider calls or AI analysis.
- Fresh regression run: 549 passed, six existing warnings. Live PostgreSQL startup, company insert, and metrics insert succeeded. Final smoke and review are recorded in the journal.
- Starting usage:60% five-hour/26% weekly used; after launch:73%/28%. These are account limits, not remaining-context measurements. No reset or purchase.
- Demo guide/smoke complete and committed in `83940ea`; Curie and Ohm closed. Curl proxy/config finding corrected. Final commit interruption by quota was recovered after user-authorized continuation; no reset was redeemed by the coordinator.
- Completed: fixture6companies/20metrics, schema/scenario tests, Laplace's create-only seeder and 60 unit cases. Volta independently approved with no findings; 62 focused cases passed. Coordinator verified full611 passed, six existing warnings; Black/isort/flake8 passed for the three new Python files. See [plan](superpowers/plans/2026-09-26-reusable-demo-fixtures.md) and [data guide](demo-data.md).
- User-created company with ticker `string` existed before this seed task, alongside original `DEMO`. Preserve both and any subsequent user edits. No cleanup of unrelated data.
- Seeder default is GET-only preview; explicit --apply adds missing fixture records without updates/deletes. Data is synthetic; marker-owned tickers and UTC period keys support repeatability. Individual API writes are not an atomic transaction.
- Live PostgreSQL verification: dry run planned6companies/20metrics with zero writes; firstapply created6/20; secondapply created0/0 and skipped6/20. Prior2companies and1metrics row compared equal to pre-seed snapshots. At verification, total8companies/21metrics; fixture companyIDs6-11 (not portable assumptions).
- Laplace and Volta closed after final reports. No background workers remain; API/PostgreSQL intentionally stay running. Stop reason: user-requested fixture scope completed, not quota interruption. Latest resource check70% five-hour/11% weekly used; no reset redeemed.
- Local fixture commit only; no push/merge. Next session starts from this branch's journal. Temporary runtime is still disposable; committed fixture can reproduce baseline data in a fresh demo, but not user edits.
- Temporary directories can disappear after cleanup/reboot. Git preserves code/docs, not the temporary demo database. Do not keep valuable data here.

## Remaining Work (Updated 2026-10-07)

- Missing-update404 and website-update regressions are complete in ancestors `3a2b0af` and `731c513`.
- Metric partial-update/null, uniqueness/rollback and collector regression coverage
  and JSON overflow handling are complete. Lifespan/CORS is merged (PR #2,
  `b10d06e`). Pydantic/SQLAlchemy deprecation cleanup is merged as
  [PR #13](https://github.com/Waber/Investment-AI-Companion/pull/13)
  (`a10e196`).
- Editable profiles and source-aware AI analysis remain unimplemented. Demo preferences are preserved in the approved September8 design/plan, not yet implemented.
- Prior WIP dependency pin on `feature/research-workflow-and-hardening` conflicts with FastAPI and is not in this branch.
- This manually exercised PostgreSQL demo is not completion of the migration/integration-test task. Financial-metrics provider ingestion is still a placeholder.
- The live next action is the section at the top of this file. The
  old demo runtime is not assumed to still exist.
