# Development Journal

## 2026-10-21 - Review delta on price bars (PR #94)

- Scope: code review on #94 at `82e0b20` requested small changes.
  Same branch, one commit. `0006` still revises `0005`. The pull
  request stays ready. `templates/`, `static/`, and `app/ui/`
  were not edited.
- Decisions: `docs/work-state.md` stays a short snapshot and
  adds "Open work elsewhere". The trim had dropped other teams'
  open items. Restored, one bullet each: #33 (`/ui` forms and
  HTTP API; backend merged in #91), #32 (watchlist page,
  stale-price marker, and PL/EN strings; backend merged in
  #90), #8/#10 (the `0001_baseline.py` plan; prices, the
  watchlist, and notes now have later revisions; `init_db`
  still uses `create_all`), and the rest of #86 (one text
  validator for names, labels, notes, and theses: Tag,
  U+206A–U+206F, U+061C, the Cs gap, Co/Cn treated as blank;
  the `/ui` part is to be agreed with the Frontend Developer).
  Also still open, and not superseded by this pull request:
  #28 fund attributes and forms, #54 (`hide_exceptions` and
  the balance-sheet ratio), the #26 remainder (no Instrument
  rename, no unique `(ticker, exchange)`, no company-list
  filters, metrics not limited to stocks), #34 (`source=manual`
  and a synthetic marker that survives a description edit),
  and the fake collector still serving demo-v1 profiles.
  `StatementError` includes `DBAPIError`. `IntegrityError` is
  still caught first, so a duplicate keeps the duplicate
  sentence. A lost connection, a locked database, or
  `DataError` is rolled back and re-raised unchanged. The
  price routes map `ValueError` to HTTP 400, so swallowing
  the driver error was turning a 500 into a 400. Only a bind
  `ValueError` on `error.orig` becomes "Price bar could not
  be stored", and that raise sits outside the handler so
  `__context__` does not keep the SQL. SQLite text `NaN`
  survives `quantize`, and `abs(NaN)` then raises
  `InvalidOperation` outside the old try, which aborted the
  upgrade with a traceback. `is_finite` inside the try names
  the id. Text `Infinity` already fails inside `quantize`.
  The default source is one `max(retrieved_at)`, then the
  distinct source names at that instant, then Python `max`.
  A tie does not load the full rows. `render_item` says
  autogenerate would render `NUMERIC` on SQLite for a future
  table. The live SQLite column is TEXT, so a new migration
  still has to say so, the way `0006` does.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY`
  unset. No live market-data calls. Scoped black, isort, and
  flake8 passed on the Python this change touches. CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1718 passed, 216 deselected, coverage 96.35%
  (4318 statements, 131 miss, 1188 branches, 54 partial).
  Local PostgreSQL 16.15, `REQUIRE_POSTGRES=1`, and
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`
  -> 216 passed, 1718 deselected. The Actions run id is
  recorded on the pull request after both jobs are green. This
  commit is the review delta, not a CI note.
- AI model: Grok 4.7. Account usage was not available in this
  session.
- Time tracking (UTC): 2026-10-21 about 19:13 to 19:26.
- Next: both GitHub Actions jobs on this head. The pull request
  stays ready for review. Agents do not merge.

## 2026-10-21 - QA delta on the price preflight (PR #94)

- Scope: one medium and two nits on #94 at `310c960`. Same
  branch. `0006` still revises `0005`. The pull request stays
  ready. `templates/`, `static/`, and `app/ui/` were not edited.
- Decisions: the preflight judges the price after the conversion
  the upgrade applies. PostgreSQL names NaN and infinity first,
  then checks `abs(ROUND(column::numeric, 8))`. That `ROUND`
  expression is the same constant the `ALTER` uses. SQLite casts
  each real to text and runs `_quantized_legacy`, which
  `_canonical_text` also calls. `999999999999.9994` stays inside
  the limit and becomes `999999999999.99900000`.
  `upsert_many` loads existing rows with one query on
  `(bar_date, source)`, then updates or inserts in memory. A
  repeated key in the same batch updates the pending row.
  `docs/work-state.md` now keeps only the current master, the
  open pull requests, the queue, and the key decisions. The
  older sections were already in this journal, including the
  note that editable profiles and source-aware AI analysis
  remain unimplemented, so they were not copied again. That
  queue line stays in the work-state file because
  `docs/research/llm-comparison.md` cites it.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY`
  unset. No live market-data calls. Scoped black, isort, and
  flake8 passed on the Python this change touches. CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1715 passed, 216 deselected, coverage 96.35%
  (4316 statements, 131 miss, 1186 branches, 54 partial).
  Local PostgreSQL 16.15, `REQUIRE_POSTGRES=1`, and
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`
  -> 216 passed, 1715 deselected. The Actions run id is
  recorded on the pull request after both jobs are green. This
  commit is the QA delta, not a CI note.
- AI model: Grok 4.7. Account usage was not available in this
  session.
- Time tracking (UTC): 2026-10-21 about 18:34 to 18:43.
- Next: both GitHub Actions jobs on this head. The pull request
  stays ready for review. Agents do not merge.

## 2026-10-21 - Review fixes on price bars (PR #94)

- Scope: code review on #94 at `dc7d9b8` requested changes. The
  fixes stay on `cursor/price-bar-followups-85-5c38`. Revision
  `0006` still revises `0005`. The pull request stays ready.
  `templates/`, `static/`, and `app/ui/` were not edited.
- Decisions: `upgrade()` checks `price_bars` before it changes a
  column. Any OHLC value with `abs >= 1e12`, or a value that is
  not finite, raises `OversizedPricesError` and names the ids.
  Nothing is rewritten. SQLite's driver stores NaN as NULL, so
  that engine's test uses `1e12`, `1e20`, and infinity.
  PostgreSQL also inserts NaN and negative infinity. The default
  source still uses the latest `retrieved_at`. Sources that share
  that instant are ordered with Python `max`, which compares
  code points, so `fake` beats `[IAC-DEMO-V2]` on every collation.
  A `ValueError` from the price column arrives as
  `StatementError`. `IntegrityError` is still handled first.
  The other statement errors roll back and raise
  `Price bar could not be stored` outside the handler, so the
  message has no SQL and no parameters. `upsert_many` reloads
  the flushed rows with one `SELECT ... WHERE id IN (...)`.
  The rollback tests patch that reload. A skip warning is logged
  once per bar id per process, in the repository and in the API.
  Putting skipped bars in the response stays a follow-up.
  Autogenerate renders `PriceAmount` as `sa.Numeric(20, 8)`.
  README and `docs/api-demo.md` say to run `alembic heads`
  instead of naming `0003` as the head. The API demo says to
  parse price strings with `Decimal`, not float math. The
  migration docstring notes that PostgreSQL `ROUND` is half away
  from zero while the app uses half-even (at most `1e-8` on a
  legacy row), and that a float keeps about 15 significant
  digits. `docs/work-state.md` still held the older sections
  under the new one at this commit. The trim is the next entry.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY`
  unset. No live market-data calls. Scoped black, isort, and
  flake8 passed on the Python this change touches. CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1712 passed, 214 deselected, coverage 96.34%
  (4306 statements, 131 miss, 1184 branches, 54 partial).
  Local PostgreSQL 16.15, `REQUIRE_POSTGRES=1`, and
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`
  -> 214 passed, 1712 deselected. The Actions run id is
  recorded on the pull request after both jobs are green. This
  commit is the review fix, not a CI note.
- AI model: Grok 4.7. Account usage was not available in this
  session.
- Time tracking (UTC): 2026-10-21 about 18:06 to 18:22.
- Next: both GitHub Actions jobs on this head. The pull request
  stays ready for review. Agents do not merge.

## 2026-10-21 - Re-chain price bars onto revision 0005

- Scope: #91 has merged. `origin/master` is `1223be6`, whose
  single head was `0005` (`0003` ticker unique, `0004`
  watchlist, `0005` notes and theses). This rebases
  `cursor/price-bar-followups-85-5c38` onto that master and
  points the price migration at `0005`. No price behavior
  change. `templates/`, `static/`, and `app/ui/` were not
  edited.
- Decisions: `0006_price_bar_numeric.py` keeps revision id
  `0006`. `down_revision` is `0005`, and the header says
  `Revises: 0005`. The docstring no longer says the parent is
  temporarily `0003`. One Alembic head. The price round-trip
  downgrades to `0005`, which undoes only this revision.
  Legacy and stamp tests that build the model with
  `create_all` and then upgrade still drop `notes`, `theses`,
  and `watchlist_items` where `0004` or `0005` would create
  those tables again. `database_models.py` keeps the price,
  research, and watchlist imports.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY`
  unset. No live market-data calls. Scoped black, isort, and
  flake8 passed on the Python this change touches. CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1708 passed, 212 deselected, coverage 96.28%
  (4285 statements, 132 miss, 1174 branches, 55 partial).
  Local PostgreSQL 16.15, `REQUIRE_POSTGRES=1`, and
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`
  -> 212 passed, 1708 deselected. Upgrade, downgrade to
  `0005`, and upgrade again passed on both engines. The
  Actions run id is recorded on the pull request after both
  jobs are green. This commit is the re-chain, not a CI note.
- AI model: Grok 4.7. Account usage was not available in this
  session.
- Time tracking (UTC): 2026-10-21 about 17:41 to 17:49.
- Next: both GitHub Actions jobs on this head. The pull
  request is ready for review. Agents do not merge.

## 2026-10-21 - Negative zero, price rollback, SQLite check pin

- Scope: QA approved PR #94 at `36d171b` on content. Three small
  items on the same branch, one commit. Revision `0006` revised
  `0003` at this commit. The re-chain entry above points it at
  `0005`.
  `templates/`, `static/`, and `app/ui/` were not edited.
- Decisions: `Decimal('-0')` compares equal to zero and still has a
  sign. `quantize` keeps that sign. SQLite then stores
  `-0.00000000`. PostgreSQL stores `0`, the read-back does not
  match, and the POST is 400. The price model sets the value to
  `Decimal(0)` before rounding when it is already zero, and again
  after rounding. The second step matters for a value such as
  `-0.000000001`, which is not zero yet and still rounds to
  negative zero. A forced read-back (a different decimal,
  `UnreadablePrice`, null, or `1e400`) raises, rolls the write
  back, leaves no new row, and leaves the earlier row unchanged.
  `upsert_many` is one transaction: the lie is on the last bar, so
  an earlier insert in that batch has already passed the check, and
  rollback removes that insert and the update of the stored row.
  The SQLite `CAST AS REAL` check accepts `'not-a-price'` (the cast
  is 0) and the float-equal pair `1000000000000.00000000` /
  `999999999999.99999999`. The API returns 422 for both. One
  sentence in `docs/demo-data.md` says the Pydantic validators are
  the authoritative rule on SQLite.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  No live market-data calls. Scoped black, isort, and flake8 passed.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1594 passed, 143 deselected, coverage 95.88%
  (3842 statements, 132 miss, 1080 branches, 55 partial).
  `app/repositories/price_bar_repository.py` is fully covered on
  that run, including the mismatch rollback. Local PostgreSQL
  16.15, `REQUIRE_POSTGRES=1`, and
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`
  -> 143 passed, 1594 deselected. The Actions run id is recorded
  on the pull request after both jobs are green. This commit is
  the behavior change, not a CI note.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-21 about 17:31 to 17:40.
- Next: the re-chain entry above. Agents do not merge.

## 2026-10-21 - Rebase price bars onto master as revision 0006

- Scope: rebase `cursor/price-bar-followups-85-5c38` onto
  `origin/master` `ad44969` (#89, after #87). The price migration
  is `0006_price_bar_numeric.py`, revision `0006`,
  `down_revision` `0003`. #90 is `0004` and #91 is `0005`. They
  merge before this file. The final re-chain sets `down_revision`
  to `0005`. `templates/`, `static/`, and `app/ui/` were not
  edited.
- Decisions: master already owns revision `0003` (unique ticker
  index). A second file also numbered `0003` would be a second
  Alembic head, and pull-request CI does not start on a conflict.
  `0006` revises `0003` for now, so `get_heads()` is `['0006']`.
  Upgrade, downgrade to `0002`, and upgrade again still pass on
  SQLite and PostgreSQL. The SQLite rebuild is still only
  `price_bars`. The migration still uses frozen literals and does
  not import the application.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  No live market-data calls. Scoped black, isort, and flake8 passed
  on the Python this change touches. CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1587 passed, 142 deselected, coverage 95.69%
  (3838 statements, 139 miss, 1076 branches, 57 partial).
  Local PostgreSQL 16.15, `REQUIRE_POSTGRES=1`, and
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`
  -> 142 passed, 1587 deselected. The Actions run id is recorded
  on the pull request after both jobs are green. This commit is
  the rebase and the renumber, not a CI note.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-21 about 17:13 to 17:20.
- Next: the owner reviews PR #94. Agents do not merge. After #90
  and #91 merge, set `down_revision` to `0005`.

## 2026-10-21 - QA round 1 on price bars (PR #94)

- Scope: QA round 1 on PR #94, head `8360ef8`, was not approved.
  Same branch `cursor/price-bar-followups-85-5c38`. The contract on
  both engines: the API never returns a price string different from
  the one it stored, and no read returns HTTP 500.
  `templates/`, `static/`, and `app/ui/` were not edited. The price
  migration is revision `0006` with `down_revision` `0003`. #90
  (`0004`) and #91 (`0005`) merge first. The final re-chain sets
  `down_revision` to `0005`.
- Decisions: `PriceAmount` is a SQLAlchemy `TypeDecorator`.
  `load_dialect_impl` uses `Numeric(20, 8)` on PostgreSQL and
  `TEXT` on SQLite. `process_bind_param` writes the canonical
  8-place string on SQLite and a `Decimal` on PostgreSQL.
  `process_result_value` parses that string back with `Decimal`.
  A cell that is not a decimal becomes `UnreadablePrice` instead
  of raising, because a raise during load aborts the whole SELECT.
  The repository logs the bar id and skips that row. The API also
  skips a row the response model rejects, so one bad bar cannot
  500 the series. `create` and `upsert_many` flush, read the row
  back, and compare the fixed-point strings before commit. A
  mismatch rolls the transaction back, so a failed write leaves
  no row. OHLC checks stay in the Pydantic model, which is the
  exact check. On SQLite the database check uses
  `CAST(column AS REAL)`, because a text comparison treats
  `'10' >= '9'` as false and would reject a valid candle. PostgreSQL
  compares the numeric columns. Revision 0002 had created those
  checks on FLOAT, and PostgreSQL kept `::double precision` after
  a type change, so upgrade drops the five OHLC checks and creates
  them again after the columns are numeric. The SQLite rebuild is
  `batch_alter_table` on `price_bars` only. `companies` is not
  rebuilt. The migration uses frozen literals and does not import
  the application. `Decimal('1e400')` makes `quantize` raise
  `InvalidOperation`, which is not a `ValueError`. That is caught
  and re-raised as `ValueError`, so the API returns 422. FastAPI's
  OpenAPI model types `maximum` as float, which turns
  `9223372036854775807` into `9.223372036854776e+18`. After FastAPI
  builds the document, the volume maximum is put back as that
  integer. After a fake refresh the default series is the 252
  `fake` bars. The demo-v2 fixture is returned only for
  `source=[IAC-DEMO-V2]`. `docs/demo-data.md` no longer says SQLite
  keeps a binary float.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  No live market-data calls. Scoped black, isort, and flake8 passed.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1542 passed, 137 deselected, coverage 95.88%
  (3728 statements, 130 miss, 1034 branches, 50 partial).
  Local PostgreSQL 16.15,
  `REQUIRE_POSTGRES=1`,
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`,
  and
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`
  -> 137 passed, 1542 deselected. The Actions run id is recorded
  on the pull request after both jobs are green. This commit does
  not exist only to note CI.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-21 about 16:38 to 17:00.
- Next: the owner reviews PR #94 again and merges with
  "Rebase and merge". Agents do not merge. After #90 and #91
  merge, set this migration's `down_revision` to `0005`.

## 2026-10-21 - Price bar follow-ups (#85)

Superseded for SQLite storage by the QA round 1 entry above.
The decimal note in this entry described numeric affinity before
that fix.

- Scope: follow-ups from PR #83, issue
  [#85](https://github.com/Waber/Investment-AI-Companion/issues/85).
  All five items. `templates/`, `static/`, and `app/ui/` were not
  edited.
- Base: `origin/master` `192c521`.
- Decisions: when `source` is omitted, the series is chosen from
  every bar of the instrument. The bar with the latest
  `retrieved_at` wins. A tie keeps the source name that sorts
  last. `from` and `to` run after that choice, so a date window
  cannot switch between the demo marker and a later `fake`
  refresh. A window that only contains the other source is `[]`.
  After a refresh the default source is `fake`. Pass
  `source=[IAC-DEMO-V2]` to read the demo series.
  `volume` is `StrictInt`. The integer `100` is stored. The
  string `"100"` is a validation error. An unknown `source`
  filter is HTTP 200 and `[]`.
  OHLC prices are `Decimal`. The columns are `Numeric(20, 8)`:
  12 digits before the decimal point and 8 after. A collector
  float becomes `Decimal(str(value))` (so `0.1` stays `0.1`),
  then half-even rounding to 8 places. FastAPI asks Pydantic for
  JSON mode, and Pydantic encodes `Decimal` as a string. The
  response uses fixed-point, so `0.00000001` is not `1E-8`. A
  JSON number or a numeric string is accepted on input. The price
  migration is `0006` and revises `0003` (the ticker index from
  #87). #90 is `0004` and #91 is `0005`. They merge first, and the
  final re-chain sets `down_revision` to `0005`. SQLite declares
  the same numeric type; its numeric affinity stores a real.
  PostgreSQL stores an
  exact numeric.
  `docs/demo-data.md` no longer says the `/ui` badge matches
  `[IAC-DEMO-V1]` only. The badge matches a description that
  starts with `[IAC-DEMO-`.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1537 passed, 135 deselected, coverage 96.31%
  (3611 statements, 113 miss, 996 branches, 41 partial).
  Local PostgreSQL 16.15,
  `REQUIRE_POSTGRES=1`,
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`,
  and
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`
  -> 135 passed, 1537 deselected. Scoped black, isort, and
  flake8 passed on the Python this change owns. No live
  market-data calls.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-21 about 16:05 to 16:28.
- Next: the owner reviews the pull request and merges with
  "Rebase and merge". Agents do not merge. After #90 and #91
  merge, set this migration's `down_revision` to `0005`.

## 2026-10-21 - Re-chain notes and theses to revision 0005

- Scope: Raul approved
  [PR #91](https://github.com/Waber/Investment-AI-Companion/pull/91).
  #87, #89, and #90 have merged. This rebases
  `cursor/notes-theses-backend-b69b` onto `origin/master`
  `cb9e47c` and renames the notes migration. No HTTP API.
  `templates/`, `static/`, and `app/ui/` were not edited.
- Decisions: `0005_notes_and_theses.py` revises `0004`
  (watchlist). The file used to be `0033`. Lengths, the status
  CHECK, and `DateTime(timezone=True)` are literals. The file
  does not import application or script code.
  `CompanyNotFoundError` is the class already on master.
  `ResearchStorageError` subclasses `RuntimeError`, so an
  `except ValueError` does not swallow it. Notes tests
  downgrade to `0004` and upgrade again. `price_bars` and
  `watchlist_items` stay. Databases that stamp `0002` or
  `0003` and upgrade drop `notes` and `theses` first, the same
  way `0004` drops `watchlist_items`. The notes feature entry
  keeps a blank line before the next heading.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1687 passed, 208 deselected, coverage 96.49% (4128
  statements, 121 miss, 1118 branches, 47 partial).
  PostgreSQL, local 16, database `investment_test`,
  `REQUIRE_POSTGRES=1` and
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`
  -> 208 passed, 1687 deselected. Scoped black, isort, and
  flake8 passed on the Python this change owns. No live
  market-data calls. GitHub Actions is recorded in the pull
  request, not in a later commit.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-21 about 17:21 to 17:35.
- Next: the owner reviews the re-chained pull request. It still
  says Refs #33. Agents do not merge.

## 2026-10-21 - Code review on notes and theses (#33)

- Scope: code review of
  [PR #91](https://github.com/Waber/Investment-AI-Companion/pull/91)
  at `7b9fb07`. Same branch. No HTTP API. `templates/`,
  `static/`, and `app/ui/` were not edited. The branch was
  rebased onto `origin/master` `192c521` (price bars, revision
  `0002`).
- Decisions: `Note` and `Thesis` are output models. They do not
  strip text or apply `max_length`, so one stored NUL or a
  201-character title does not fail `list_for_company`. Write
  models still validate. The migration copies the lengths and
  the status CHECK as literals (`String(10000)`, `String(200)`,
  `String(5000)`, `String(6)`, `status IN ('active', 'closed')`).
  It does not import `app.models.research`. At this review the
  file was still `0033` with `down_revision` `0002`, because
  leaving it on `0001` made two Alembic heads. The re-chain
  entry above moved that file to `0005`.
  A title strips format characters at the edges and rejects bidi
  controls (U+202A–E, U+2066–9, U+200E, U+200F, U+061C) and
  categories Zl and Zp. A multi-line field turns `\\r\\n` and
  `\\r` into `\\n` before the length check. `created_at` and
  `updated_at` are NOT NULL. Inserts use the server default.
  Updates set `updated_at` in the repository in UTC. The columns
  have no `onupdate`. `update`, `delete`, and `set_status` roll
  back on `SQLAlchemyError` and raise `ResearchStorageError`
  after the handler, with no driver text. There is no shared
  storage error on this branch. `ThesisStatus` is a `StrEnum`,
  so `str(ThesisStatus.ACTIVE)` is `active`. Create and update
  models use `extra='forbid'`.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1586 passed, 189 deselected, coverage 96.59%.
  PostgreSQL, local 16, database `investment_test`,
  `REQUIRE_POSTGRES=1` and
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`
  -> 189 passed, 1586 deselected. Scoped black, isort, and
  flake8 passed on the Python this change owns. No live
  market-data calls.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-21 about 16:08 to 16:20.
- Next: the owner sends PR #91 back to code review. Agents do
  not merge.

## 2026-10-21 - QA on notes and theses, blank format characters (#33)

- Scope: QA on
  [PR #91](https://github.com/Waber/Investment-AI-Companion/pull/91),
  two items, before code review. Same branch
  `cursor/notes-theses-backend-b69b`. The revision file was
  still `0033` at this QA pass. The re-chain entry above
  renamed it. No HTTP API.
  `templates/`, `static/`, and `app/ui/` were not edited.
- Decisions: a title, body, or thesis-breakers value is blank
  when every character is whitespace or Unicode category Cf
  (U+200B, U+FEFF, and the joiners). `str.strip` only removes
  whitespace at the ends, so a space between two format
  characters would otherwise be stored. That value now raises
  `ValidationError` for a title or a body, and thesis-breakers
  become `""`. A letter with a format character beside it is
  kept, same as `normalize_name`. The migration tests call
  Alembic `compare_metadata` after `create_all`, a drop of
  `notes` and `theses`, stamp `0001`, and upgrade, and assert
  the diff is empty. That is the watchlist autogenerate check.
  A legacy companies table would still diff, so the legacy
  upgrade test does not use the full compare. No second
  revision file is rendered. PostgreSQL uses the scratch schema
  `notes_autogen`.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1535 passed, 174 deselected, coverage 96.38%.
  PostgreSQL, local 16, database `investment_test`,
  `REQUIRE_POSTGRES=1` and
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`
  -> 174 passed, 1535 deselected. Scoped black, isort, and
  flake8 passed on the Python this change owns. No live
  market-data calls.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-21 about 15:55 to 16:02.
- Next: the owner sends PR #91 to code review. Agents do not
  merge. The re-chain entry above is the later link onto
  master.

## 2026-10-21 - Notes and investment theses, backend (#33)

- Scope: the backend of
  [#33](https://github.com/Waber/Investment-AI-Companion/issues/33).
  Notes and investment theses for one company: SQLAlchemy tables,
  Pydantic models, repositories, and Alembic revision `0033`.
  No HTTP API. `templates/`, `static/`, and `app/ui/` were not
  edited. The UI stays with the Frontend Developer. The pull
  request says Refs #33.
- Decisions: constants, `ThesisStatus`, and the Pydantic models
  live in `app.models.research`. Tables `notes` and `theses` are
  in `app.models.database_models`. Both foreign keys are
  `ON DELETE CASCADE` and indexed on `company_id`. Every
  repository read and write includes `company_id`, so another
  company's id looks missing. `create` checks that the company
  exists and raises `CompanyNotFoundError` (`LookupError`, not
  `ValueError`) instead of `IntegrityError`, including when
  SQLite foreign keys are off. Text is stripped before the
  length check. A title rejects every Unicode Cc character. A
  body and thesis-breakers allow newline, carriage return, and
  tab only. Thesis-breakers may be empty. Status is `active` or
  `closed`, with a CHECK constraint. `updated_at` moves when a
  field changes. An empty update, or `set_status` to the status
  already stored, leaves `updated_at` alone. The revision file
  was `0033` and followed master's head `0001` at that time. It
  was not named `0002`, because open PRs #83 and #87 each added
  a revision with that id, and the #32 watchlist migration
  added one too. The re-chain entry above is the later link.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1529 passed, 168 deselected, coverage 96.37%.
  PostgreSQL, local 16, database `investment_test`,
  `REQUIRE_POSTGRES=1` and
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`
  -> 168 passed, 1529 deselected. Scoped black, isort, and
  flake8 passed on the Python this change owns. No live
  market-data calls.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-21 about 15:27 to 15:48.
- Next: the owner reviews the pull request. The Frontend
  Developer can build the `/ui` forms on the interface in the
  pull request body. Agents do not merge. The re-chain entry
  above links the notes revision after those merges.

## 2026-10-21 - Rebase the watchlist branch onto ad44969

- Scope: pull request #89 merged, so `origin/master` is
  `ad44969`. The watchlist branch is rebased onto that commit.
  Revision `0004` still revises `0003`. No watchlist behavior
  changed. `app/ui/` was not edited by this rebase.
- Decisions: the rebase had no conflicts. #89's journal and
  work-state entries stay below the watchlist entries. The
  migration file is still `0004_watchlist_items.py`, with the
  literals `0004` and `0003`.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1629 passed, 153 deselected, coverage 96.22% (3824
  statements, 121 miss, 1050 branches, 47 partial).
  `REQUIRE_POSTGRES=1` and
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`
  with `-m integration` -> 153 passed, 1629 deselected.
  No live market-data calls. GitHub Actions is recorded in the
  pull request, not in a later commit.
- AI model: Grok 4.7. Account usage was not available as a
  number in this session.
- Time tracking (UTC): 2026-10-21 about 17:13 to 17:20.
- Next: the owner reviews the updated pull request. It still
  says Refs #32. Agents do not merge.

## 2026-10-21 - Re-chain the watchlist migration to 0004

- Scope: pull request #87 merged, so `origin/master` is
  `cb6ba64`. The watchlist revision moves from `0003` to
  `0004` and revises `0003` (the companies ticker unique
  revision). No other behavior changed. `app/ui/` was not
  edited.
- Decisions: the file is `0004_watchlist_items.py`. `revision`
  and `down_revision` are the literals `0004` and `0003`.
  The migration does not import application or script code.
  `ScriptDirectory.get_heads()` has length 1. Watchlist
  upgrade tests downgrade to `0003`. The ticker tests that
  stamp `0002` and upgrade to head drop `watchlist_items`
  first, because `create_all` already built that table and
  revision `0004` creates it.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1612 passed, 153 deselected, coverage 96.23% (3796
  statements, 120 miss, 1032 branches, 46 partial).
  `REQUIRE_POSTGRES=1` and
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`
  with `-m integration` -> 153 passed, 1612 deselected.
  Upgrade, downgrade to `0003`, and upgrade again passed on
  SQLite and PostgreSQL. No live market-data calls. GitHub
  Actions is recorded in the pull request, not in a later
  commit.
- AI model: Grok 4.7. Account usage was not available as a
  number in this session.
- Time tracking (UTC): 2026-10-21 about 16:53 to 17:00.
- Next: the owner reviews the updated pull request. It still
  says Refs #32. Agents do not merge.

## 2026-10-21 - Code review on the watchlist (PR #90)

- Scope: the Code Reviewer's changes on `059d28a`, on the same
  branch. Rebased onto `origin/master` `192c521` after pull
  request #83 merged the price bars revision. `app/ui/` was not
  edited. `company.normalize_name` was not changed.
- Decisions: Alembic revision `0003` (`0003_watchlist_items.py`)
  revises `0002`. `ScriptDirectory.get_heads()` has length 1.
  The integration `TRUNCATE` lists `watchlist_items` and
  `price_bars`. `WatchlistRepository.add` inserts inside
  `begin_nested`, a SAVEPOINT, so a unique-constraint failure
  undoes only that insert. Earlier flushed work in the session
  stays. A successful insert still commits. The POST docstring
  and the OpenAPI 200 response say a repeat keeps the original
  label. `Settings.WATCHLIST_STALE_PRICE_DAYS` is `Field(7, ge=1)`.
  The field name is the environment variable, same as the other
  settings. Labels also reject U+061C, U+206A–U+206F, and the tag
  characters U+E0000–U+E007F. That set stays in
  `app/models/watchlist.py`. `app/ui/form_fields.py` keeps its
  smaller bidi set, so company-name checks stay as they are.
  One shared constant would either reject more names on the form
  or require an `app/ui/` edit for the smaller set. `POST
  /api/v1/watchlist` without a slash is 307. The HTTP errors in
  `app/api/watchlist.py` are raised with nothing chained, so they
  no longer use `from None`. The repository still raises after
  its handler. Open pull request #87 has its own unmerged
  revision `0003`. Whichever of #90 and #87 merges second has to
  re-chain.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1584 passed, 148 deselected, coverage 96.44% (3714
  statements, 112 miss, 1008 branches, 40 partial).
  `REQUIRE_POSTGRES=1` and
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`
  with `-m integration` -> 148 passed, 1584 deselected.
  Scoped black, isort, and flake8 passed on the Python this
  change owns. No live market-data calls. GitHub Actions is
  recorded in the pull request, not in a later commit.
- AI model: Grok 4.7. Account usage was not available as a
  number in this session.
- Time tracking (UTC): 2026-10-21 about 16:08 to 16:20.
- Next: the owner reviews the updated pull request. It still
  says Refs #32. Agents do not merge.

## 2026-10-21 - Watchlist review nits (PR #90)

- Scope: Security Engineer nits and QA lows on the watchlist
  backend, same branch as issue #32. `app/ui/` was not edited.
  `company.normalize_name` was not changed. The page, the stale
  marker, and the PL/EN strings stay with the Frontend Developer.
- Decisions: after `strip`, a watchlist label with a Unicode Cc
  character (NUL included, so `A\x00B` too) or a bidi control
  (U+202A–U+202E, U+2066–U+2069, U+200E, U+200F) is a
  `ValidationError`, which the API returns as 422. A label made
  only of whitespace or Cf characters (U+200B, U+FEFF, and the
  like) is null. A Cf character next to a letter is kept. U+200E
  and U+200F are Cf, and they are rejected rather than stored as
  null. The rule lives on `clean_watchlist_label` in
  `app/models/watchlist.py`. `WatchlistRepository.add` returns
  `(row, created)`. The request that loses the unique constraint
  is HTTP 200. A company deleted between the existence check and
  the insert is `CompanyNotFoundError` (a `LookupError` with
  `company_id`, the same shape as pull request #91). The API
  returns 404 `Company not found`. Any other integrity failure
  stays `WatchlistStorageError` and HTTP 500. Both errors are
  raised after the handler, so `__context__` is `None` and the
  driver text is not chained. `watchlist_stale_price_days` is
  `Field(7, ge=1)`, so 0 and -1 are rejected. `DELETE` takes
  `company_id: int = Path(gt=0)`, so 0 and -1 are 422. `POST`
  sets `responses=` for 201, 200, and 404. A `text/plain` body,
  a form body, and a body with no `Content-Type` are 422.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1529 passed, 137 deselected, coverage 96.23% (3228
  statements, 104 miss, 858 branches, 36 partial).
  `REQUIRE_POSTGRES=1` and
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`
  with `-m integration` -> 137 passed, 1529 deselected.
  Scoped black, isort, and flake8 passed on the Python this
  change owns. No live market-data calls. GitHub Actions is
  recorded in the pull request, not in a later commit.
- AI model: Grok 4.7. Account usage was not available as a
  number in this session.
- Time tracking (UTC): 2026-10-21 about 15:56 to 16:05.
- Next: the owner reviews the updated pull request. It still
  says Refs #32. After #83 or #87 merges, rebase this branch
  and point the migration at the new head. Agents do not merge.

## 2026-10-21 - Watchlist backend (issue #32)

- Scope: the backend of
  [#32](https://github.com/Waber/Investment-AI-Companion/issues/32).
  `WatchlistItemDB` stores one row per company. The read model is
  `WatchlistItem` and the write model is `WatchlistItemCreate`.
  `WatchlistRepository` adds, removes, and lists those rows.
  `Settings.watchlist_stale_price_days` defaults to 7. The HTTP
  routes are `GET` and `POST /api/v1/watchlist/` and
  `DELETE /api/v1/watchlist/{company_id}`. The page, the stale
  marker, and the PL/EN strings stay with the Frontend Developer.
  `templates/`, `static/`, and `app/ui/` were not edited.
- Decisions: `company_id` references `companies.id` with
  `ON DELETE CASCADE`. `CompanyDB.watchlist_item` sets
  `passive_deletes` and `uselist=False`, because the unique
  constraint allows one row. `added_at` uses `UTCDateTime`.
  `label` is a nullable string of at most 80 characters; a blank
  label is stored as null. Adding a company that is already
  listed returns that row and does not change the label. If two
  adds pass the first lookup together, the unique constraint
  fires, the loser rolls back, and the stored row is returned.
  Any other constraint failure is `WatchlistStorageError`, raised
  after the handler so `__context__` is `None`. An unknown
  company is HTTP 404. The first add is 201 and a repeat is 200.
  Revision `0002` revises `0001`, which is master's head. Pull
  requests #83 and #87 also add a revision `0002`. This one must
  be rebased and re-chained after whichever of those merges
  first. The filename slug stays `watchlist_items`.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1500 passed, 134 deselected, coverage 96.19% (3201
  statements, 104 miss, 846 branches, 36 partial).
  `REQUIRE_POSTGRES=1` and
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`
  with `-m integration` -> 134 passed, 1500 deselected.
  Scoped black, isort, and flake8 passed on the Python this
  change owns. No live market-data calls. GitHub Actions is
  recorded in the pull request, not in a later commit.
- AI model: Grok 4.7. Account usage was not available as a
  number in this session. The user resumed after a reset.
- Time tracking (UTC): 2026-10-21 about 15:27 to 15:45.
- Next: the owner reviews the pull request. It says Refs #32
  and stays open, because the watchlist page is still the
  Frontend Developer's work. After #83 or #87 merges, rebase
  this branch and point the migration at the new head. Agents
  do not merge.

## 2026-10-21 - Code review on the ticker check, rebased onto price bars

- Scope: Code Reviewer on pull request #87 at `1ba6616`.
  Same branch `cursor/ticker-unique-and-alembic-0e9d`, rebased
  onto `origin/master` `192c521` after #83. The ticker revision
  is `0003` with `down_revision` `0002` (`price_bars`). Pull
  request #90 may merge first and take `0003`. This branch keeps
  `0003` until then so it has one Alembic head, and it is
  re-chained to the next free number after whatever merges ahead.
  `app/ui/forms.py` was not edited.
- Decisions: `main` builds the engine inside the `try`.
  `ArgumentError` and any other `SQLAlchemyError` each print one
  fixed line and exit 1. The return is after the handler, and the
  line does not include the URL or the driver text. `DATABASE_URL`
  is accepted when no argument is passed. An argument wins. The
  README recommends the environment variable because an argument
  can appear in `ps` and in shell history. After `strip`,
  `normalize_name` rejects Unicode category `Cc` anywhere, including
  a leading, trailing, or middle NUL and DEL. A format character
  beside a letter is kept. A provider name with a newline is 502
  and is not stored. The duplicate check trims spaces, tabs,
  carriage returns, and line feeds on both SQLite (`TRIM` with a
  character set) and PostgreSQL (`BTRIM`) before `UPPER`. The
  stored text is quoted and the rows are not rewritten. Revision
  `0003` adds `uq_companies_ticker` with `op.create_index`, not a
  `batch_alter_table` rebuild. With foreign keys on, a rebuild
  would drop `companies` and cascade-delete `price_bars`.
  `CompanyDB` keeps the `price_bars` relationship and the ticker
  index.
- Verification: no `.env`. `SECRET_KEY` comes from
  `tests/conftest.py`. SQLite CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  : 1556 passed, 139 deselected, coverage 96.10%. PostgreSQL
  `REQUIRE_POSTGRES=1` and
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`
  with `-m integration`: 139 passed, 1556 deselected. Scoped
  black and flake8 passed on the Python this change touches.
  PostgreSQL 16.15. GitHub Actions for this head is recorded on
  the pull request, not in a later docs-only commit.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-21 about 16:01 to 16:16.
- Next: push with `--force-with-lease`. The owner reviews pull
  request #87. If #90 merges first, re-chain this revision.
  Agents do not merge.

## 2026-10-21 - QA follow-up: ticker collisions ignore case and surrounding spaces

- Scope: QA on pull request #87 at `d50ce1c`, pass with findings.
  Same branch `cursor/ticker-unique-and-alembic-0e9d`. Rebased
  onto `origin/master` `192c521` after #83 merged.
  The ticker revision is `0003`, with `down_revision` `0002`
  (the `price_bars` migration from #83). Pull request #90 may
  merge first and take `0003`; this branch is re-chained after
  that.
  `templates/`, `static/`, and `app/ui/` were not edited.
- Decisions: the migration and
  `scripts.check_duplicate_tickers` group by
  `UPPER(TRIM(ticker))`, which is the application's `strip` and
  `upper`. `aapl` and `AAPL ` are one collision. The message quotes
  the stored text, including the trailing space. The rows are not
  rewritten. An `OperationalError` (database unreachable, or the
  read failing) prints one line to stderr and exits 1, with no
  traceback. A missing `companies` table found by the inspector is
  still exit 2. `alembic.script.ScriptDirectory.get_heads()` is
  asserted to have length 1, so this branch stays a single head
  until the later renumber.
- Verification: no `.env`. `SECRET_KEY` comes from
  `tests/conftest.py`. SQLite CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  : 1503 passed, 128 deselected, coverage 95.96%. PostgreSQL
  `REQUIRE_POSTGRES=1` and
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`
  with `-m integration`: 128 passed, 1503 deselected. Scoped
  black, isort, and flake8 passed on the Python this change
  touches. PostgreSQL 16.15. GitHub Actions for this commit is
  recorded on the pull request when it finishes, not in a later
  docs-only commit.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-21 about 15:27 to 15:32.
- Next: push this commit. Do not renumber until #83 is on master.
  The owner reviews pull request #87. Agents do not merge.

## 2026-10-21 - Ticker uniqueness, shared name rule, and Alembic follow-ups

- Scope: issues #79 and #8 together, with the `normalize_name`
  hardening from #86 and two Code Reviewer notes from #75.
  Branch `cursor/ticker-unique-and-alembic-0e9d` from
  `origin/master` `6d45f01`. `templates/`, `static/`, and
  `app/ui/` were not edited.
- Decisions: after `strip`, a company name must contain one
  character that is not whitespace and not Unicode category C*
  (`Cc`, `Cf`, `Co`, `Cn`, `Cs`). `'\u200b \u200b'`, a lone NUL,
  and U+E000 are rejected. A letter with a format character
  beside it is kept. Create and update share one duplicate rule:
  ticker and a present ISIN are unique, and the same name may be
  stored on another ticker (`BRK.A` / `BRK.B`).
  `DuplicateTickerError` and `DuplicateIsinError` are unchanged
  and are still raised after the integrity handler so
  `__context__` is `None`. Revision `0003` runs
  `scripts.check_duplicate_tickers` first. Repeated tickers are
  named and the rows are not changed. It then creates the unique
  index `uq_companies_ticker`. That is an index, not a
  `UNIQUE CONSTRAINT`, because SQLite cannot add a constraint
  while `financial_metrics` points at `companies`. The model uses
  the same index, and autogenerate is empty on SQLite and
  PostgreSQL. Money columns stay `Float`. Demo and seed tickers
  already match the write pattern, so there is no ticker-cleanup
  migration. `0001_baseline.py` for instruments, prices, and
  ETF/ETC attributes is not written: those tables are not on
  master. README and `docs/api-demo.md` no longer say to add the
  columns by hand. That would skip the CHECK, `uq_companies_isin`,
  and `alembic stamp head`. Migration tests call
  `require_company_instrument_columns` after `upgrade_head`.
- UI impact, not edited here: `/ui` create and edit call the
  repository, so saving a shared name with a different ticker now
  succeeds. The form still has a name-duplicate branch for an
  error raised while another row has that name.
- Verification: no `.env`, `DATABASE_URL` unset except the test
  harness. `SECRET_KEY` comes from `tests/conftest.py`. SQLite CI
  command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  on this commit's code: 1481 passed, 127 deselected, coverage
  95.96%. PostgreSQL `REQUIRE_POSTGRES=1` and
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`
  with `-m integration`: 127 passed, 1481 deselected. The name
  commit was 1465 passed / 124 deselected / 96.06% and 124
  PostgreSQL passed. The name-rule commit was 1467 passed / 124
  deselected / 95.97% and 124 PostgreSQL passed. Scoped black,
  isort, and flake8 passed on the Python this change adds.
  PostgreSQL 16.15. GitHub Actions is recorded on the pull
  request, not in a later docs-only commit.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-21 about 08:06 to 08:30.
- Next: the owner reviews the pull request. It says Closes #79,
  Refs #8, and Refs #86. Agents do not merge.

## 2026-10-21 - Code review round 1 on price bars (PR #83)

- Scope: the review on `e346725`. Volume is BIGINT so a session
  above 2,147,483,647 is stored on PostgreSQL. The price list
  defaults to one source. A failed insert that leaves no row is a
  generic constraint error, not "already exists". A collector
  `ValidationError` is HTTP 502 before the `ValueError` handler.
  Deleting a company cascades to its bars. The redundant indexes
  on `id` and `instrument_id` are gone. The fixture test pins
  1777 bars. `templates/`, `static/`, and `app/ui/` were not
  edited. Float prices stay. The `/ui` badge stays with the
  Frontend Developer. This entry also records the green run for
  `e346725`, which the previous note had left on `03952d9`.
- Decisions: `volume` is `BigInteger` in the model and in Alembic
  `0002` (edited in place; the revision is unreleased). The
  Pydantic field rejects a volume above `2**63 - 1`. The default
  list keeps the source with the latest `retrieved_at` in the
  date range. A tie keeps the source name that sorts last, so
  `fake` wins a tie with `[IAC-DEMO-V2]`. Pass `source` to read
  the other series. The seeder requests `source=[IAC-DEMO-V2]`
  so a newer refresh does not hide the rows it skips. After
  rollback, `get_by_key` on the keys this call tried to insert
  decides the message: a row means the duplicate sentence, no
  row means "Price bar could not be stored". Both raises are
  outside the handler, so `__context__` is `None`. The collector
  `ValidationError` uses the fixed provider sentence and is not
  logged with the provider's values. `passive_deletes=True` and
  `ON DELETE CASCADE` let the database remove bars. The unique
  key already indexes `instrument_id`, and the primary key
  already indexes `id`.
- Verification: no `.env`. `DATABASE_URL` and `SECRET_KEY` unset.
  SQLite CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1510 passed, 134 deselected, coverage 96.30%
  (3558 statements, 112 miss, 978 branches, 40 partial).
  PostgreSQL, `REQUIRE_POSTGRES=1` and
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`,
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`:
  134 passed, 1510 deselected. Scoped black, isort, and flake8
  passed on the Python this change owns. No live market-data
  call.
- AI model: Grok 4.7. Account usage was not available in this
  session, so no usage percent was recorded.
- Time tracking (UTC): 2026-10-21 about 07:48 to 07:57.
- Next: one push of this commit. No follow-up commit to record
  the Actions run. PR #83 still says Refs #27 and stays
  unmerged. Agents do not merge.

## 2026-10-21 - QA round 1 on price bars (PR #83)

- Scope: the candle bounds on a stored bar. `PriceBarCreate`
  rejects a high below the open or the close, a low above the
  open or the close, a high below the low, and a negative volume,
  when those values are present. The same six checks are
  `CheckConstraint`s on `PriceBarDB` and in Alembic `0002`.
  Upgrade and downgrade are tested on SQLite and PostgreSQL.
  The duplicate-bar `ValueError` is raised after the
  `IntegrityError` handler. The earlier journal line for the
  PostgreSQL command now matches CI: no coverage flags and no
  `--cov-fail-under=80`. `docs/product-requirements.md` says the
  demo fixture is weekly (Mondays). `templates/`, `static/`, and
  `app/ui/` were not edited. Float prices stay. The `/ui` badge
  (M2) stays with the Frontend Developer.
- Decisions: a missing price is not compared. Equal prices are a
  valid flat session. Volume zero is valid. A SQL check passes
  when the expression is null, so each constraint is a single
  comparison and a null side does not hide another comparison.
  Downgrade drops `price_bars`, and the checks go with the table.
  `create` and `upsert_many` store the driver error inside the
  `except` and raise `ValueError(...) from None` after it, so
  `__context__` and `__cause__` are both `None`. The fixed
  sentence is unchanged.
- Verification: no `.env`. `DATABASE_URL` and `SECRET_KEY` unset.
  SQLite CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1503 passed, 131 deselected, coverage 96.30%
  (3522 statements, 111 miss, 962 branches, 39 partial).
  PostgreSQL, `REQUIRE_POSTGRES=1` and
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`,
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`:
  131 passed, 1503 deselected. Scoped black, isort, and flake8
  passed on the Python this change owns. No live market-data
  call. GitHub Actions on `03952d9` succeeded
  ([run 39563380255](https://github.com/Waber/Investment-AI-Companion/actions/runs/39563380255)):
  SQLite job 119099695642, 1503 passed, 131 deselected, coverage
  96.30%. PostgreSQL job 119099695294, 131 passed, 1503
  deselected. The docs commit `e346725` succeeded
  ([run 39563741560](https://github.com/Waber/Investment-AI-Companion/actions/runs/39563741560)):
  SQLite job 119100911310, 1503 passed, 131 deselected, coverage
  96.30%. PostgreSQL job 119100911030, 131 passed, 1503
  deselected.
- AI model: Grok 4.7. Account usage was not available in this
  session, so no usage percent was recorded.
- Time tracking (UTC): 2026-10-21 about 07:32 to 07:41.
- Next: the owner reviews
  [PR #83](https://github.com/Waber/Investment-AI-Companion/pull/83).
  It says Refs #27 and stays unmerged. Agents do not merge. The
  Frontend Developer still owns the `/ui` badge for
  `[IAC-DEMO-V2]`.


## 2026-10-21 - Price bars and the demo-v2 fixture (Refs #27)

- Scope: store daily-or-weekly session prices with provenance, query
  them by an inclusive date range, refresh them from the configured
  collector, and seed `fixtures/demo-v2.json` through the existing
  D2 command. Backend only. `templates/`, `static/`, and `app/ui/`
  were not edited. ETF and ETC attribute columns stay on #28.
  Issue #27 stays open: this pull request says Refs #27. A code
  reviewer's approval is one of the issue's acceptance checks, and
  the `/ui` synthetic badge still matches only `[IAC-DEMO-V1]`.
- Decisions: `PriceBarDB.instrument_id` points at `companies.id`.
  The companies table was not renamed. The API path is
  `/api/v1/instruments/{id}/prices`, which is the name in the
  issue. The unique key is instrument, session date, and source,
  so a seeded `[IAC-DEMO-V2]` bar and a later `fake` refresh of
  the same date both remain. A second refresh of the same source
  updates that row. OHLC and volume stay null when the provider
  omits them. They are never stored as zero. A high below the low
  is rejected. The list has no pages: one response is the whole
  range. `from` after `to` is 422. A missing instrument is 404.
  An instrument with no bars is 200 and `[]`. Refresh uses
  `get_collector()`. Provider failures are HTTP 502 with a fixed
  sentence. The log records the exception class and the ticker,
  not the provider's text. The collector's bars have no currency,
  so refresh stores the instrument's currency, or `USD` when that
  field is null. `POST` of one bar exists so the HTTP seeder can
  insert. A duplicate key is 400 with a fixed sentence. The
  seeder never updates or deletes. Alembic `0002` creates
  `price_bars` after `0001`. `create_all` databases should be
  stamped, not upgraded. The fixture is weekly Mondays from
  2022-10-03 through 2026-09-28 (about four years). `DEMO_PL_EMPTY`
  has no prices. `DEMO_JP_STABLE` ends on 2024-09-30, so it is
  stale against `as_of` 2026-09-30. Currencies include PLN, USD,
  EUR, and JPY. Every company description and every fixture price
  source is `[IAC-DEMO-V2]`. Descriptions say the series is
  synthetic and not market data. They do not say buy or sell.
  `seed_demo` still defaults to demo-v1. `scripts/run_demo.py`
  loads demo-v2. The fake collector still reads demo-v1, so a
  refresh of `DEMO_ETF_GPW` or `DEMO_ETC_SILVER` finds no series.
  `DEMO_ETF_WORLD` and `DEMO_ETC_GOLD` are in the fake profiles.
- Verification: no `.env`. `DATABASE_URL` and `SECRET_KEY` unset.
  SQLite CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1491 passed, 124 deselected, coverage 96.26%
  (3503 statements, 111 miss, 940 branches, 39 partial).
  PostgreSQL, `REQUIRE_POSTGRES=1` and
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`,
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`:
  124 passed, 1491 deselected.
  Scoped black, isort, and flake8 passed on the Python this
  change owns. Tests use the in-memory client, `FakeCollector`,
  and stubs. No live market-data call. GitHub Actions on
  `533e2bd` succeeded
  ([run 39560060518](https://github.com/Waber/Investment-AI-Companion/actions/runs/39560060518)):
  SQLite job 119088883697, 1491 passed, 124 deselected, coverage
  96.26%. PostgreSQL job 119088883999, 124 passed, 1491
  deselected.
- AI model: Grok 4.7. Account usage was not available in this
  session, so no usage percent was recorded.
- Time tracking (UTC): 2026-10-21 about 06:46 to 07:13.
- Next: the owner reviews
  [PR #83](https://github.com/Waber/Investment-AI-Companion/pull/83).
  It says Refs #27 and stays unmerged. Agents do not merge. The
  Frontend Developer still owns the `/ui` badge for
  `[IAC-DEMO-V2]`.

## 2026-10-21 - QA fixes for the instrument-type select (#34, part)

- Scope: QA on PR #89 at `ce730e8`, same branch
  `cursor/ui-instrument-type-select`. Rebased onto
  `origin/master` `a21d912`. PR #87 is still open, so
  `docs/development-journal.md` and `docs/work-state.md`
  had nothing to merge. Frontend only. Models, schema,
  migrations, repositories, services, collectors, scoring,
  and AI adapters were not changed.
- Decisions: a failed edit that omits `instrument_type`,
  or posts only spaces, copies the stored column into the
  values before the form is rendered again. The select
  then keeps ETF selected, so fixing the ticker does not
  store STOCK. A posted type, including an unknown one,
  stays as sent. `instrument_type_for_payload` returns a
  control character unchanged, before `strip`, matching
  `normalize_instrument_type`. `ETF` plus a newline is
  422 and inserts no row. `etf` and ` ETF ` still store
  ETF. Spaces are omitted: create uses STOCK, and an edit
  leaves the column. The list and the detail page no
  longer have a missing-data branch for the type. The
  CHECK constraint and the STOCK default make that cell
  unreachable, and coverage stayed above the 80% gate.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY`
  unset. CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1500 passed, 124 deselected, coverage 96.07%. Scoped
  black, isort, and flake8 passed on the touched Python.
  PostgreSQL was not run locally. The two bug tests failed
  before the fix: the edit 422 selected STOCK, and
  `ETF\n` answered 303.
- AI model: Grok 4.7. Account usage was not readable as a
  percentage in this session.
- Time tracking (UTC): 2026-10-21 about 15:50 to 15:58.
- Next: this commit is pushed to PR #89 with
  `--force-with-lease`. Wait for both GitHub Actions jobs.
  The owner reviews. Agents do not merge.

## 2026-10-21 - Instrument type on the company forms (#34, part)

- Scope: the instrument-type control from
  [#34](https://github.com/Waber/Investment-AI-Companion/issues/34).
  Create and edit under `/ui` gain a select. The list and the
  detail page show the stored type. Models, schema, migrations,
  repositories, services, collectors, scoring, and AI adapters
  were not changed. ETF/ETC attribute columns and `source=manual`
  stay blocked on #28.
- Decisions: the option values are `InstrumentType`
  (`STOCK`, `ETF`, `ETC`). The visible words are the existing
  catalog keys `type.stock`, `type.etf`, and `type.etc`
  ("akcja" / "stock", and the abbreviations ETF and ETC). The
  label is the same `field.type` string the detail page uses,
  tied to the select with `for` and `id`. A blank post omits
  the key. Create then uses the `CompanyCreate` default
  `STOCK`. Update leaves the stored column, because
  `CompanyUpdate` rejects an explicit null. An unknown value
  is a 422 on that select (`aria-invalid`, the localized
  sentence, and the posted text kept as an extra option so a
  resubmit does not silently become STOCK). Jinja escapes that
  text. `to_instrument` maps the column to the lowercase
  catalog id the list filter already compares. A missing or
  unknown stored value is `None`, and the template shows the
  missing-data sentence instead of calling the row a stock.
  The same-origin check is the existing router dependency.
  No new disclaimer copy.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY`
  unset. CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1494 passed, 124 deselected, coverage 96.10%. Scoped
  black, isort, and flake8 passed on the touched Python.
  PostgreSQL was not run locally. In the browser on
  `127.0.0.1:8765`: the Polish create form labeled the select
  "Typ" with "akcja" selected; saving ETF showed ETF on the
  detail page; the English edit form kept ETF selected under
  "Type"; changing it to ETC showed ETC on the list and in
  the type filter.
- AI model: Grok 4.7. Account usage was not readable as a
  percentage in this session.
- Time tracking (UTC): 2026-10-21 about 15:26 to 15:35.
- Next: open the pull request against master. It says Refs
  #34 and stays unmerged. The owner reviews it. Agents do
  not merge.

## 2026-10-21 - Demo source comes from the marker token

- Scope: QA on PR #84, one low finding, before code review.
  `DEMO_SOURCE` was the literal `demo-v1`, so a V2 row showed
  that label. The badge check is unchanged: `to_instrument`
  still uses a case-sensitive `startswith` on
  `company.description`, with no strip. The source is now the
  token between `[IAC-DEMO-` and the next `]`, lowercased, and
  only when that token is 1 to 16 ASCII letters or digits.
  `[IAC-DEMO-V2]` shows `demo-v2`. A missing bracket, a space,
  a hyphen, or a longer token shows the neutral `demo` and
  still has the badge. Models and fixtures were not changed.
- Decisions: a person can type `[IAC-DEMO-` into a description
  and get the badge. That is a misleading label on a
  hand-written row. It does not bypass the seeder, and it is
  acceptable for the local demo. The note is in
  `docs/demo-data.md`.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1468 passed, 124 deselected, coverage 96.07%. Scoped black,
  isort, and flake8 passed on `app/ui/view_models.py`,
  `tests/test_ui_view_models.py`, and `tests/test_ui_pages.py`.
  PostgreSQL was not run locally. GitHub Actions on `c85f287`
  succeeded
  ([run 39565019024](https://github.com/Waber/Investment-AI-Companion/actions/runs/39565019024)).
  SQLite job `119105110715`: 1468 passed, 124 deselected,
  coverage 96.07%. PostgreSQL job `119105110896`: 124 passed,
  1468 deselected.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-21 about 07:48 to 07:56.
- Next: the owner sends
  [PR #84](https://github.com/Waber/Investment-AI-Companion/pull/84)
  to the Code Reviewer. Agents do not merge. PR #83 can merge
  before or after this one.

## 2026-10-21 - Synthetic badge matches any [IAC-DEMO- prefix

- Scope: the `/ui` synthetic-data badge. `to_instrument` still
  reads `company.description` and still uses a case-sensitive
  `startswith`, with no strip. The matched text is now the prefix
  `[IAC-DEMO-` instead of the exact `[IAC-DEMO-V1]` string. V1,
  V2, and a hypothetical V3 show the badge. An ordinary company
  does not. A lookalike that omits the bracketed prefix does not.
  A leading space and a different letter case stay unmarked. The
  source text stays `demo-v1` when the row is synthetic. Models,
  the schema, migrations, repositories, the API, and the demo
  fixtures were not changed. This is independent of PR #83 and
  can merge in either order.
- Decisions: `DEMO_MARKER` stays the name, and the check stays
  in `to_instrument`. Only the string changed. The HTML test uses
  the existing async test client and the English catalog string
  `synthetic data`. It inserts the rows in the test database. It
  does not load a fixture and it does not call a market-data
  provider. The older edit test still uses a V1 description. Its
  comment now names the shared prefix.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1466 passed, 124 deselected, coverage 96.05%. Scoped black,
  isort, and flake8 passed on `app/ui/view_models.py`,
  `tests/test_ui_pages.py`, and `tests/test_ui_forms.py`.
  PostgreSQL was not run locally (no `TEST_POSTGRES_DSN`).
  GitHub Actions on `d6cd957` succeeded
  ([run 39563358213](https://github.com/Waber/Investment-AI-Companion/actions/runs/39563358213)).
  SQLite job `119099622496`: 1466 passed, 124 deselected,
  coverage 96.05%. PostgreSQL job `119099622586`: 124 passed,
  1466 deselected.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-21 about 07:32 to 07:41.
- Next: the owner reviews
  [PR #84](https://github.com/Waber/Investment-AI-Companion/pull/84)
  and merges with "Rebase and merge". Agents do not merge.
  PR #83 can merge before or after this one.

## 2026-10-21 - Map duplicate codes and align the company name (#80)

- Scope: the remainder of
  [#80](https://github.com/Waber/Investment-AI-Companion/issues/80)
  on the server-rendered `/ui` forms. Models, schema, migrations,
  repositories, and services were not changed.
- Base: master `6d45f01` is the merge of
  [PR #81](https://github.com/Waber/Investment-AI-Companion/pull/81).
  [PR #75](https://github.com/Waber/Investment-AI-Companion/pull/75)
  is merged as `f7e90bf` and
  [PR #78](https://github.com/Waber/Investment-AI-Companion/pull/78)
  is merged as `d772409`. The work-state #81 committed on master
  still says PR #81 is not merged. That line is stale. This
  entry records the three merges, then the state of PR #82.
- Decisions: a failed company save reads `DuplicateTickerError` and
  `DuplicateIsinError` by class or by `.code` (`duplicate_ticker`,
  `duplicate_isin`). The exception text is not read. Those two
  codes select the existing localized field sentences and mark
  that input. The page stays HTTP 400, which is what a duplicate
  already was. The ticker row lookup is gone. A duplicate name
  still has no code (the repository raises a plain `ValueError`),
  so that case still looks for another row with `==` on the name.
  A plain `ValueError` or a raw `IntegrityError` is the generic
  constraint sentence, even when a ticker row is already stored.
  The real repository turns a unique-index failure into one of
  the two classes before the form sees it. `normalized_company_name`
  calls `normalize_name`. A name the form accepts is stored as
  that function would store it, including a format character
  beside a letter (Persian ZWNJ, U+200C). The form still answers
  422 when a bidi control appears anywhere, a control character
  remains in the middle, or the name is only invisible characters
  or marks. The create and edit forms now have an ISIN field so
  the ISIN error has an input. A blank ISIN is stored as null.
  QA on PR #82: the detail page, where a save redirects, shows
  that ISIN after the ticker. The label is the localized field
  name. A null ISIN is a dash.
  Code review on PR #82: any Cc character left after
  ``normalize_name`` (NUL or DEL at either end, or a control in
  the middle) is 422 on create and on edit, so PostgreSQL never
  sees that name. A save that repeats both the ticker and the
  ISIN marks only the ticker. An empty ISIN on the detail page
  uses the same missing-data sentence as the other fields.
  Invisible Cf characters at the edges stay for a follow-up.
  Instrument type is still not on the form; create keeps the
  model's STOCK default. `Secure` on the language cookie stays
  deferred until HTTPS (#56).
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1480 passed, 124 deselected, coverage 96.06%. Scoped black,
  isort, and flake8 passed on the Python this change owns.
  PostgreSQL was not run locally (no `TEST_POSTGRES_DSN`).
  Browser on `127.0.0.1:8000` with the fake collector and a
  throwaway SQLite file: a Hindi name was stored and shown; a
  second ticker showed the Polish ticker sentence on that field;
  the same ISIN showed the Polish ISIN sentence; English showed
  the ISIN sentence and, on edit, the ticker sentence; a Persian
  name with ZWNJ (U+200C) was stored between the letters. After
  the detail-page fix, a save with US0378331005 landed on the
  detail page and showed that ISIN in EN and PL. A blank ISIN
  showed a dash in both languages. The list still showed both
  tickers. After the code-review fix, a blank ISIN showed
  "brak danych" and "no data", and an edit whose name had NUL
  and DEL stayed on the form with the required-field sentence.
  The stored name did not change.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-21 about 06:46 to 07:05.
- Pull request: [PR #82](https://github.com/Waber/Investment-AI-Companion/pull/82)
  (Refs #80), opened on 2026-10-21. Not merged. This docs commit
  marks it ready for review. GitHub Actions on this head is not
  recorded yet.
- Next: both GitHub Actions jobs on this docs head. The owner
  reviews and merges with "Rebase and merge". Agents do not
  merge. #80 stays open until QA, Security, and Code Review
  approve, and until the HTTPS cookie in #56.

## 2026-10-21 - Rebase the UI follow-up onto master after #75 and #78

- Scope: rebase `cursor/ui-issue-80-forms-origin-5105` onto
  `origin/master` `f7e90bf` (PR #75 and PR #78 merged). No new
  form behavior. The duplicate-code mapping and aligning
  `normalized_company_name` with `normalize_name` stay out of
  this pull request.
- Decisions: the only conflicts were the tops of
  `docs/development-journal.md` and `docs/work-state.md` on the
  first docs commit. Both histories stay. This branch's notes
  stay first. `DuplicateTickerError`, `DuplicateIsinError`,
  `normalize_name`, `instrument_type`, and ISIN come from master
  and were not edited. The form still finds a duplicate by a
  row lookup. `CompanyCreate.instrument_type` defaults to
  STOCK, so the existing form, which does not send a type,
  still validates.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  on the tip: 1465 passed, 124 deselected, coverage 96.05%.
  The same command passed on each rebased code commit (1459
  through 1465 passed, coverage 95.96% to 96.05%). Scoped black,
  isort, and flake8 passed on the Python this branch owns.
  Whole-tree isort and flake8 still report the pre-existing
  findings on master. PostgreSQL was not run locally.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-21 about 06:33 to 06:42.
- Next: push with `--force-with-lease` and wait for GitHub
  Actions. The owner reviews PR #81. It still says Refs #80 and
  stays unmerged. The duplicate `error.code` mapping and the
  name-helper alignment are a separate pull request.

## 2026-10-20 - QA on the language return path (PR #81)

- Scope: two medium UX findings on
  [PR #81](https://github.com/Waber/Investment-AI-Companion/pull/81)
  at `d5f5d2b`. The filter left `next` on the old query, and a
  POST error page sent the language switch to a POST-only URL.
  Models, the schema, migrations, repositories, and the API were
  not changed.
- Decisions: the list fragment includes two hidden inputs with
  `hx-swap-oob="outerHTML"`. They replace `#language-next-pl` and
  `#language-next-en` with the URL HTMX just pushed. There is no
  inline script, because the page CSP is `'self'`. A full page
  does not include those inputs. `language_next_path` uses the
  request URL only for GET. `POST /ui/companies` returns to
  `GET /ui/companies/new`. `POST /ui/companies/{id}/metrics`
  returns to `GET .../metrics/new`. Edit and delete already have
  a GET at the same path. Any other POST falls back to `/ui`.
  Switching language loads that GET page, so unsaved form input
  is dropped. The 422 page still shows what was typed; the page
  after PL/EN does not.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  after the filter commit: 1368 passed, 121 deselected, coverage
  95.97%. After the POST mapping: 1370 passed, 121 deselected,
  coverage 96.01%. Scoped black, isort, and flake8 passed.
  In the browser, filtering from `q=Lodz` to `q=Nope` and clicking
  PL stayed on the Nope query. A blank ticker on the company form
  then EN opened `/ui/companies/new` in English with an empty
  name, not a 405. PostgreSQL was not run locally. GitHub Actions
  on `6533438` succeeded
  ([run 39495703430](https://github.com/Waber/Investment-AI-Companion/actions/runs/39495703430)):
  PostgreSQL job 118880080085 and SQLite job 118880080581.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-20 about 20:42 to 20:52.
- Next: the owner reviews PR #81 again. It still says Refs #80 and
  stays unmerged. After #75 lands, align the name helper with
  `normalize_name` and map `error.code`.

## 2026-10-20 - Code review on the language switch and the name helper (PR #81)

- Scope: the review on
  [PR #81](https://github.com/Waber/Investment-AI-Companion/pull/81).
  Dot segments in `safe_next`, the language switch as a POST, bidi
  controls in a company name, and every M* mark in the only-marks
  check. Models, the schema, migrations, repositories, and the API
  were not changed.
- Decisions: `safe_next` unquotes the path until it settles (at most
  eight times). A path that is still changing is refused. Any `.`
  or `..` segment is refused, so `/ui/./language/pl` and
  `/ui/%2e/language/pl` are not a return path. The language
  comparison also uses `posixpath.normpath` after that decode.
  The PL and EN controls are same-origin forms. Each posts a hidden
  `next` and a button that looks like the old link. Keyboard focus
  uses the existing outline. There is no `hx-post`, so HTMX history
  restore still gets the full page and a fragment still has no
  switch. `POST /ui/language/{code}` sets the cookie and is covered
  by `require_same_origin`. `GET /ui/language/{code}` does not set
  the cookie: a known code redirects to `safe_next` (an old
  bookmark is not a 403), and an unknown code stays HTML 404. A
  cross-site POST of an unknown code is 403 because the dependency
  runs first. A bidi override or isolate (U+202A–U+202E,
  U+2066–U+2069) anywhere in a name is 422, including at an end the
  strip would otherwise remove. Mn, Mc, and Me with no base letter
  are invisible. A letter with one of those marks is kept. The
  form rule stays stricter than #75 `normalize_name` at `2c64565`
  until that pull request merges. The duplicate `error.code`
  mapping still waits for #75.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  after the dot-segment commit: 1366 passed, 121 deselected,
  coverage 95.96%. After the POST switch: 1367 passed, 121
  deselected, coverage 95.96%. After the name rule: 1367 passed,
  121 deselected, coverage 95.97%. Scoped black, isort, and flake8
  passed. The language buttons were also clicked in a browser, with
  the keyboard, and on a narrow viewport. PostgreSQL was not run
  locally. GitHub Actions on `d5f5d2b` succeeded
  ([run 39492311897](https://github.com/Waber/Investment-AI-Companion/actions/runs/39492311897)):
  PostgreSQL job 118868382717 and SQLite job 118868383103.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-20 about 20:12 to 20:28.
- Next: the owner reviews PR #81 again. It still says Refs #80 and
  stays unmerged. After #75 lands, align the name helper with
  `normalize_name` and map `error.code`.

## 2026-10-20 - QA on the language switch and the name helper (PR #81)

- Scope: one medium and one low finding on
  [PR #81](https://github.com/Waber/Investment-AI-Companion/pull/81).
  Models, the schema, migrations, repositories, and the API were
  not changed.
- Decisions: `safe_next` rejects every path under `/ui/language`,
  including `/ui/language` itself, and returns `/ui`. The 403 for a
  direct visit is rendered at the switch URL, so the PL/EN links
  put that URL in `next`. Chrome then follows the 303 with a
  same-origin `Referer`. Returning to `/ui/language/pl` set `pl`
  after the click had set `en`. The test loads the 403 page, follows
  the EN link, and checks the final cookie is `en`.
  `normalized_company_name` is still the one form helper. It now
  strips whitespace, Cf (zero-width), and Cc (NUL and other
  controls) from both ends. A control that remains anywhere is
  422. A name that is only combining marks (Mn) or only invisible
  characters is 422. A letter with an accent is kept. A zero-width
  mark between two letters is kept. #75 at `2c64565` adds
  `normalize_name` on the write model: it strips whitespace and
  rejects a Cf-only name, and it keeps a format character beside a
  letter. This form rule is stricter until that pull request
  merges. Then this helper should be aligned with `normalize_name`.
  The duplicate `error.code` mapping still waits for #75.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1366 passed, 121 deselected, coverage 95.94%, after the name
  helper. The language-switch commit before it was 1365 passed,
  coverage 95.91%. Scoped black, isort, and flake8 passed.
  PostgreSQL was not run locally.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-20 about 19:52 to 20:10.
- Next: the owner reviews PR #81 again. It still says Refs #80 and
  stays unmerged. After #75 lands, align the name helper with
  `normalize_name` and map `error.code`.

## 2026-10-20 - UI forms follow-up, the part that does not need #75 (#80)

- Scope: the frontend part of
  [#80](https://github.com/Waber/Investment-AI-Companion/issues/80).
  Models, the schema, migrations, repositories, and the API were
  not changed. The `error.code` mapping waits for #75.
- Decisions: create and edit share `normalized_company_name` in
  `app/ui/form_fields.py`. It strips surrounding whitespace with
  `str.strip` (space, newline, NBSP U+00A0, ideographic space
  U+3000) and returns None when nothing visible remains. Empty,
  whitespace-only, and Cf/zero-width-only names are
  `error.required` and HTTP 422, in Polish or English. Category C
  as a whole is blank, not only Cf: a control character is not a
  visible name either. A zero-width mark beside a real letter is
  kept, because `strip` does not remove it. The old comments at
  `company_payload` and `_name_is_blank` said `strip` removed NBSP
  and U+3000 and that a Cf-only name was blank "too". The check
  never called `strip` for that, and it skipped every category C.
  Those comments are replaced by the helper's docstring.
  `GET /ui/language/{code}` calls `origin_allowed` before it sets
  the cookie. Other GETs stay unchecked. A same-origin link click
  usually has no `Origin`. `Referrer-Policy: same-origin` still
  sends `Referer`, and a missing `Origin` with that `Referer`
  passes. A cross-site `Origin` or `Referer` is the HTML 403 and
  the cookie is not set. A bad `Origin` is not rescued by a good
  `Referer`. The address bar and a bookmark send neither header.
  That is the same 403, with a link back to `/ui`, so a cross-site
  GET that strips `Referer` cannot change the language. An unknown
  code such as `de` does not set a cookie, so it stays the HTML
  404 and skips the check. `Secure` on the language cookie waits
  for HTTPS (#56). On this HTTP demo a `Secure` cookie would not
  be stored. Duplicate ticker and ISIN still use the stored-row
  lookup. A TODO in `_company_save_failed` names
  `DuplicateTickerError.code` (`duplicate_ticker`) and
  `DuplicateIsinError.code` (`duplicate_isin`) for the rebase
  after #75.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1364 passed, 121 deselected, coverage 95.90%. Scoped black,
  isort, and flake8 passed. PostgreSQL was not run locally.
  GitHub Actions
  [run 39485588275](https://github.com/Waber/Investment-AI-Companion/actions/runs/39485588275)
  on `ed0fe02` succeeded. SQLite job `118845515082` and PostgreSQL
  job `118845515315` both concluded success. The earlier run
  [39485504563](https://github.com/Waber/Investment-AI-Companion/actions/runs/39485504563)
  on `a067d61` was cancelled when the docs commit moved the head.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-20 about 19:25 to 19:45.
- Pull request: [PR #81](https://github.com/Waber/Investment-AI-Companion/pull/81)
  (Refs #80), opened on 2026-10-20. Not merged.
- Next: the owner reviews the pull request. After #75 lands, rebase
  and map `error.code`.

## 2026-10-21 - Rebase instrument type onto master after PR #78

- Scope: rebase `cursor/instrument-type-isin-1db6` onto
  `origin/master` `d772409` (PR #78 merged). No new behavior.
  Conflicts in `app/models/company.py` keep both sets:
  `name` `min_length=1` and `max_length=255`, and `ticker`
  `max_length=TICKER_MAX_LENGTH` with `pattern=TICKER_PATTERN`.
  `normalize_name`, ISIN, `instrument_type`, and the `isascii`
  currency check stay. Journal and work-state conflicts keep
  both the collector entries and the instrument-type entries.
- Verification: no `.env`, `DATABASE_URL` unset,
  `REQUIRE_POSTGRES=1`. Every rebased commit passed the SQLite
  CI command and `pytest -m integration`. The tip
  `9d4c0e9` is 1458 passed, 124 deselected, coverage 95.90%
  on SQLite, and 124 passed, 1458 deselected on PostgreSQL.
- AI model: Grok 4.7. Account usage was not available in this
  session.
- Time tracking (UTC, 2026-10-21): rebase started about 06:11.
- Next: the owner merges PR #75 with "Rebase and merge".
  Agents do not merge.

## 2026-10-20 - Code review round 1 on instrument type and ISIN

- Scope: code review on
  [PR #75](https://github.com/Waber/Investment-AI-Companion/pull/75),
  head was `5316d26`. Same branch, rebased onto current
  `origin/master` `9d26948` already. No UI files.
- Decisions: startup calls `create_all`, then refuses to serve
  when `companies` exists without `instrument_type` or `isin`.
  The error names `alembic upgrade head` and `alembic stamp head`.
  README and `docs/api-demo.md` say which command matches an
  Alembic database, an older `create_all` database, and a fresh
  `create_all` database. `DuplicateTickerError` and
  `DuplicateIsinError` are raised after the `IntegrityError`
  handler, so `__context__` and `__cause__` are empty. A name
  that is only Unicode format characters (`Cf`) after strip is
  rejected. The ISIN pattern comment says the country prefix is
  not checked. `test_duplicate_ticker_create_returns_400` was
  not in this repository (it lived on `qa/known-defects-xfail`);
  it is restored as a passing test in `tests/test_known_defects.py`.
- Verification: no `.env`, `DATABASE_URL` unset. Each commit was
  green locally on SQLite and PostgreSQL, then on both GitHub
  Actions jobs.
  `6190e85` run
  [39484912819](https://github.com/Waber/Investment-AI-Companion/actions/runs/39484912819)
  (SQLite `118842697553`: 1415 passed, 124 deselected, coverage
  96.17%; PostgreSQL `118842697008`: 124 passed).
  `bdffb76` run
  [39485111338](https://github.com/Waber/Investment-AI-Companion/actions/runs/39485111338)
  (SQLite `118843392239`, PostgreSQL `118843392660`).
  `93771eb` run
  [39485323078](https://github.com/Waber/Investment-AI-Companion/actions/runs/39485323078)
  (SQLite `118844117434`, PostgreSQL `118844117786`).
  `03d8d43` run
  [39485556256](https://github.com/Waber/Investment-AI-Companion/actions/runs/39485556256)
  (SQLite `118844913556`: 1416 passed, 124 deselected, coverage
  96.13%; PostgreSQL `118844913923`: 124 passed, 1416 deselected).
- AI model: Grok 4.7. Account usage was not available in this
  session.
- Time tracking (UTC, 2026-10-20): review round from about 19:25.
- Next: the owner reviews PR #75. Agents do not merge.

## 2026-10-20 - Generic update error drops the SQL text

- Scope: a security nit on
  [PR #75](https://github.com/Waber/Investment-AI-Companion/pull/75).
  The generic update `ValueError` was raised inside
  `except IntegrityError`.
- Decisions: that sentence is raised after the handler ends, with
  `from None`. Written inside the handler, `from None` still
  stores the driver error on `__context__`, and that object
  includes the SQL text. `test_not_null_rollback_reuses_same_session`
  asserts `__context__` and `__cause__` are both `None`. The
  session can still update the same row afterwards.
- Verification: no `.env`, `DATABASE_URL` unset. CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1411 passed, 123 deselected, coverage 96.15%. PostgreSQL
  (`TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`,
  `REQUIRE_POSTGRES=1`, `pytest -m integration`) -> 123 passed,
  1411 deselected.
- AI model: Grok 4.7. Account usage was not available in this
  session.
- Time tracking (UTC, 2026-10-20): security nit from about 19:05.
- Next: the owner reviews PR #75. Agents do not merge.

## 2026-10-20 - Dotted ticker duplicate is 400

- Scope: extra QA finding on
  [PR #75](https://github.com/Waber/Investment-AI-Companion/pull/75).
  A second create of an existing name and ticker such as `BRK.B`
  returned HTTP 500 on master. The branch was rebased onto
  `origin/master` `9d26948`.
- Decisions: create still looks the ticker up before insert, and
  again after rollback when the unique index fires. Both paths
  raise `DuplicateTickerError`. The driver text is not read.
  SQLite's `IntegrityError` names the columns and does not
  contain `uq_company_name_ticker`. `CompanyCreate.name` and
  `CompanyUpdate.name` keep `min_length=1`. `max_length` on
  `CompanyUpdate.ticker` stays with PR #78. The next rebase of
  either pull request keeps both.
- Verification: no `.env`, `DATABASE_URL` unset. CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1411 passed, 123 deselected, coverage 96.15%. PostgreSQL
  (`TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`,
  `REQUIRE_POSTGRES=1`, `pytest -m integration`) -> 123 passed,
  1411 deselected. GitHub Actions
  [run 39478793637](https://github.com/Waber/Investment-AI-Companion/actions/runs/39478793637)
  on `0188f53` succeeded. SQLite job `118821628878`: 1411
  passed, 123 deselected, coverage 96.15%. PostgreSQL job
  `118821628158`: 123 passed, 1411 deselected.
- AI model: Grok 4.7. Account usage was not available in this
  session.
- Time tracking (UTC, 2026-10-20): extra QA finding from about
  18:45, after the rebase onto `9d26948`.
- Next: the owner reviews PR #75. Agents do not merge.

## 2026-10-20 - QA round 1 on instrument type and ISIN

- Scope: QA findings on
  [PR #75](https://github.com/Waber/Investment-AI-Companion/pull/75),
  on the same branch as security round 1. The explicit
  `instrument_type: null` update was already 422 from that round.
- Decisions: the company read model maps a stored type outside
  `STOCK`, `ETF`, and `ETC` to null and logs the value's class
  name, so one bad row does not fail the list. Create and update
  share one sentence per duplicate. The repository raises
  `app.repositories.company_errors.DuplicateTickerError` or
  `DuplicateIsinError`. Both subclass `DuplicateCompanyError`
  (`ValueError`) and carry `code` (`duplicate_ticker` or
  `duplicate_isin`). The 400 body keeps `detail` as a string and
  adds `code`. A company name is stripped, and a blank name is
  422 on create and on update when the field is sent.
  `docs/api-demo.md` now describes `instrument_type`, `isin`, and
  the error body. #16 is closed by the pull request. #26 stays a
  reference because the wider instruments model is still open.
- Verification: each commit was green locally on SQLite and
  PostgreSQL, then on both GitHub Actions jobs.
  `77d54f8` run
  [39467269111](https://github.com/Waber/Investment-AI-Companion/actions/runs/39467269111)
  (SQLite `118781804311`, PostgreSQL `118781803573`).
  `61300c9` run
  [39467492356](https://github.com/Waber/Investment-AI-Companion/actions/runs/39467492356)
  (SQLite `118782583815`, PostgreSQL `118782583650`).
  `79b6bc6` run
  [39467716661](https://github.com/Waber/Investment-AI-Companion/actions/runs/39467716661)
  (SQLite `118783362013`: 1346 passed, 122 deselected, coverage
  96.12%; PostgreSQL `118783361167`: 122 passed, 1346 deselected).
- AI model: Grok 4.7. Account usage was not available in this
  session.
- Time tracking (UTC, 2026-10-20): QA round after security round 1,
  from about 17:24.
- Next: the owner reviews PR #75. Agents do not merge.

## 2026-10-20 - Security round 1 on instrument type and ISIN

- Scope: three low findings on
  [PR #75](https://github.com/Waber/Investment-AI-Companion/pull/75).
  A named unique constraint on ticker alone is a follow-up and is
  not in this pull request. The ticker column stays unique.
- Decisions: `update()` uses the same lookup as `create` after an
  `IntegrityError`. A stored ticker or ISIN raises the fixed
  sentence, and that error is not chained to the driver. Any other
  constraint keeps `Update failed due to constraint violation`.
  The handler does not bind the unused driver exception. ISIN
  uniqueness is `Index("uq_companies_isin", unique=True)` on the
  model and in revision `0001`. A test compares `create_all` with
  the migrated schema on SQLite and on PostgreSQL. An explicit
  `instrument_type: null` on update is HTTP 422. Omitting the
  field keeps the stored type.
- Verification: each commit was run locally on SQLite and
  PostgreSQL before it was pushed, then GitHub Actions ran on
  that commit. `add849e` run
  [39464829393](https://github.com/Waber/Investment-AI-Companion/actions/runs/39464829393)
  succeeded (SQLite job `118773372256`, PostgreSQL job
  `118773371523`). `65bd0b2` run
  [39465048567](https://github.com/Waber/Investment-AI-Companion/actions/runs/39465048567)
  succeeded (SQLite job `118774146241`, PostgreSQL job
  `118774146797`). `a81e646` run
  [39465272356](https://github.com/Waber/Investment-AI-Companion/actions/runs/39465272356)
  succeeded. SQLite job `118774915084`: 1341 passed, 122
  deselected, coverage 96.05%. PostgreSQL job `118774915673`:
  122 passed, 1341 deselected.
- AI model: Grok 4.7. Account usage was not available in this
  session.
- Time tracking (UTC, 2026-10-20): security fixes after the first
  CI report, from about 17:05.
- Next: the owner reviews PR #75. QA findings may follow. Agents
  do not merge.

## 2026-10-20 - Instrument type, ISIN, and duplicate ticker 400

- Scope: add `instrument_type` and `isin` on the existing company
  API (issue #26, narrowed), and return HTTP 400 when a create
  repeats a ticker (issue #16) or an ISIN. `Company` is not
  renamed. `app/ui/`, `templates/`, and `static/` were not edited.
- Decisions: `instrument_type` is a Python `enum.Enum` that also
  subclasses `str`, stored as `String(8)` with a CHECK for
  `STOCK`, `ETF`, and `ETC`. A PostgreSQL ENUM would not match
  SQLite. Omitted creates and existing rows are `STOCK`.
  `EQUITY` is rejected and is not copied from a provider
  `quoteType`. `isin` is checked at the write boundary: ASCII
  only, then strip and uppercase, then ISO 6166 pattern and
  Luhn. Letters expand to two digits (A=10 … Z=35) because Luhn
  only adds 0–9. Revision `0001` uses `ALTER TABLE ADD COLUMN`,
  not Alembic batch mode, because batch rebuilds drop
  `companies` and the `financial_metrics` foreign key is on.
  Duplicate ticker and ISIN are detected by looking the row up
  after rollback. The driver message is not parsed: SQLite and
  PostgreSQL name the unique index differently, and that text
  must not reach the client. Unknown integrity errors stay a
  generic 500. Ticker stays unique on its own. Unique
  `(ticker, exchange)`, `/api/v1/instruments/`, list filters,
  and "metrics only for stocks" stay deferred. Startup still
  uses `create_all`. This is not the #8 baseline.
- Verification: `.venv` Python 3.12, no `.env`, `DATABASE_URL`
  unset. CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1337 passed, 121 deselected, coverage 96.01%. PostgreSQL
  (`TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`,
  `pytest -m integration`) -> 121 passed, 1337 deselected, 0
  xfailed. GitHub Actions
  [run 39462037357](https://github.com/Waber/Investment-AI-Companion/actions/runs/39462037357)
  on `04aaeeb` succeeded. SQLite job `118763701814`: 1337 passed,
  121 deselected, coverage 96.01%. PostgreSQL job `118763702685`:
  121 passed, 1337 deselected. The earlier run
  [39460651955](https://github.com/Waber/Investment-AI-Companion/actions/runs/39460651955)
  covered only the checksum helper (`07f7983`).
- AI model: Grok 4.7. Account usage was not available in this
  session.
- Time tracking (UTC, 2026-10-20): implementation continued from
  about 16:33 and this entry was written after the local suites
  passed.
- Pull request:
  [PR #75](https://github.com/Waber/Investment-AI-Companion/pull/75)
  (Refs #26, Refs #16). Branch
  `cursor/instrument-type-isin-1db6`, based on `origin/master`
  `1f1678f`.
- Next: the owner reviews the pull request and merges it with
  "Rebase and merge". Agents do not merge.
## 2026-10-20 - Code review round 1 on collector hardening (#76)

- Scope: code review on the open pull request, after rebasing onto
  `origin/master` `9d26948` (PR #77 is merged). Conflicts were only
  in this journal and `docs/work-state.md`. Issue #75 is still open,
  so ISIN, instrument type, and `normalize_name` were not added.
  Templates, static files, and `app/ui/` were not edited. Tests do
  not call a live provider.
- Decisions:
  - A spent deadline still gives yfinance a 0.001 s timeout, because
    raising inside the library is swallowed. If `remaining()` is 0
    after the call and the result is `None` or empty, Yahoo raises
    `TransientProviderError`. That is HTTP 502 and the guard does
    not cache it. A real payload is kept. A fake clock that jumps
    past the deadline covers both.
  - The "cannot be cached" comment sits on the path that has no
    cache key. `GuardPolicy` says a TTL of 0 or an unhashable
    argument disables de-dup.
  - The HTTP-cap marker is on the session object. The next
    `_install_http_cap` wraps a session yfinance replaced.
    `history` is where `PriceHistory` passes `timeout`.
  - A failed leader removes its key, so the next same-ticker call
    can lead and succeed. A cache hit found inside `_coalesced` is
    returned without another provider call.
- Verification: no `.env`, `DATABASE_URL` unset, Python 3.12.3 venv
  from `requirements-dev.lock` (includes `python-multipart==0.0.32`
  from master). CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1405 passed, 121 deselected, coverage 95.62%. Scoped black,
  isort, and flake8 passed on the touched Python files. PostgreSQL
  was not run locally. GitHub Actions runs both jobs.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (2026-10-20, UTC): review notes read about 18:49.
- Next: both CI jobs, then the code-review table on the pull request.
  Agents do not merge.

## 2026-10-20 - Security round 1 on collector hardening (#76)

- Scope: security re-review of the open pull request. Same branch.
  The QA round 1 retry rule stays. Templates, static files, and
  `app/ui/` were not edited. Tests do not call a live provider.
- Decisions:
  - The in-flight permit is taken with `acquire(blocking=False)`
    before the rate-limit wait. A rejected call raises
    `ProviderError` and does not sleep or record a token. The
    timestamp is recorded only while the permit is held. `finally`
    releases the permit before a retry sleep, so a backoff does not
    keep the slot. At most `max_inflight` threads can be inside the
    rate-limit wait.
  - A second request for a key that already has a leader fails at
    once (`ProviderError`, HTTP 502). It does not wait up to the
    deadline. Waiting, even for one second, would still hold a
    worker without a permit. The leader's result is cached for a
    later request.
  - `YfData.get` and `post` are not the only HTTP entry points.
    yfinance 1.7 calls `session.get` with `timeout=30` from the
    cookie and crumb helpers. Those methods are wrapped with the
    same cap. A missing timeout is capped too, because the requests
    default `None` waits with no limit. The tests record the
    timeout and open no socket.
  - A ticker made only of dots is rejected. Pydantic's regex engine
    has no lookahead, so the pattern requires one non-dot character.
    Length stays capped at 20 in `normalize_ticker` and on the fields.
- Verification: no `.env`, `DATABASE_URL` unset, Python 3.12.3 venv
  from `requirements-dev.lock`. CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1338 passed, 121 deselected, coverage 95.38%. Scoped black,
  isort, and flake8 passed on the touched Python files. PostgreSQL
  was not run locally (no `TEST_POSTGRES_DSN`). GitHub Actions runs
  both jobs.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (2026-10-20, UTC): security notes read about 18:13.
  Local suite finished after that.
- Next: both CI jobs, then the security table on the pull request.
  Agents do not merge.

## 2026-10-20 - QA round 1 on collector hardening (#76)

- Scope: review findings on the open pull request for the collector
  hardening branch. Same branch. Templates, static files, and
  `app/ui/` were not edited. Tests do not call a live provider.
- Decisions:
  - `__context__` is followed only for a `ProviderError` wrapper.
    `__cause__` is always followed. A `KeyError` raised inside
    `except TransientProviderError`, including `from None`, is not
    retried: the call fails once and becomes the fixed provider error.
  - Python sets `__suppress_context__` for every `raise New from Old`,
    not only for `from None`. The kept wrapper test uses
    `raise ProviderError from ValueError`, so the transient error is
    only on `__context__` while suppress is already true. That wrapper
    is still retried because it has an explicit cause. `from None` has
    no cause, so a `ProviderError` raised that way does not follow
    context either.
  - One fake-clock test pins that a retry does not restart the
    deadline. After a 10 s backoff, a 20 s rate-limit wait no longer
    fits in the 25 s deadline. The 30 s rate-limit cap would still
    allow it, so only the shared clock refuses the sleep.
  - The gitleaks allowlist uses `condition = "AND"`. The default OR
    would hide every secret in `tests/conftest.py` because the path
    alone matched.
- Verification: no `.env`, `DATABASE_URL` unset, Python 3.12.3 venv
  from `requirements-dev.lock`. CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1331 passed, 121 deselected, coverage 95.17%. Scoped black,
  isort, and flake8 passed on the touched Python files. PostgreSQL
  was not run locally (no `TEST_POSTGRES_DSN`). GitHub Actions runs
  both jobs.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (2026-10-20, UTC): QA notes read about 17:59.
- Next: both CI jobs, then the pull request is marked ready for
  review. Agents do not merge.

## 2026-10-20 - Collector hardening (#76)

- Scope: port the unmerged collector hardening from
  `cursor/collector-resilience-currency-ed10` (`30b6f11`) onto current
  master, and cover the Security Engineer findings on #76. PR #70 was
  closed without merging. PR #72 is already on master, so this branch
  starts from `origin/master` and does not replay #72's guard.
  Templates, static files, and `app/ui/` were not edited. Tests do not
  call a live market-data provider.
- Already on master from #72, so not ported again: the 5 s rate-limit
  wait cap (`d8c9daa`), the autouse `reset_collector` fixture
  (`63e6497`), and `COLLECTOR_RETRY_MAX_RETRIES` of 0 (`d47e8be`).
- Decisions:
  - One deadline (`COLLECTOR_TOTAL_DEADLINE_SECONDS`, default 15 s,
    allowed 1 to 120) covers the rate-limit sleeps and the retry
    backoff of a single call. A sleep that would pass it is refused.
    The provider call is not killed by that clock.
  - `COLLECTOR_MAX_INFLIGHT` (default 4, allowed 1 to 16) is a
    semaphore around the provider call only. `acquire(blocking=False)`
    fails at once when every permit is taken. The permit is released
    in `finally`, including before a retry sleep. Cache hits do not
    take one.
  - The cache key strips and uppercases `ticker`. The string forwarded
    to the inner collector stays as the caller sent it. Yahoo calls
    `normalize_ticker` again before `yf.Ticker`.
  - Two misses for the same key share one provider call. The others
    wait on an `Event`.
  - A `TransientProviderError` on `__cause__` or `__context__` is
    retried. Any other unexpected error becomes `ProviderError` with
    a fixed message and `from None`, so the provider text is not
    chained. fetch-company maps that to HTTP 502 and logs the class
    name only.
  - Yahoo logs `type(e).__name__`. A filter on the `yfinance` logger
    replaces library log text. `NullHandler.handle` does not run
    filters, so the filter sits on a normal handler.
  - Each Yahoo HTTP request is capped at 10 s
    (`YFINANCE_HTTP_TIMEOUT_SECONDS`), and at the time left on the
    deadline when that is shorter. yfinance 1.7 has no timeout argument
    on `Ticker`; `history` does, and `get`/`post` are wrapped.
  - `.` and `..` are not tickers. Pydantic's regex engine has no
    lookahead, so the pattern is two alternatives instead of
    `(?!\.\.?$)`.
  - Currency checks `isascii()` before the three-letter check, so a
    long s or a ligature cannot fold into an ISO code. #72 already
    rejects a non-ASCII code with `[A-Za-z]`; the check is now explicit
    and runs first. Whitespace is still rejected, not stripped.
  - `.gitleaks.toml` allowlists the pytest placeholder on
    `tests/conftest.py` line 7 and keeps the default rules.
- Verification: no `.env`, `DATABASE_URL` unset, Python 3.12.3 venv
  from `requirements-dev.lock`. CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1329 passed, 121 deselected, coverage 95.15%. Scoped black,
  isort, and flake8 passed on the touched Python files. The two
  pre-existing E501 lines in `tests/test_provider_data_hygiene.py`
  are unchanged. PostgreSQL was not run locally (no
  `TEST_POSTGRES_DSN`). GitHub Actions runs both jobs.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (2026-10-20, UTC): read the issue and the old branch
  from about 16:58. Local suite finished 17:24.
- Next: the owner reviews the pull request. Agents do not merge.
## 2026-10-20 - Drop the new disclaimer asserts (PR #77)

- Scope: the PM decision on
  [PR #77](https://github.com/Waber/Investment-AI-Companion/pull/77).
  AGENTS.md and product requirements section 12 record Raul's
  decision of 2026-10-10: the disclaimer banner is not a product
  requirement. The six banner asserts added in
  `tests/test_ui_forms.py` are removed. No new disclaimer copy.
  The shipped banner and the tests that predate this pull request
  are unchanged.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1363 passed, 121 deselected, coverage 95.83%. Scoped black
  and flake8 passed on the test file.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-20 about 18:05 to 18:15.
- Next: the owner reviews PR #77. It still says Refs #34 and stays
  unmerged.

## 2026-10-20 - Review notes on the company forms (PR #77)

- Scope: the code review on
  [PR #77](https://github.com/Waber/Investment-AI-Companion/pull/77).
  Models and the repository were not changed.
- Decisions: `python-multipart` floor is `>=0.0.32`. The comment
  cites GHSA-5rvq-cxj2-64vf / CVE-2026-53539 (quadratic urlencoded
  parse, fixed in 0.0.30) and the older CVE-2024-53981 note.
  `pip-compile` on both lock files left `python-multipart==0.0.32`
  and its hashes unchanged. A company name is stripped of
  surrounding whitespace in `company_payload` only. A name with no
  visible character is 422, including nbsp, ideographic space, and
  a name made only of format characters such as U+200B. The origin
  check still compares scheme, host, and port. The docstring says
  it relies on `TrustedHostMiddleware`, so `ALLOWED_HOSTS` must
  stay loopback-only (DNS rebinding). `localhost` is not
  `127.0.0.1`.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1363 passed, 121 deselected, coverage 95.83%. Scoped black,
  isort, and flake8 passed. `pip-audit` on both locks: no known
  vulnerabilities. PostgreSQL was not run locally.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-20 about 17:50 to 18:15.
- Next: the owner reviews PR #77 again. It still says Refs #34 and
  stays unmerged.

## 2026-10-20 - QA notes on the company forms (PR #77)

- Scope: four notes from QA on
  [PR #77](https://github.com/Waber/Investment-AI-Companion/pull/77).
  Models, the repository, the schema, and the backend sentences were
  not changed.
- Decisions: a failed company create or update no longer reads the
  exception text. The form asks whether another row already stores
  that ticker, with ``==`` on the value the write model already
  uppercased, which is how the repository compares it. Only then
  does the page show the ticker sentence, in Polish or English. The
  same lookup on the name selects the existing name sentence. Any
  other failure stays the generic constraint sentence, including
  both "Company name or ticker already exists" and the #75 sentence
  "A company with this ticker already exists" when no such row is
  stored. A blank or whitespace-only name is ``error.required`` and
  422 in the form layer; ``CompanyCreate`` still accepts ``""``.
  A wrong method on a `/ui` path is an HTML 405 with the `/ui`
  security headers. API 405 responses stay JSON. Editing a
  description drops the `[IAC-DEMO-V1]` badge; a test records that
  today's read model works that way.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1356 passed, 121 deselected, coverage 95.81%. Scoped black,
  isort, and flake8 passed. PostgreSQL was not run locally.
  GitHub Actions
  [run 39466655138](https://github.com/Waber/Investment-AI-Companion/actions/runs/39466655138)
  on `5602504` succeeded. SQLite job `118779699006` and PostgreSQL
  job `118779699318` both concluded success.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-20 about 17:25 to 17:45.
- Next: the owner reviews PR #77 again. It still says Refs #34 and
  stays unmerged.

## 2026-10-20 - Company and financial-metrics forms under /ui (#34, part)

- Scope: the part of
  [#34](https://github.com/Waber/Investment-AI-Companion/issues/34)
  that fits today's `Company` and `FinancialMetrics` models. Create,
  edit, and delete for a company, and the same three actions for one
  company's metrics, from the detail page. Validation reuses
  `CompanyCreate` / `CompanyUpdate` and `FinancialMetricsCreate` /
  `FinancialMetricsUpdate`, plus the existing repositories. Models,
  schema, migrations, services, collectors, scoring, and the API were
  not changed. `Company` was not renamed.
- Decisions: forms are ordinary POST forms. A validation error is a
  422 (or 400 for a duplicate) full page with the posted text, so it
  works with JavaScript off. HTMX still filters the list. The pinned
  `htmx-config` meta does not swap 4xx responses, and that meta stays
  as it is. Empty optional company fields become `None` before
  Pydantic, so a blank website is not an invalid URL and a blank
  currency keeps the repository default of USD. Number and period
  fields are `type="text"` so `NaN`, `inf`, and a bad date reach
  Pydantic instead of being blocked by the browser. `period_type` is
  a free string of at most 20 characters, matching
  `FinancialMetricsCreate`. The edit form shows it and does not submit
  it, because `FinancialMetricsUpdate` has no such field. A time with
  no zone is stored as UTC. Delete is a GET confirmation plus a POST
  button. The company warning says the financial metrics go with it
  (`CompanyDB` cascade). There is no CSRF token: there is no session
  to bind one to. Every unsafe `/ui` method requires `Origin`
  (or `Referer` when `Origin` is absent) to match this request's
  scheme, host, and port. Otherwise the response is an HTML 403.
  `Referrer-Policy` is `same-origin`. `no-referrer` makes Chrome send
  `Origin: null` on a normal form POST and omit `Referer`, which
  rejected every save in the browser. `same-origin` still withholds
  the address from a company website. CSP `form-action 'self'` and
  the language cookie `SameSite=lax` stay. `python-multipart` 0.0.32
  is pinned with hashes (floor 0.0.18, CVE-2024-53981).
- Deferred until #26 / #28: instrument type, ISIN, ETF/ETC attribute
  forms, a `source=manual` column, a real synthetic-marker column
  (the badge is a `[IAC-DEMO-V1]` prefix on the description, so
  editing that description can drop it), and cascades beyond
  financial metrics. Edit time shows the existing `updated_at`. No
  column was added.
- Verification: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1349 passed, 121 deselected, coverage 95.71%. Scoped
  black, isort, and flake8 passed. `pip-audit` on both locks:
  "No known vulnerabilities found". PostgreSQL was not run locally.
  Browser (Chrome, `127.0.0.1:8000`, fake collector, SQLite file in
  `/tmp`): empty company form showed the Polish ticker error with
  focus on the summary; a `<script>` name and description were stored
  as text; ticker `tst` became `TST` and currency `pln` became `PLN`;
  metrics `NaN` and an empty period stayed on the form; a valid row
  showed `1 000 PLN` and `0 PLN`; the edit form kept period type
  read-only and showed the existing update time; English delete
  confirmation warned that the company's metrics go with it, and the
  POST left the list empty. The list filter still applied.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (UTC): 2026-10-20 about 16:35 to 17:15. Reading the
  issue and the current models, then forms, tests, the browser check,
  and this entry.
- Pull request: [PR #77](https://github.com/Waber/Investment-AI-Companion/pull/77)
  (Refs #34), opened on 2026-10-20. GitHub Actions
  [run 39462413658](https://github.com/Waber/Investment-AI-Companion/actions/runs/39462413658)
  on `76367fc` succeeded. SQLite job `118765004831` and PostgreSQL
  job `118765005870` both concluded success.
- Next: the owner reviews the pull request and merges it with
  "Rebase and merge". This pull request says Refs #34 and leaves
  the issue open.

## 2026-10-20 - Local venv, IDE interpreter guide and the Python 3.14 probe

- Scope: a persistent `.venv` for local tests, the missing `.venv/`
  ignore rule, IDE interpreter setup for PyCharm, IntelliJ IDEA and
  Cursor, and an issue for moving to Python 3.14.
- Decisions: stay on Python 3.12 locally because CI and the locks use
  it. The README names `python3.12` instead of `python`, because
  Homebrew's `python3` is 3.14 and plain `python` may not exist on
  macOS. The 3.14 move is
  [#73](https://github.com/Waber/Investment-AI-Companion/issues/73),
  not part of this branch. The existing docs test that requires the
  shared checkout path in `docs/ide-startup.md` failed once after the
  rewrite; the path was restored as the example interpreter path.
- Python 3.14 probe (throwaway venv in the session scratchpad, Homebrew
  3.14.3): the hashed install fails on `psycopg2-binary==2.9.9` (no
  3.14 wheel, source build needs `pg_config`). A PyPI check of the 70
  locked pins found no other missing wheel. `sqlalchemy==2.0.23` then
  fails at import (`TypingOnly` sees `__firstlineno__` and
  `__static_attributes__`). With `sqlalchemy` 2.0.55 and
  `psycopg2-binary` 2.9.13 the CI command gives 1300 passed and
  `-m integration` 105 passed, 16 skipped.
- Verification: in `.venv` (Python 3.12.15), no `.env`,
  `DATABASE_URL` and `SECRET_KEY` unset. CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-fail-under=80`
  -> 1300 passed, 121 deselected, coverage 95.80%. `pytest -m
  integration` -> 105 passed, 16 skipped. `git check-ignore` confirms
  `.venv/` is ignored. The IDE menu paths were written from the IDE
  docs, not clicked through; names vary by IDE version.
- AI model: Claude Opus 5.5 (Claude Code). Account usage was not
  available in this session.
- Time tracking (+0200): 2026-10-19 about 15:10, discussion of the
  environment; 2026-10-20 13:02 Python 3.12 installed by the owner,
  13:02 to 13:20 venv, probe, issue, docs and this entry.
- Pull request: [PR #74](https://github.com/Waber/Investment-AI-Companion/pull/74)
  (Refs #73), opened on 2026-10-20.
- Local fix: at the owner's request, removed the broken
  `~/.local/bin/python3.12` link (it pointed into an old session
  scratchpad and shadowed Homebrew on `PATH`). `which -a python3.12`
  now lists only `/opt/homebrew/bin/python3.12`.
- Next: the owner reviews PR #74, then #26 together with #16.

## 2026-10-19 - Rebase of the offline demo (#25) onto PR #72

- Scope: the owner merged
  [PR #72](https://github.com/Waber/Investment-AI-Companion/pull/72)
  (#24 part 2), which left
  [PR #71](https://github.com/Waber/Investment-AI-Companion/pull/71)
  in conflict. Rebased `cursor/one-command-offline-demo-64f5` onto
  `origin/master` `922bdfe`. No code change.
- Decisions: the only conflicts were the stacked top entries of
  `docs/work-state.md` and this journal. Both entries were kept, the
  newer #25 entry first. The pre-rebase head is kept locally as
  `backup/demo-25-before-rebase-72`.
- Verification: fresh Python 3.12.15 venv installed from
  `requirements-dev.lock`, no `.env`, `DATABASE_URL` unset. CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-fail-under=80`
  -> 1300 passed, 121 deselected, coverage 95.80% (1259 from master
  plus the demo tests). `pytest -m integration` -> 105 passed, 16
  skipped (no `TEST_POSTGRES_DSN`; CI runs PostgreSQL).
- AI model: Claude Opus 5.5 (Claude Code). Account usage was not
  available in this session.
- Time tracking (+0200, 2026-10-19): PR #72 merged 14:10; rebase,
  tests and this entry 14:20 to 15:00.
- Next: the owner reviews and merges PR #71 and closes PR #70. Then
  #26 together with #16.

## 2026-10-15 - Security and QA review of the offline demo (#25)

- Scope: review fixes on the same branch as
  [#25](https://github.com/Waber/Investment-AI-Companion/issues/25).
  Security N1 and the QA medium finding are the same hole: a `demo/`
  directory that is a symlink was followed by `Path.resolve`, so a
  reset could delete a database outside the checkout. Security N2:
  always generate a fresh `SECRET_KEY`. QA low: check the port before
  deleting the file. QA nit: one line in `docs/RUN_DEMO.md` pointing
  at `python -m scripts.run_demo`.
- Decisions: `refuse_symlink_escape` refuses a symlink at `demo/`, at
  `investment_demo.db`, at a parent that is still inside the checkout,
  and when the checkout path passed in is itself a symlink. Following
  the link must also leave `demo` as a direct child of that checkout.
  `remove_database_files` refuses again before `unlink`. The command
  binds `127.0.0.1` and the chosen port before it builds or seeds, and
  exits with a fixed message when that port is taken. `resolve_secret_key`
  no longer reads the shell. The generated key is still not printed and
  not written to disk. The absolute database path in the banner stays
  (security N3).
- Verification: no `.env`, `DATABASE_URL` unset. CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1175 passed, 121 deselected, total coverage 95.41%. Scoped
  `black`, `isort`, and `flake8` on `scripts/run_demo.py` and
  `tests/test_run_demo.py` passed. PostgreSQL was not run locally
  (no `TEST_POSTGRES_DSN`). GitHub Actions
  [run 38705460114](https://github.com/Waber/Investment-AI-Companion/actions/runs/38705460114)
  on `4449053` completed with conclusion success: SQLite job
  `116323646312` success, PostgreSQL job `116323646645` success.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (2026-10-15, UTC): review fixes started about 08:11.
  Full SQLite suite finished 08:21.
- Next: #26 together with #16, after CI on this commit is green.

## 2026-10-15 - One-command offline demo (#25)

- Scope: [#25](https://github.com/Waber/Investment-AI-Companion/issues/25).
  `python -m scripts.run_demo` creates `demo/investment_demo.db`, seeds
  `demo-v1`, selects the fake collector, and serves the app on
  `127.0.0.1`. The printed page is `/ui` because that router is on
  master. UI templates and static files were not edited.
- Decisions: the database is fresh unless `--keep` is passed. `--reset`
  is the default written out; the two flags cannot be combined. The
  only accepted URL is the absolute SQLite file
  `demo/investment_demo.db`. `postgresql://` and any other path are
  refused, and the error does not repeat the URL. Settings are built
  with explicit arguments and `_env_file=None`. Those values are
  published in the process environment before the app is imported, and
  copied onto the shared settings object, so a personal `DATABASE_URL`
  in `.env` or in the shell is not the demo database. `SECRET_KEY` is
  taken from the process environment when it is set; otherwise the
  process generates one with `secrets.token_urlsafe(32)`. It is not
  printed and it is not written to disk. `uvicorn.run` is called with
  `host="127.0.0.1"`. `main.py` already binds `127.0.0.1` in its
  `__main__` block; the demo does not call that block.
  `app/data_collectors/` and the currency code were not edited, so this
  branch does not wrap the fake collector. PR #70 is in review and
  touches the live-collector wrapper plus those docs files.
- Verification: no `.env`, `DATABASE_URL` unset. CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1170 passed, 121 deselected, total coverage 95.60%. Scoped
  `black`, `isort`, and `flake8` on `scripts/run_demo.py` and
  `tests/test_run_demo.py` passed. PostgreSQL was not run locally
  (no `TEST_POSTGRES_DSN`). GitHub Actions
  [run 38703046058](https://github.com/Waber/Investment-AI-Companion/actions/runs/38703046058)
  on `8cde777` completed with conclusion success: SQLite job
  `116315619295` success, PostgreSQL job `116315618716` success.
  A manual loopback run
  with `DATABASE_URL` and `SECRET_KEY` unset and no `.env` printed
  the URL, seeded 6 companies and 20 metrics, and served `/`,
  `/docs`, `/ui`, and the company list on `127.0.0.1`. A second run
  with `--keep` reported 0 created and 6 companies already present.
  The console text did not include a secret.
- AI model: Grok 4.7. Account usage was not available in this session.
- Time tracking (2026-10-15, UTC): session start 07:39. Full SQLite
  suite finished 08:00.
- Next: #26 together with #16.

## 2026-10-14 - Collector guard and currency normalization, part 2 (#24)

- Scope: the two open items of
  [#24](https://github.com/Waber/Investment-AI-Companion/issues/24).
  `app/data_collectors/guard.py` adds `guard_collector(inner, policy)`:
  a TTL cache per capability (LRU-bounded, deep copies, the original
  `retrieved_at` kept), a sliding-window rate limit, and retries of
  `TransientProviderError` with full-jitter exponential backoff.
  Twelve `COLLECTOR_*` settings with bounds are in `app/core/config.py`.
  With `DATA_COLLECTOR=yahoo`, `get_collector()` returns one shared
  guarded Yahoo collector; `fake` mode is unchanged. Currency codes are
  stored in uppercase except Yahoo's `GBp` and `ZAc`.
  [Spec](superpowers/specs/2026-10-13-collector-guard-design.md),
  [plan](superpowers/plans/2026-10-13-collector-guard.md).
- Decisions by the owner: the guard sits in front of Yahoo now, not only
  as a hook. Defaults: profiles 24 h, metrics 1 h, prices 15 min, funds
  24 h; 30 provider calls per 60 s with a 5 s max wait; 2 retries with
  a 1 to 8 s backoff.
- Decisions by the controller:
  - The guard class is built from one mixin per capability the inner
    collector has, not with `__getattr__`. In Python 3.12, `isinstance`
    against a protocol uses `inspect.getattr_static`, which does not
    see `__getattr__` (checked on 3.12.15). A guarded Yahoo collector
    is therefore not a `FundAttributes`.
  - A full rate limit raises a plain `ProviderError` (HTTP 502) and is
    not retried. The max wait is cumulative per attempt.
  - After the final review, a "no data" answer got its own cache time,
    `COLLECTOR_CACHE_TTL_NO_DATA_SECONDS` (300 s, capped by the
    capability's TTL). yfinance can report a hidden HTTP failure as no
    data, and a 24 h cache would turn one failure into a false 404 for
    a day. The spec was amended.
  - Mapping yfinance errors to `TransientProviderError` stays in R1
    (#54), so the retry path is exercised by tests only for now.
  - Stored currency rows are not rewritten, because there are no
    migrations. An old lowercase row can show as a separate `/ui`
    currency filter option.
- Verification: the CI command (`pytest -q -p no:cacheprovider
  -W error::DeprecationWarning --cov=app --cov=main --cov=scripts
  --cov-branch --cov-fail-under=80`) gives 1259 passed, 121 deselected,
  coverage 95.68% (baseline 1134 passed, 95.24%). `pytest -m
  integration` gives 105 passed, 16 skipped (no PostgreSQL here).
  Scoped black and isort are clean; flake8 shows only the two E501
  lines in `tests/test_provider_data_hygiene.py` that are on `master`.
  The thread test fails in 10 of 10 runs with a no-op lock and passes
  10 of 10 with the real lock.
- Backlog: store `retrieved_at` (for example in
  `companies.last_data_update`) so the data age is visible after a
  cache hit; typing of the guarded class for mypy (not a CI gate yet);
  two optional test nits (the max-wait test hangs instead of failing on
  a lock-held-while-sleeping regression, which CI's 15-minute timeout
  catches; log assertions on the combined text). Then #25.
- Review: every task had a task review. Task 1 needed one fix round
  (the commit trailer had no blank line before it) and Task 4 one (the
  README table needed a blank line after it). The final whole-branch
  review found one Important gap (the no-data cache time) and three
  test gaps (a thread test that could not see a missing lock, no test
  for the cumulative max wait, a log test without the method name and
  level). One fix wave closed them, and the scoped re-review said ready
  to merge. The controller's closing commit fixed one README wording
  nit from that re-review.
- Pull request: [PR #72](https://github.com/Waber/Investment-AI-Companion/pull/72),
  opened on 2026-10-15 with the owner's go-ahead. It closes #24 on
  merge. PR #70 from Cursor Agent, opened the same morning, implements
  the same part 2; the owner merges one of the two and closes the
  other.
- AI model: Claude Opus 5.5 (Claude Code) as controller (spec, plan,
  rulings, this entry). Implementers: Claude Haiku 4.5 (Tasks 1 and 5)
  and Claude Sonnet 5.5 (Tasks 2 to 4 and the final fix wave).
  Reviewers: Claude Sonnet 5.5 (Tasks 1, 2, 4 and 5), Claude Opus 5.5
  (Task 3, the final review and its re-review), and Claude Haiku 4.5
  (the two small fix re-reviews). Account usage was not available in
  this session.
- Time tracking (+0200): 2026-10-13, part 2 started at 15:00 (the
  owner's request; design questions and answers, not in git); spec
  commit 17:57; plan commit 18:15. 2026-10-14, execution started at
  11:22 (the owner chose subagent-driven). Git times by commit subject:
  "feat: add the collector guard settings and policy" 11:28; "feat: add
  the collector guard with capabilities and a TTL cache" 11:33; "feat:
  add the rate limit and retry with backoff" 11:37; "feat: put the
  collector guard in front of Yahoo" 11:44 and its README fix 11:47;
  "feat: store currency codes in uppercase" 11:50; the final review,
  then the fix wave 12:07 to 12:10; the controller's closing docs
  commit after the re-review. 2026-10-15: branch pushed and PR #72
  opened at 13:13.

## 2026-10-12 - Collector interface and offline fake, part 1 (#24)

- Scope: part 1 of
  [#24](https://github.com/Waber/Investment-AI-Companion/issues/24).
  Provider-neutral contracts (`app/data_collectors/base.py`: provenance,
  `Sourced`, `ProviderError`, capability protocols), an offline
  `FakeCollector`, the Yahoo collector moved onto the contracts, and a
  `DATA_COLLECTOR` setting (`fake` or `yahoo`) behind the new
  `get_collector()` dependency. The root `conftest.py` forces `fake` (all
  selection modes) and makes yfinance use `requests`.
- Decisions: #24 is split. Part 2 (cache, rate limit, backoff, currency
  normalization) is a later PR. `DATA_COLLECTOR` defaults to `yahoo` so a
  normal run behaves as before; tests and the demo (#25) select `fake`.
  The fake takes stock profiles from `fixtures/demo-v1.json`, so the
  `[IAC-DEMO-V1]` marker and the `/ui` synthetic badge keep working;
  fake funds carry the marker too. Fund key metrics are all `None`.
  Fake stock metrics follow the fixture's latest annual row: P/E is
  `None` for a net loss, ROE and margin have the sign of net income, and
  `debt_to_equity` is a percent like Yahoo's. `debt_to_assets` from the
  balance sheet goes to R1 (#54); the ETF/MUTUALFUND guard is added now.
  Provenance is carried by collector results but not yet stored or
  returned.
  `DEMO_PL_EMPTY` keeps its profile (fetch-company creates it); its key
  metrics and history are "no data" (`None`). fetch-company: no data is
  404 (provider-neutral text), `ProviderError` is 502
  `Data provider error`.
- Task 4 extras: yfinance 1.7 hides exceptions, so an unknown ticker gave
  a near-empty `info`. `fetch_company_info` and `fetch_key_metrics` now
  return `None` without a name (404, not 502; one shared helper).
  Provenance is built outside the `try`, so a bad clock is a
  `ValueError`, not a 502.
- Network guard (tests only, `tests/network_guard.py`): an autouse
  fixture makes any connect, `connect_ex`, `create_connection`,
  `getaddrinfo` or `gethostbyname` to a non-loopback address fail. Every
  blocked attempt is recorded and also fails the test at teardown, so a
  swallowed error is still caught. It sees Python code that uses the
  `socket` module (`requests`, `urllib3`, `httpx`). It cannot see C
  clients that open their own sockets: libpq (psycopg2) and libcurl
  (`curl_cffi`). yfinance 1.7 prefers `curl_cffi`, so the root
  `conftest.py` sets `YF_DISABLE_CURL_CFFI=1` and yfinance uses
  `requests`, which the guard sees. A test makes a real yfinance call
  with raising stand-ins under the guard (socket, curl_cffi, no proxy,
  dummy cookie cache), so it cannot reach the network even if the guard
  regresses; it asserts the guard recorded the attempt. Tests marked
  `integration` are exempt (PostgreSQL). The Windows asyncio proactor
  loop is not covered.
- Verification: full CI command (`pytest -q -p no:cacheprovider
  -W error::DeprecationWarning --cov=app --cov=main --cov=scripts
  --cov-branch --cov-fail-under=80`): 1102 passed, 121 deselected,
  coverage 95.22% (baseline 1019 passed, 94.76%). `pytest -m
  integration`: 105 passed, 16 skipped (no PostgreSQL here, so the
  PostgreSQL tests were not run). `pytest -m ''`: 1207 passed, 16
  skipped. Scoped black and isort clean; flake8 shows two E501 lines in
  `tests/test_provider_data_hygiene.py` that exist on master.
- Backlog: under yfinance `hide_exceptions`, a Yahoo HTTP failure can
  look like "no data" (404) or an empty history instead of a
  `ProviderError`; fix in R1 (#54), documented on the collector class.
  Fund key metrics (52-week range, average volume, beta, dividend yield
  from the fake bars) belong to I2 (#27) and I3 (#28). The fake P/E is
  not yet consistent with P/B divided by ROE (for example
  `DEMO_DE_INDUSTRY`); fix with the demo-v2 data in I2 (#27). Part 2 of
  #24 and #25 remain.
- Review: each task had a task review; Task 4 needed two fix rounds
  (the fake setting under integration selections, and the guard not
  seeing yfinance's `curl_cffi`). The final whole-branch review asked
  for one fix wave (Yahoo key metrics for an unknown ticker, fake
  metrics against the fixture, docs); its scoped re-review said ready
  to merge.
- AI model: Claude Opus 5.5 (Claude Code) as controller; Claude Sonnet
  5.5 implementers for Tasks 1-4 and the review fixes; reviewers Claude
  Sonnet 5.5 (Tasks 1-2, re-reviews of #19) and Claude Opus 5.5
  (Tasks 3-4, Task 4 re-reviews, the final review and its re-review).
  Account usage was not available in this session.
- Time tracking (2026-10-12, +0200): session start 14:12 (the
  controller's first command; not in git; setup, Python 3.12 venv,
  baseline run, plans). Git times, by commit subject: "docs: plan the
  collector interface" 14:34; "feat: add provider-neutral data collector
  contracts" 14:36; "feat: add deterministic offline FakeCollector"
  14:40; "feat: put the Yahoo collector on the contracts" 14:45;
  "feat: select the data collector with DATA_COLLECTOR" 14:57 (an
  import-sort fix at 14:57 was folded into it before the push);
  "docs: document DATA_COLLECTOR" 14:58; "test:
  force the fake collector in every selection mode" 15:13; "docs:
  correct the collector docs" 15:13; "test: make the guard tests unable
  to reach the network" 15:27; "docs: correct the journal after the
  second review" 15:27; "fix: return no data for unknown Yahoo key
  metrics" 15:53; final-wave docs commit 15:53; the controller's
  closing docs commit after the final re-review. Before the push, the
  controller rewrote two co-author trailers (Tasks 1 and 2 were written
  by Claude Sonnet 5.5 but carried the Opus line from the plan) and
  folded the import-sort commit; the tree did not change. Total 14:12
  to 15:58 (the closing docs commit).
- Published as
  [PR #68](https://github.com/Waber/Investment-AI-Companion/pull/68)
  (Refs #24, part 1). The owner chose to push; the pull request was
  opened at 17:17 +0200. The R1 hand-offs are posted on
  [#54](https://github.com/Waber/Investment-AI-Companion/issues/54#issuecomment-6127198668)
  at 17:19.
- Rebase (2026-10-13): the owner merged PR #67 (#19) first, at 14:38
  +0200, as merge commit `114c93a`. The branch was rebased onto it.
  Only `docs/development-journal.md` and `docs/work-state.md`
  conflicted, because both pull requests added a top entry. Both
  entries are kept (#24 above #19), and the #19 work-state section now
  says PR #67 is merged. The #67 code came in unchanged. After the
  rebase: CI command 1134 passed, 121 deselected, coverage 95.24%;
  `-m integration` 105 passed, 16 skipped; `-m ''` 1239 passed, 16
  skipped. Pushed with `--force-with-lease` (see this commit's git
  time).
- Merged (2026-10-13): the owner merged PR #68 at 14:48 +0200 as merge
  commit `107adf0`, after CI passed on SQLite and PostgreSQL. The merge
  also closed #24. The PR body said it "does not close" the issue, and
  GitHub reads "close" followed by an issue number as a closing
  keyword, even after "does not". Part 2 is still open, so #24 was
  reopened at 14:55 with a comment that lists part 2. Lesson: a
  partial delivery says only "Refs" and never puts a closing keyword
  before the issue number. The session worktrees and the merged local
  branches were removed. The merged remote branches and two backup refs
  are left for the owner.

## 2026-10-12 - Bound skip and limit on the list endpoints (#19)

- Scope: `GET /api/v1/companies/`, `GET /api/v1/financial-metrics/`
  and `GET /api/v1/financial-metrics/company/{company_id}`. `skip`
  must be at least 0 and `limit` must be 1 to 1000. Out-of-range
  values return 422 through the existing validation handler. Before
  this, `limit=-1` reached SQL and SQLite read it as no limit.
- Decision: `MAX_PAGE_LIMIT = 1000`, the value proposed in the
  issue. The default stays `limit=100`, `skip=0`. The bounds live
  in `app/api/pagination.py` as two `Annotated[int, Query(...)]`
  types, so the three endpoints share one definition. The value
  1000 awaits the owner's or the Code Reviewer's OK in the pull
  request, as the issue requires.
- Tests: the strict-xfail test named in the issue is not on the
  remote (`qa/known-defects-xfail`), so
  `tests/test_pagination_bounds.py` was written from the task
  brief. It covers 422 for `skip=-1`, `limit=-1`, `limit=0` and
  `limit=1001`, 200 for `limit=1000` and `skip=0&limit=1`, the
  default page of 100 with 101 rows (companies and both metrics
  lists), the `loc` of the error, and the OpenAPI minimum, maximum
  and default. RED: 12 cases returned 200 instead of 422.
- Found in review: `skip=9223372036854775808` returned HTTP 500 on
  SQLite (integer overflow). `skip` now has `le=2**63 - 1`
  (`MAX_SKIP`, the signed 64-bit maximum). `2**63` returns 422 and
  `2**63 - 1` returns 200.
- Verification, from the worktree root with the Python 3.12 venv:
  - `python -m pytest -q -p no:cacheprovider
    tests/test_pagination_bounds.py`: 32 passed.
  - `python -m pytest -q -p no:cacheprovider
    tests/test_delete_and_not_found_api.py tests/test_seed_demo.py`:
    72 passed.
  - `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider
    -W error::DeprecationWarning --cov=app --cov=main --cov=scripts
    --cov-branch --cov-report=term-missing --cov-fail-under=80`:
    1051 passed, 119 deselected, total coverage 94.78%.
  - `python -m black --check` on the four changed `.py` files:
    clean. `python -m isort --check-only` and `python -m flake8` on
    `app/api/pagination.py` and `tests/test_pagination_bounds.py`:
    clean.
  - isort and flake8 already failed on master for `companies.py`
    and `financial_metrics.py` (flake8: 14 findings, same count
    now). The new import lines sit in the old order in those files
    and the branch does not re-sort them.
  - `python -m pytest -q -p no:cacheprovider -m integration` with
    no `TEST_POSTGRES_DSN`: 103 passed, 16 skipped. The 16 skips
    need PostgreSQL.
- Review: the Code Reviewer agent (Claude Opus 5.5) found 2
  Important and 8 Minor issues and approved `MAX_PAGE_LIMIT = 1000`.
  All were fixed except the commit trailer, which names the model
  that wrote the commits. A scoped re-review (Claude Sonnet 5.5)
  marked every finding addressed.
- Published as
  [PR #67](https://github.com/Waber/Investment-AI-Companion/pull/67).
  Not merged. The owner's OK on 1000 is asked for in the PR.
- AI model: Claude Sonnet 5.5 implementer via Claude Code, Claude
  Opus 5.5 controller. Account usage was not available in this
  session.
- Time: session started about 14:10 +0200 (setup, baseline run,
  plans). Plan commit 14:34, implementation commit 14:37. Review
  and the fix round followed; the fix round ended at 14:47 +0200.
  The pull request was opened at 14:59 +0200.

## 2026-10-10 - Point the requirements at issues #57, #58 and #65

- Scope: after PR #64 was squash-merged to `origin/master` as
  `34f462a`, record the GitHub issues agents should pick up
  later. No application code.
- Decision: #57 and #58 stay the portfolio and signal issues.
  Their bodies now match requirements v0.4, including several
  monitored portfolios and buy/sell signals without a
  not-advice notice. The AI Portfolio is a new deferred issue,
  #65, so it is not folded into the real-portfolio work.
- Verification: issue text plus
  `tests/test_secure_config.py::test_tracked_files_have_no_personal_machine_paths`
  (1 passed). The UI suite was not run.
- Published as
  [PR #66](https://github.com/Waber/Investment-AI-Companion/pull/66).
  Not merged.
- AI model: Grok 4.7 (Cursor). Account usage was not available
  in this session.

## 2026-10-10 - Record portfolios, buy/sell signals, and the AI Portfolio

- Scope: documentation only. Raul asked to check whether the
  docs already describe three later features, and to add what was
  missing on its own branch. No application code.
- What was already written: section 12.3 stored private
  portfolios and holdings (#57) without monitoring rules.
  Section 12.4 already allowed post-demo buy/sell signals (#58)
  and required a "not investment advice" notice on every signal.
  An experimental model-managed portfolio was not described.
- Decision, portfolios: several real portfolios. Add, edit and
  remove holdings. Total value is the sum of holding market
  values. Split by instrument type (stock, ETF, ETC). Gain/loss
  per holding and for the portfolio. A missing price is not zero.
  No FX conversion. No broker orders.
- Decision, signals: the application, together with an agent, may
  issue buy and sell signals. Raul does not want a notice that
  this is not investment advice. The demo still has no signals.
  The shipped `/ui` banner stays until a later UI change; it is
  not a requirement anymore. Sources, freshness, assumptions,
  risks and uncertainty stay.
- Decision, AI Portfolio: a later virtual book, separate from
  real portfolios. Editable virtual cash, a monthly top-up whose
  amount is also editable, virtual purchases from the model's
  predictions, and virtual sales when the model exits a position.
  Performance tracking does not count added cash as gain. No
  GitHub issue yet.
- Files: `docs/product-requirements.md` (draft v0.4),
  `AGENTS.md`, `README.md`, `docs/demo-data.md`,
  `docs/RUN_DEMO.md`, this journal, `docs/work-state.md`.
- Verification: no behaviour change. `tests/test_ui_pages.py`
  still expects the current banner, and those tests were not
  run. `tests/test_secure_config.py::test_tracked_files_have_no_personal_machine_paths`
  was run after the edits.
- Published as
  [PR #64](https://github.com/Waber/Investment-AI-Companion/pull/64).
  Not merged.
- AI model: Grok 4.7 (Cursor). Account usage was not available
  in this session.

## 2026-10-09 - Rebase /ui onto secure defaults and add the demo guide (#29)

- Scope: rebase
  [PR #63](https://github.com/Waber/Investment-AI-Companion/pull/63)
  onto `origin/master` `8ee15e3` after PR #61 merged. Same branch
  `cursor/ui-skeleton-htmx-aa8b`. No merge of master into the
  branch. Disclaimer wording, autoescape, the website check, the
  type filter, and the `/ui` id 404 rules stay.
- Conflict, `main.py`: kept both import lines
  (`TrustedHostMiddleware` and `StaticFiles` / the `/ui` router)
  and both behaviours. CORS still uses `settings.cors_origins`.
  `TrustedHostMiddleware` still wraps the app.
  `python main.py` still binds `127.0.0.1`. `/ui` and `/static`
  stay mounted.
- Conflict, journal and work-state: #61's entries and the
  personal-path clean-up stay. The `/ui` section stays the current
  one. The first `/ui` commit had introduced the old personal
  database URL in the sqlite seed tests. That string was replaced
  with `postgresql://investment_ai@localhost:5432/investment_ai`
  in that commit so the guard passes on every commit. No personal
  path was put back.
- Decision, docs: `docs/RUN_DEMO.md` is the copy-pasteable demo.
  README links it near the top. `docs/demo-data.md` points there
  instead of repeating the commands. `SECRET_KEY` is required.
  The bind is `127.0.0.1`. `ALLOWED_HOSTS` is left at its default.
- Verification: no `.env` during pytest. Each rebased commit
  passed
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`.
  Dependency commit: 965 passed, 119 deselected, exact 92.79%.
  Feature commit: 1011 passed, 119 deselected, exact 94.61%.
  Type-filter commit: 1011 passed, 119 deselected, exact 94.63%.
  History-restore commit: 1015 passed, 119 deselected, exact
  94.71%. ASCII-id commit: 1017 passed, 119 deselected, exact
  94.72%. Review commit: 1019 passed, 119 deselected, exact
  94.76%. The docs commits do not change Python and repeat the
  count of the commit they follow. The demo commands in
  `docs/RUN_DEMO.md` were run: seed created 6 companies and 20
  metric rows, `/ui` returned 200 with the disclaimer and the
  language switch, and a non-allowed Host returned 400.
  `docker` is not installed here, so the README `docker run` was
  not executed. `-m integration` with `TEST_POSTGRES_DSN` unset
  was 103 passed, 16 skipped, 1019 deselected.
- AI model: Grok 4.7 (Cursor cloud agent). Account usage was not
  available in this session.

## 2026-10-08 - Review fixes for /ui ids and website links (#29)

- Scope: follow-up on
  [PR #63](https://github.com/Waber/Investment-AI-Companion/pull/63),
  same branch `cursor/ui-skeleton-htmx-aa8b`. Code review of head
  `d64cbbb`. Disclaimer wording, autoescape, the type filter, and
  `/api/v1` id parsing stay. `docs/demo-data.md` was not rewritten
  for `SECRET_KEY` or the bind host. PR #61 is not in this branch.
- Decision, ids: `int` raises `ValueError` on an ASCII digit
  string longer than about 4300 characters, and that was a
  plain-text 500. The helper now returns `None` when the string
  is not ASCII, is not all digits, or is longer than 19
  characters, before calling `int`. A value that still exceeds
  `2**63 - 1` is also `None`. `01` and `007` are not a second URL
  for rows 1 and 7. The single character `0` is still a normal
  id. All of these misses are the existing HTML 404.
- Decision, responses: every `/ui` response also sends
  `Cache-Control: no-store`, next to `Vary: HX-Request`.
- Decision, websites: a `javascript:` or `data:` URL is still
  not a link when it has a host. Unicode format characters
  (category `Cf`, including U+202E and U+200B) and DEL (code
  point 127) are rejected in the view-model. Approved links
  stay `http` or `https` with `rel="noopener noreferrer"`.
- Decision, htmx: the config meta also sets `allowEval` and
  `allowScriptTags` to false, next to `includeIndicatorStyles`.
  The script stays the local file. No CDN.
- Verification: no `.env`, `DATABASE_URL` unset, the CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 900 passed, 119 deselected, exact 94.95%. The docs commit
  does not change Python and repeats that result. `black --check`,
  `isort`, and `flake8` passed on the touched Python files.
- AI model: Grok 4.7 (Cursor cloud agent). Account usage was not
  available in this session.

## 2026-10-08 - ASCII instrument ids and htmx CSP config (#29)

- Scope: follow-up on
  [PR #63](https://github.com/Waber/Investment-AI-Companion/pull/63),
  same branch `cursor/ui-skeleton-htmx-aa8b`. Disclaimer wording,
  autoescape, the http/https website check, and the type filter
  stay. The JSON API is unchanged.
- Decision, ids: `str.isdigit` is true for Unicode digits.
  Superscript `²` made `int` raise (HTTP 500). Arabic-Indic `١`
  became `1` and opened that company. A 23-digit value overflowed
  SQLite's signed 64-bit integer. `/ui` now accepts an id only
  when the string is ASCII, every character is a digit, and the
  integer is `<= 2**63 - 1`. Anything else is the existing HTML
  404.
- Decision, htmx: `base.html` sets
  `<meta name="htmx-config" content='{"includeIndicatorStyles":false}'>`
  before the vendored script. HTMX otherwise injects an inline
  style, which the page CSP does not allow.
- Verification: no `.env`, `DATABASE_URL` unset, the CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 898 passed, 119 deselected, exact 94.91%. The docs commit
  does not change Python and repeats that result. `black --check`,
  `isort`, and `flake8` passed on the touched Python files.
- AI model: Grok 4.7 (Cursor cloud agent). Account usage was not
  available in this session.

## 2026-10-08 - QA fixes on /ui (#29)

- Scope: follow-up on
  [PR #63](https://github.com/Waber/Investment-AI-Companion/pull/63),
  same branch `cursor/ui-skeleton-htmx-aa8b`. QA reviewed head
  `766fbfd`. The type filter and the skip link from the previous
  entry stay. Disclaimer wording, the website http/https check,
  autoescape, and the bind host are unchanged. No CDN was added.
- Decision, history restore: `HX-History-Restore-Request: true`
  returns the full page even when `HX-Request` is also set. HTMX
  writes that response into `body`, so a fragment would drop the
  header, the language switch, and the disclaimer. Every `/ui`
  response sends `Vary: HX-Request`.
- Decision, return path: `safe_next` still requires a `/ui` prefix.
  It also rejects a `..` segment after decoding, so
  `next=/ui/../api/v1/companies/` stays on `/ui`.
- Decision, unknown id: `/ui/instruments/{id}` takes a string. A
  non-integer such as `abc` renders the HTML 404. The API's JSON
  422 handler is unchanged.
- Decision, headers: `/ui` sends `Content-Security-Policy` with
  `default-src 'self'`, `base-uri 'self'`, `form-action 'self'`,
  and `frame-ancestors 'none'`, plus `X-Frame-Options: DENY`,
  `X-Content-Type-Options: nosniff`, and
  `Referrer-Policy: no-referrer`. The local HTMX page does not
  need another host.
- Decision, docs and tests: the sqlite seed tests use
  `postgresql://investment_ai@localhost:5432/investment_ai`. The
  Settings default is unchanged. `docs/demo-data.md` says the
  server filters the list. `SECRET_KEY` is still not required on
  this branch, and `python main.py` still binds `0.0.0.0`. After
  #61, the demo seed and uvicorn both need `SECRET_KEY` and the
  bind becomes `127.0.0.1`. The template scan rejects `| safe`
  with a space. `static/vendor/README.txt` records the sha256 of
  the vendored htmx file.
- Verification: no `.env`, `DATABASE_URL` unset, the CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 896 passed, 119 deselected, exact 94.89%. The docs commit
  does not change Python and repeats that result. `black --check`,
  `isort`, and `flake8` passed on the touched Python files.
- AI model: Grok 4.7 (Cursor cloud agent). Account usage was not
  available in this session.

## 2026-10-08 - Type filter and keyboard focus on /ui (#29)

- Scope: follow-up on
  [PR #63](https://github.com/Waber/Investment-AI-Companion/pull/63),
  same branch `cursor/ui-skeleton-htmx-aa8b`. Issue #29 asks the
  list to filter by type, exchange, and currency. The list already
  filtered by search, exchange, and currency. This adds type.
  Disclaimer text, the bind host, and the website link rule are
  unchanged.
- Decision: the type dropdown is built from the distinct
  `instrument_type` values the view-model returns. On this branch
  that is `stock`. The option label is `type.stock` ("akcja" /
  "stock"). The empty option is the existing "wszystkie" / "any"
  string. An unknown `type` query matches no rows and returns 200.
  A missing catalog key still renders, because `translate` returns
  the key.
- Decision, accessibility only: a skip link to `#main`, `scope="col"`
  on the list table headers, and a `:focus-visible` outline. No
  `outline: none`. No new external asset.
- Verification: no `.env`, `DATABASE_URL` unset, the CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 892 passed, 119 deselected, exact 94.81%. `black --check`,
  `isort`, and `flake8` passed on the touched Python files. In the
  browser, choosing Typ "akcja" requested `type=stock` and kept the
  six demo rows. `type=etf` returned the Polish empty state and
  still offered "akcja". English showed "Type", "any", and "stock",
  plus "Skip to main content" and seven `scope="col"` headers.
- AI model: Grok 4.7 (Cursor cloud agent). Account usage was not
  available in this session.

## 2026-10-08 - /ui instrument list and detail (D4, #29)

- Scope: the first runnable UI demo, rebased onto `origin/master`
  `d7f6798` after PR #60 (the PostgreSQL harness, #9). Branch
  `cursor/ui-skeleton-htmx-aa8b`. Refs #29. This does not close #29,
  and it does not start #26, #27, #28, or #25.
  [PR #63](https://github.com/Waber/Investment-AI-Companion/pull/63).
  PR #61 (secure defaults) is still open and was not copied.
- Decision, read model: templates bind to instrument view-models.
  `CompanyDB` stays behind `app/ui/queries.py`. Every current row is
  type `stock` until #26. A description that starts with
  `[IAC-DEMO-V1]` is synthetic and shows the badge. The list filters
  in Python (`casefold`) because the demo file is small and SQLite
  `LIKE` is not the same case-fold for every character.
- Decision, website links: `website_view` is the only place that
  decides whether a stored string becomes an `href`. After stripping
  whitespace, only an `http` or `https` URL with a host is a link
  (`javascript:` and `data:` stay plain text). The template checks
  `instrument.website.href` and copies `rel` from the view-model
  (`noopener noreferrer`). An empty value uses the catalog string
  "brak danych" / "no data".
- Decision, pages: Jinja2 3.1.6 is pinned and locked. Autoescape is
  on. HTMX 2.0.10 (Zero-Clause BSD) and the CSS are files under
  `static/`; the script URL is root-relative, not a CDN. Language is
  a cookie (`ui_lang`), Polish by default, with the same catalog
  keys in PL and EN. Numbers and dates are formatted in Python, not
  with `locale.setlocale`. `python-multipart` is not added.
- Decision, demo database: `scripts/seed_demo.py --database-url`
  writes sqlite through the same create/skip rules as the HTTP
  seeder. File sqlite engines set `check_same_thread=False` so a
  sync route can use a pooled connection. The personal
  `DATABASE_URL` default is unchanged. PR #60 did not change
  `requirements.txt` or either lock, so this pin was not recompiled.
- Decision, PostgreSQL job: the UI tests are not marked
  `integration`. The default command still deselects that marker.
  The PostgreSQL job runs only `-m integration` and does not execute
  these pages. Deselected tests are not skips, so the zero-skip
  guard does not see them.
- Verification: no `.env`, `DATABASE_URL` unset during pytest.
  Dev venv `/tmp/iac-venv` (Python 3.12.3) installed from
  `requirements-dev.lock` with `--require-hashes`. Command:
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  After the rebase onto `d7f6798`: the dependency commit was
  846 passed, 119 deselected, exact 92.58%. The feature commit
  was 892 passed, 119 deselected, exact 94.79%. The docs commit
  does not change Python and repeats that 892 / 119 / 94.79%.
  `-m integration` with no `TEST_POSTGRES_DSN` was 103 passed,
  16 skipped, 892 deselected. Those 16 skips are the harness
  tests that open PostgreSQL. The UI tests are in the 892
  deselected, not in the skips.
  `black --check`, `isort --check-only`, and `flake8` passed on the
  touched Python files before the rebase. A separate venv installed
  from `requirements.lock` only, then the commands in
  `docs/demo-data.md` (with that venv's Python): seed created 6
  companies and 20 metric rows; uvicorn on `127.0.0.1:8000` returned
  200 for `/ui`, `/ui/instruments/1`, `/static/ui.css`, and the HTMX
  file. In the browser, the list filter swapped to `DEMO_US_GROWTH`
  only, the English cookie rendered "It is not financial advice",
  and `https://vistula.example.com/` was a link with
  `rel="noopener noreferrer"`.
- AI model: Grok 4.7 (Cursor cloud agent). Account usage was not
  available in this session.

## 2026-10-08 - Code Reviewer round 1 on ff300e6

- Scope: requested changes from the review of `ff300e6`, added
  after the rebase onto `d7f6798`. Each item is its own commit.
- B1: `max_length=20` stays on `FinancialMetricsCreate` only.
  `FinancialMetricsUpdate` does not set `period_type`. A SQLite
  row with a 25-character `period_type` returns HTTP 200 from
  `GET /api/v1/financial-metrics/company/{id}`. `Company` and
  `HistoricalData`, the other response models, have no write-time
  length limits. A test locks that in.
- Nit 1: README and `.env.example` say `ALLOWED_HOSTS` is
  enforced, so any other Host gets HTTP 400 `Invalid host header`.
- Nit 2: the IDE settings-errors line says to check `SECRET_KEY`
  is at least 32 characters.
- Nit 3: `ide-startup.md`, `api-demo.md`, and `demo-data.md` name
  `~/IdeaProjects/Investment-AI-Companion`. The historical cluster
  block tells the reader to substitute their own `$TMPDIR` path.
  The personal-path guard still passes.
- Nit 4: a missing `SECRET_KEY` defaults to `""`. `validate_default`
  runs the existing validator, so the error includes
  `token_urlsafe(32)` instead of a bare `Field required`.
- Nit 5: `ALLOWED_HOSTS` entries are stored in lowercase, so
  `LocalHost` is `localhost`. Whitespace and control characters
  inside an entry are rejected, so `local host` fails startup.
- Nit 6: the personal-path test requires `git grep` exit code 1.
  Exit 0 is a match. Any other code is a failed search, not a pass.
- Nit 7: the PostgreSQL `dup` versus `DUP` expected failure stays
  strict. Uppercasing makes `dup` the same unique-index 500 as
  issue #16, so the reason says that instead of claiming case
  folding has not landed.
- Follow-up on nit 4: the empty `SECRET_KEY` default made
  `test_stray_dotenv_database_url_is_ignored` fail, because `""`
  is a substring of every line. The check now runs only when the
  code default is a non-empty string. The harness key in the
  output is still required.
- Verification: SQLite CI command, 965 passed, 119 deselected,
  exact 92.79% (1145 statements, 77 missed, 256 branches, 14
  partial). DSN, isolation, and skip-guard integration tests:
  103 passed, no database. No local PostgreSQL or Docker, so the
  API-level PostgreSQL job is left to GitHub Actions.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not
  measured. Account usage was not available in this session; no
  percentage recorded.

## 2026-10-08 - Rebase onto the merged PostgreSQL harness (#60, #9)

- Scope: `cursor/secure-config-provider-hygiene-c91c` rebased onto
  `origin/master` `d7f6798` after pull request #60 merged.
- Decision, journal: newest first. The secure-defaults entry stays
  above #60's entries, and those entries are kept. This branch
  keeps its own personal-path cleanup. Master's older journal
  text still names a home-directory prefix and a
  temporary-directory prefix; using that text fails
  `test_tracked_files_have_no_personal_machine_paths`.
- Decision, work-state: one next action, #24. The branch line names
  `d7f6798`. Incomplete work no longer says the PostgreSQL harness
  stays later. Alembic (#8) still does. #60's harness facts that
  are still true stay in that section, including the integration
  client on `http://127.0.0.1` and the 34-character test secret.
- #60 already reads the database URL default from `Settings` and
  does not add personal paths. No application code changed in this
  rebase for `SECRET_KEY`, `ALLOWED_HOSTS`, or CORS.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not
  measured. Account usage was not available in this session; no
  percentage recorded.

## 2026-10-08 - Secure defaults, neutral paths, and provider hygiene (#45, #47, #50)

- Scope: #45 (secure config defaults), #47 (neutral defaults and a
  personal-path guard), and #50 (provider-data hygiene and ticker
  validation) in one pull request. Branch
  `cursor/secure-config-provider-hygiene-c91c`, based on master
  `d568663`.
  [PR #61](https://github.com/Waber/Investment-AI-Companion/pull/61).
  Blank tickers on company create and fetch-company are
  rejected, which is the remaining #17 case, so this pull request
  also closes #17. Out of scope: auth (#48), the collector interface
  (#24), negative pagination (#19), duplicate ticker (#16),
  pip-audit/Dependabot (#52), and universal locks (#53).
  `docs/product-requirements.md` was not edited.
- Decision, ALLOWED_HOSTS: enforced with Starlette
  `TrustedHostMiddleware`. The default is `localhost` and
  `127.0.0.1`. The middleware is added after CORS so it is the
  outermost layer. A host that is not in the list gets HTTP 400
  and the plain text `Invalid host header`. The port is stripped
  before the comparison, so `127.0.0.1:8000` is accepted. Test
  clients use `base_url="http://127.0.0.1"`. The setting stays
  because an unused security-looking list would be misleading.
- Decision, SECRET_KEY: kept and required. Nothing signs tokens
  with it yet, but `GET /api/v1/test-config` reports whether it is
  set, and a default or a placeholder would look like a real
  secret. There is no default. Empty, whitespace, `your-secret-key-here`,
  and `replace-this-in-local-env` fail settings construction.
  Tests and the demo set their own value. `.env.example` leaves
  the key empty and shows how to generate one.
- Decision, DEBUG and test-config: `DEBUG` defaults to false.
  `/api/v1/test-config` stays registered. When DEBUG is off the
  route returns 403. When DEBUG is on the body is presence flags
  only (check marks), never secret values or the database URL.
- Decision, CORS: pydantic-settings stays at 2.1.0. `NoDecode` is
  not in that release, and both hashed locks are unchanged. The
  field `BACKEND_CORS_ORIGINS` is a `str`. A validator accepts a
  comma-separated string, a JSON list string, and a Python list,
  then stores canonical origin strings. `settings.cors_origins`
  is the list the app reads. An invalid URL fails settings
  construction with a clear error. An empty string means no
  origins. This is the fix for the startup crash on a
  comma-separated value: pydantic-settings JSON-decodes `list`
  fields before validators run.
- Decision, bind address: `python main.py` and the documented
  uvicorn commands bind `127.0.0.1`, not every interface.
- Decision, DATABASE_URL: the code default is
  `postgresql://investment_ai@localhost:5432/investment_ai`.
  Tests and the demo still pass their own SQLite URLs. The value
  is not required from the environment.
- Decision, personal paths: tracked files use
  `~/projects/Investment-AI-Companion` and `$TMPDIR`. Historical
  journal and plan text was edited for those paths only. A pytest
  test runs `git grep` for a personal home-directory prefix, the
  old macOS temporary-directory prefix, and the previous local
  account name. The needles are built from string pieces so the
  test file itself does not contain them. After the docs edit
  there are zero matches, so there is no allowlist.
- Decision, ticker pattern: `^[A-Z0-9._\-^=]{1,20}$` after a
  control-character check, then strip and uppercase. The issue
  example was `{1,15}` without underscore. The demo fixture uses
  underscores (`DEMO_PL_TECH`) and `DEMO_DE_INDUSTRY` is 16
  characters. The database column is `String(20)`. The pattern
  matches the column and keeps the fixture loadable. It accepts
  `PKN.WA`, `CDR.WA`, `VWCE.DE`, `BRK-B`, `^GSPC`, `EURUSD=X`,
  and a 20-character symbol. It rejects 21 characters, blank,
  whitespace-only, CR/LF, and other control characters. Control
  characters are rejected before strip, so `"AAPL\n"` is not
  turned into `AAPL`. `None` still means "field omitted" on
  update. Currency keeps the letters it was sent with. Yahoo's
  `GBp` means pence, and rewriting it to `GBP` would treat the
  amount as pounds.
- Decision, provider errors: in `fetch_company_data`, pydantic
  `ValidationError` is caught before `ValueError` (it is a
  subclass) and returned as HTTP 502 with the fixed detail
  `Provider returned invalid company data`. The body does not
  include provider input. The log records field names and error
  types, and the ticker with `%r`. It does not call
  `logger.exception` on that error, because the exception text
  includes the input. Uniqueness `ValueError` stays HTTP 400
  with the business message. `update` returning `None` stays
  HTTP 500 with `Failed to update company`, and that path now
  logs the ticker. Unexpected exceptions stay HTTP 500 with
  `Error fetching company data`.
- `fetch-financial-metrics` was checked. It has no
  `ValidationError` or `ValueError` handler. It is still a
  placeholder. It uses the same `FetchCompanyRequest`, so a bad
  ticker is HTTP 422 before the handler runs.
- Length limits match the database columns: name 255, ticker 20,
  sector, industry, and country 100, website 500, exchange 50,
  currency 3. `description` is text and has no limit.
  `period_type` is 20 on the financial-metrics create and
  response models. Over-length user input is HTTP 422 on company
  create and update. Over-length or invalid provider data on
  fetch-company is HTTP 502.
- Log calls in `data_collection.py` and `yahoo_finance.py` pass
  the ticker as a `%r` argument. A CR/LF inside a ticker cannot
  forge a second log line. Request validation blocks those
  tickers at the API. The log tests bypass that validation and
  call the collector and the handler directly.
- History: four commits, and each one passes the CI pytest
  command. Tests are first and marked `xfail(strict=True)`, so
  the suite exits 0 while `--runxfail` shows assertion failures
  (not import errors). The fix commit removes those markers
  except the personal-path test, which still failed until the
  docs commit. That test is no longer xfail. The last commit
  only adds the pull request link.
- Client-visible behaviour: startup fails without a real
  `SECRET_KEY`. `DEBUG` defaults to false, so
  `/api/v1/test-config` is 403 until a local `.env` turns DEBUG
  on. A bad `Host` header is HTTP 400. The process binds
  `127.0.0.1`. A comma-separated `BACKEND_CORS_ORIGINS` no longer
  crashes startup. Blank, whitespace, and control-character
  tickers are HTTP 422 on company create, company update,
  fetch-company, and fetch-financial-metrics, and no row is
  written. Accepted tickers are stored uppercased and stripped.
  Over-length company fields and `period_type` are HTTP 422.
  Provider data that fails the company schema on fetch-company
  is HTTP 502 with the fixed detail above. Uniqueness is still
  HTTP 400. A missing company on update is still HTTP 500 with
  `Failed to update company`.
- Verification, from the repository root, no `.env`,
  `DATABASE_URL` unset, Python 3.12.3, packages from
  `pip install --require-hashes -r requirements-dev.lock`
  (the venv started on pip 24.0 and the lock upgraded pip):
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`.
  Test commit `e352413`: 865 passed, 51 xfailed, 14.91s, TOTAL
  92.93%. `--runxfail` failures were `AssertionError` or
  `pytest.fail`, not import errors. Fix commit `849b08a`: 918
  passed, 1 xfailed, 14.44s, exact coverage 93.41% (1035
  statements, 65 missed, 194 branches, 6 partial). Docs tree: 919
  passed in 14.56s, no xfailed, exact coverage 93.41%. Collector
  tests stay offline. `black
  --check` passed on the touched Python files. CI runs pytest
  only. `setup_database.py` still has the pre-existing flake8
  unused-import and E402 findings; those were not drive-by
  fixes. isort was applied to that file because the run command
  string changed.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not
  measured. Account usage was not available, so no percentage is
  recorded. No subagents.

### Security and QA review on `b36f7da`

Follow-up commits on the same branch. Each one started with a
failing assertion, then the fix, and the commit itself passes the
same CI pytest command. No force-push. #60 was still open, so this
branch was not rebased.

- B1, `cef67b6`: `hide_input_in_errors=True`. A missing or rejected
  `SECRET_KEY` no longer prints `DATABASE_URL` or `OPENAI_API_KEY`
  in the `ValidationError` text. 920 passed, exact coverage 93.41%.
- N1, `f94088e`: placeholders are compared with `casefold()`, and
  `SECRET_KEY` must be at least 32 characters. `token_urlsafe(32)`
  is 43 characters, which is what `.env.example` and the README
  tell you to generate. Test keys were lengthened in the same
  commit so collection still works. 924 passed, exact 93.41%.
- N2, `7a923f4`: `ALLOWED_HOSTS` is a string plus a validator, like
  CORS. A comma list and a JSON list both work. `*`, an empty
  entry, and a host that includes a port are rejected. The default
  is still `localhost,127.0.0.1`. 931 passed, exact 92.53%.
- N3, `2c94486`: company-name success logs and the collector's
  `str(e)` logs use `%r`. A newline in the name or the exception
  text cannot start a second log line. 933 passed, exact 92.53%.
- N4, `9cc3e0e`: `isascii()` runs before `strip` and `upper`, so
  `aapl` plus a line separator, a no-break space plus `aapl`, and
  `ıbm` are HTTP 422. 936 passed, exact 92.56%.
- N5, `d5c5570`: 422 errors still include `input`, because
  `tests/test_validation_errors.py` checks short values such as
  `inf` and a nested structure. Strings longer than 100 characters
  are cut, so a 200k-character name does not come back in the
  body. `description` is capped at 5000 characters on create and
  update only. The column is `Text`. 5000 is about a page, enough
  for a provider summary, and a longer row already stored can
  still be read. 938 passed, exact 92.71%.
- N6, `531fb00`: a CORS origin must be `http` or `https` with a
  host and an optional port. A path other than `/`, userinfo, a
  query, a fragment, or `*` is rejected at startup. 946 passed,
  exact 92.46%.
- N7, `7c4f7c9`: `fetch_company_data` no longer calls `.upper()`
  again. The request model already did. 947 passed, exact 92.46%.
- QA, documented commands, `8afeafb`: the demo `DATABASE_URL`
  export used single quotes, so `$TMPDIR` never expanded. It is
  double-quoted. A test scans the guides for any other
  single-quoted `$TMPDIR` or `~/`. There were no others. 948
  passed, exact 92.46%.
- QA, currency, `7bb9ee0`: `GBp` is stored and read back unchanged.
  Currency is three letters, and the case is not rewritten.
  Yahoo's `GBp` means pence, and rewriting it to `GBP` would
  treat the amount as pounds. 949 passed, exact 92.49%.
- QA, read model, `88f3250`: ticker, length, and ASCII checks apply
  to create and update only. `GET /companies/` returns 200 when a
  row inserted past the model has a blank ticker. 950 passed,
  exact 92.57%.
- Security and QA approved at `f1072cc`. The pull request now
  says `Closes #50`. Follow-ups stay tracked separately. It still
  closes #45, #47, and #17. fetch-company truncates a provider
  description to the first 5000 characters, with no ellipsis, so
  a long Yahoo summary is stored instead of returning HTTP 502.
  User create and update still reject anything longer with HTTP
  422. 951 passed, exact 92.63%. #60 is a separate PostgreSQL
  harness on the same base. Whichever lands second has to point
  its test client at `http://127.0.0.1`, stop hard-coding the old
  database URL default, clear the personal paths the git-grep
  guard flags, and refresh the work-state line that says `#9 stays
  later`.
- The company read model keeps `website` as plain text. A stored
  value that is not a URL still returns HTTP 200 from
  `GET /companies/`. Create and update still require a URL. 952
  passed, exact 92.63%.
- A CORS origin that includes userinfo fails startup without
  repeating the username or password. 953 passed, exact 92.63%.
- IPv6 CORS origins are not supported for now.
  ``http://[::1]:3000`` is rejected with that reason. The old
  branch that tried to put the brackets back never ran, because
  ``AnyHttpUrl`` receives the host without them. 954 passed,
  exact 92.77%.

## 2026-10-08 - Module-level skips fail the PostgreSQL job (#9)

- Scope: QA approved `5aa1ccf` and sent it to Code Reviewer.
  One low follow-up: `pytest.skip(allow_module_level=True)` left
  the PostgreSQL job green (`5 passed, 1 skipped`, exit 0). That
  skip is a collection report. `pytest_runtest_logreport` never
  sees it.
- Decision: `pytest_collectreport` records the same skips as the
  per-test hook. Expected failures (`wasxfail`) stay ignored.
  The same node id is stored once. The failure banner names the
  first three node ids and, when there are more, how many remain.
  The default SQLite job still does not set `REQUIRE_POSTGRES`.
- Verification, from the repository root, no `.env`,
  `DATABASE_URL` unset, Python 3.12.3: the CI pytest command
  -> 846 passed, 119 deselected in 12.43s, exact 92.58%.
  `REQUIRE_POSTGRES=1` and the local test DSN with
  `-m integration` -> 117 passed, 2 xfailed, 846 deselected in
  4.15s, exit 0. `test_skip_guard.py -m integration` -> 8 passed
  in 1.07s, including a child process whose module-level skip
  exits 1 and names `test_mod.py`. `black`, `isort --check-only`,
  and `flake8` passed on the touched Python files. GitHub Actions
  for this commit follows the push.
- Work-state next action: unchanged. #45 and #47 together, with
  #50 if that fix stays small. Then #24, #19, #25, and #26 (with
  #16 and #17).
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not
  measured. Account usage was not available in this session; no
  percentage recorded.

## 2026-10-08 - Rebase onto #59 and three review nits (#9)

- Scope: rebase `cursor/postgres-integration-harness-fc54` onto
  `origin/master` `f66f26b` (issue #59, requirements v0.3). The
  journal keeps both histories, newest first. Code Reviewer
  approved `4960a42` with three nits. Two items stay for later:
  the private pytest frame walk in `env_isolation`, and `PGPORT`
  in the denylist identity.
- Decision, zero skips: `pytest_sessionfinish` in
  `tests/integration/conftest.py` fails the session when
  `REQUIRE_POSTGRES=1` and any test was skipped. Deselected tests
  are not skips. An expected failure is not a skip either: pytest
  reports it with ``outcome == "skipped"`` and sets ``wasxfail``.
  An already failing session keeps its status. The default SQLite
  job does not set `REQUIRE_POSTGRES`.
- Decision, case collision: the expected failure cites PRD open
  question 10 and I1 issue #26.
- Decision, setup: the two expected-failure tests create `DUP`
  in the test body and add the strict xfail marker only after
  that create returns 201. Pytest reports a fixture failure
  inside an already-marked xfail test as xfailed, so the marker
  is added late. A failed create is a normal failure. A pass
  after the marker is a strict XPASS.
- Work-state next action: unchanged. #45 and #47 together, with
  #50 if that fix stays small. Then #24, #19, #25, and #26 (with
  #16 and #17).
- Verification, from the repository root, no `.env`,
  `DATABASE_URL` unset, Python 3.12.3: the CI pytest command
  -> 846 passed, 116 deselected in 8.14s, exact 92.58%.
  `-m integration` with the local test DSN -> 114 passed, 2
  xfailed, 0 skipped in 3.06s. The two target tests with no DSN
  -> 2 skipped. The same tests with `REQUIRE_POSTGRES=1` and no
  DSN -> 1 error, exit 1. `black`, `isort --check-only`, and
  `flake8` passed on the touched Python files.
  GitHub Actions
  [run 37841595814](https://github.com/Waber/Investment-AI-Companion/actions/runs/37841595814)
  on `3ebd6b0` failed the PostgreSQL job: the guard counted the
  two expected failures as skips. The follow-up ignores
  ``wasxfail``.
  [run 37841966780](https://github.com/Waber/Investment-AI-Companion/actions/runs/37841966780)
  on `135bc59bcb851626683902c44121e6e29eb24ec0` is green. SQLite
  job 846 passed, 116 deselected in 16.90s. PostgreSQL job 114
  passed, 2 xfailed, 846 deselected in 4.88s. The summary has
  no skipped tests, and the job stayed green with
  `REQUIRE_POSTGRES=1`.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not
  measured. Account usage was not available in this session; no
  percentage recorded.

## 2026-10-08 - Review follow-up on requirements v0.3

- Scope: documentation only, one commit on top of `55cc070`. The
  disclaimer stays in both phases, including on post-demo signals.
  Only the no-buy/sell rule is demo-only. The hosting note is research
  input, not a decision. `docs/work-state.md` is unchanged.
- OVH: the heading "OVH VPS 2027 range" was left as written. OVHcloud's
  VPS page and the 2026 blog post "VPS 2027: OVHcloud's new server
  range" use that name. VPS-1 is the entry model in that range.
- AI model: Grok 4.7 (Cursor cloud agent). Account usage was not
  available in this session.

## 2026-10-08 - Product requirements v0.3 and hosting research

- Scope: documentation only, on a branch from `origin/master` `d568663`.
  `docs/product-requirements.md` is the Project Manager's v0.3 source,
  applied with the PM's v0.2-to-v0.3 diff on top of master.
  `docs/research/hosting-options.md` is the Researcher's hosting note,
  verbatim. No `.py` files, workflows, or config files were edited.
  `docs/work-state.md` is unchanged. The live next action stays #45
  and #47 together.
- Decision: "No authentication, no hosting" and "the score is never a
  buy/sell signal" apply to the demo phase only. Section 12 is the
  PM's post-demo direction (server for the owner, login, private
  holdings, scheduled scanner with signals and notifications).
  Refs #48, #56, #57 and #58. This does not close them.
- Merge with PR #51: two hunks did not apply on the #51 roadmap text.
  The P6 row and the dependency bullet that starts "On 2026-10-08 the
  Project Manager moved #11's security/deps part" stay exactly as on
  master, including the note that the `yfinance>=1.7` pin moved with
  that security/deps part. The P7 row, the issue map (#48, #54–#58),
  the P7 dependency line, and section 12 are the PM's wording.
- There is no `docs/research/README`. The hosting note has no relative
  links to rewrite.
- AI model: Grok 4.7 (Cursor cloud agent). Account usage was not
  available in this session.
- Verification: GitHub Actions Tests run 37833690203 succeeded on
  `786e1e0` (the content commit). Job `pytest (Python 3.12, SQLite)`
  completed with conclusion success.
  https://github.com/Waber/Investment-AI-Companion/actions/runs/37833690203

## 2026-10-08 - PGHOSTADDR applies even when the URL names a host (#9)

- Scope: QA re-check of `3f9de18` approved the four earlier
  findings. One remaining bypass: libpq dials `PGHOSTADDR` even
  when the URL already names a host. A localhost URL with
  `PGHOSTADDR=127.0.0.99` connected to `127.0.0.99`. `PGSERVICE`
  can load a service file that names another server. `PGHOST`
  does not override an explicit host.
- Decision: `decide_test_dsn` now checks `PGHOSTADDR` and
  `PGSERVICE` on every URL. `PGHOSTADDR` must be loopback
  (`localhost`, `127.0.0.1`, or `::1`). Any `PGSERVICE` value is
  refused. `PGHOST` is still checked only when the URL has no
  host. `TEST_POSTGRES_ALLOW_REMOTE=1` does not relax these
  checks. A remote `PGHOST` next to a localhost URL is still
  accepted, and a loopback `PGHOSTADDR` is still accepted.
- Verification, from the repository root, no `.env`,
  `DATABASE_URL` unset, Python 3.12.3, packages from
  `requirements-dev.lock`:
  the CI pytest command -> 846 passed, 111 deselected in 13.37s,
  exact 92.58%. `tests/integration/test_postgres_dsn.py -m integration`
  -> 83 passed in 0.11s. Collection of `-m integration` is 111
  tests (95 do not open PostgreSQL; 16 hit the database: 14
  pass and 2 xfail when a server is configured). `black
  --check`, `isort --check-only`, and `flake8` passed on
  `tests/integration/postgres_dsn.py` and
  `tests/integration/test_postgres_dsn.py`. The database tests
  were not re-run; this change does not open a connection.
  GitHub Actions for this commit follows the push. The previous
  code head `64acc52` is green in
  [run 37838815029](https://github.com/Waber/Investment-AI-Companion/actions/runs/37838815029):
  SQLite 846 passed, 108 deselected in 18.22s. PostgreSQL 106
  passed, 2 xfailed, 846 deselected in 2.96s.
- Work-state next action: unchanged. #45 and #47 together, with
  #50 if that fix stays small, until #61 lands.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not
  measured. Account usage was not available in this session; no
  percentage recorded.
## 2026-10-08 - DSN query guard and merge-safe integration import (#9)

- Scope: QA follow-up on `c9b7302`, applied on top of `1fc4edb`.
  libpq query parameters and environment variables could point the
  connection at a different database than the allowlist checked.
  Issue #16 does not include case-insensitive tickers. Pull
  request #61 requires `SECRET_KEY` before `Settings()` can be
  built.
- Decision, query and environment: `decide_test_dsn` refuses
  `dbname`, `database`, `hostaddr`, and `service` in the query
  string. A `host` query value is accepted only when every
  comma-separated piece is localhost, `127.0.0.1`, `::1`, or an
  absolute socket path (`?host=/socket/dir` still passes). When
  the URL has no host, `PGHOST` must be local, `PGHOSTADDR` must
  be loopback, and `PGSERVICE` is refused. `TEST_POSTGRES_ALLOW_REMOTE=1`
  does not relax those checks. Only the exact value `1` enables
  the remote-host override.
- Decision, `.env` denylist: `dotenv_values` reads `DATABASE_URL`
  from a `.env` file without applying it, and that URL is refused
  as an application database. The root conftest also treats
  `-qm integration`, an empty `-m` value, and `pytest.main` as
  selecting the marker, using the marker expression pytest has
  already parsed. If the marker is selected, a `.env` exists, and
  isolation did not run, configuration raises `UsageError`.
- Decision, secret: before the isolated import, the root conftest
  sets `SECRET_KEY` with `setdefault` to a 34-character throwaway
  that is not a known placeholder. A shell-exported secret is
  left in place. The default SQLite command does not take this
  path. `tests/conftest.py` was not modified.
- Decision, #16: the current test still expects 500 for an exact
  duplicate `DUP`, then a different ticker `OTHER` to show the
  session recovered. It no longer asserts that `dup` is stored.
  A strict xfail covers the #16 target (exact duplicate is 400 or
  409 and one row). A second strict xfail covers case collision
  and names ticker normalization, not #16. Both start from a
  fixture that creates `DUP`, so a failed create is an error
  rather than an expected failure.
- Verification, from the repository root, no `.env`,
  `DATABASE_URL` unset, Python 3.12.3, packages from
  `requirements-dev.lock`:
  the CI pytest command -> 846 passed, 108 deselected in 13.83s,
  exact 92.58%. Node id without the marker -> 1 deselected,
  exit 5. `-m integration` with the local test DSN -> 106 passed,
  2 xfailed, 846 deselected in 3.65s. Of those 108 integration
  tests, 92 do not open PostgreSQL and 16 hit the database (14
  passed, 2 xfailed). `black`, `isort --check-only`, and
  `flake8` passed on the touched Python files.
  GitHub Actions
  [run 37838815029](https://github.com/Waber/Investment-AI-Companion/actions/runs/37838815029)
  on `64acc52326c638f9ae8c6d645345fde8e751e509`: SQLite job
  846 passed, 108 deselected in 18.22s. PostgreSQL job
  106 passed, 2 xfailed, 846 deselected in 2.96s.
  The previous head `1fc4edb` is green in
  [run 37837340255](https://github.com/Waber/Investment-AI-Companion/actions/runs/37837340255):
  SQLite 846 passed, 68 deselected in 16.98s. PostgreSQL 67
  passed, 1 xfailed, 846 deselected in 2.86s.
- Work-state next action: unchanged. #45 and #47 together, with
  #50 if that fix stays small, until #61 lands. Then #24, #19,
  #25, and #26 (with #16 and #17). The sentence that the harness
  stays later is updated when this branch rebases onto #61.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not
  measured. Account usage was not available in this session; no
  percentage recorded.
## 2026-10-08 - Integration client host and neutral paths (#9)

- Scope: follow-up on `cursor/postgres-integration-harness-fc54`
  after
  [Actions run 37836507848](https://github.com/Waber/Investment-AI-Companion/actions/runs/37836507848)
  went green on `c9b7302`. Pull request #61 is still open, so
  this branch is not rebased onto it.
- Decision, client host: `postgres_client` uses
  `base_url="http://127.0.0.1"`. #61 adds `TrustedHostMiddleware`
  that allows `localhost` and `127.0.0.1`. The name `testserver`
  would be HTTP 400 and would fail the PostgreSQL API tests
  after that merge. `tests/conftest.py` is still untouched.
- Decision, paths: text added by this pull request no longer
  contains a personal account name or a machine-specific home or
  temporary directory. DSN tests read the application default from
  `Settings.model_fields` instead of copying a role name. Example
  URLs use the role `user`. The README names the refused database
  as `investment_ai` on localhost. Historical journal and
  work-state paths that were already on master are left for #61,
  which rewrites those same lines. Rewriting them here would
  conflict with that edit.
- Not in this commit: the work-state sentence "#9 stays later".
  #61 adds that sentence in its new top section. This branch
  updates it when it rebases onto #61.
- Verification, same environment as the allowlist entry:
  default suite 846 passed, 68 deselected, exact 92.58%.
  `-m integration` with the local test DSN: 67 passed, 1
  xfailed. `black`, `isort --check-only`, and `flake8` passed
  on the touched Python files.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not
  measured. Account usage was not available in this session; no
  percentage recorded.
## 2026-10-08 - PostgreSQL harness review follow-up (#9)

- Scope: QA and PM follow-up on the harness in
  `cursor/postgres-integration-harness-fc54`, still based on
  `origin/master` `d568663`. The PM accepted the GitHub Actions
  service container and is editing issue #9. Alembic
  upgrade/downgrade on PostgreSQL moves to #8 and is not in this
  change. The disposable `scripts/test_postgres.py` runner and its
  cleanup tests are dropped. `.env` isolation before the
  application import stays in #9 and is in this change.
- Decision, allowlist: refusing only the application URL was not
  enough. The harness drops and truncates tables, so any other
  name would have been destroyed. `decide_test_dsn` now refuses a
  database name unless it contains `test` as its own word
  (`investment_test` passes; `testing`, `testdb`, and
  `investment_ai` do not). The host must be localhost,
  `127.0.0.1`, `::1`, or a Unix socket, unless
  `TEST_POSTGRES_ALLOW_REMOTE=1`. That override does not relax
  the name rule or the application-database check. The CI URL
  `postgresql://postgres:postgres@127.0.0.1:5432/investment_test`
  already passes, so the database was not renamed and the job
  does not set the override.
- Decision, image pin: the PostgreSQL job uses
  `postgres:16.15@sha256:ca0bd484cb98bf4b24eb1010e73fb3fcbd6714d240fbc1a10eea5b7dbecb641d`.
  That digest is the `postgres:16` image the earlier CI run
  pulled. The README tells a local Docker run to use the same
  image and `TEST_POSTGRES_DSN`.
- Decision, `.env` isolation: `Settings` reads `env_file=".env"`
  from the process working directory. pytest loads the repository
  root `conftest.py` before `tests/conftest.py`, and
  `tests/conftest.py` imports the application at module level.
  When the command selects the `integration` marker (pytest's own
  `-m` grammar; the last `-m` wins over `PYTEST_ADDOPTS`; no `-m`
  means this repo's addopts, which deselects the marker), the
  root conftest imports `app.core.config`, `app.core.database`,
  and `main` from an empty temporary directory. The later import
  reuses that module, so a `.env` in the original directory is
  not applied. A `DATABASE_URL` exported in the shell is still
  read. The default SQLite command does not select the marker, so
  it does not take this path. `tests/conftest.py` was not
  modified.
- Decision, issue #16: the current-behaviour test stays (duplicate
  `DUP` is 500, and `dup` is stored). A second test expects 400
  or 409 and one row, with `strict` xfail. When the fix lands,
  that marker has to be removed or the suite fails. A fixture
  setup error is not an expected failure.
- Docstring only: `SET TIME ZONE` stays after COMMIT. Only
  ROLLBACK reverts it. The `begin` listener still sets
  `Europe/Warsaw` on every transaction. Behaviour is unchanged.
- Verification, from the repository root, no `.env`,
  `DATABASE_URL` unset, Python 3.12.3, packages from
  `requirements-dev.lock`:
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 846 passed, 68 deselected in 12.84s, no warnings summary,
  TOTAL 92% (exact 92.58%).
  Node id without the marker -> 1 deselected, exit 5.
  `-m integration` with `TEST_POSTGRES_DSN` unset -> 53 passed,
  15 skipped, exit 0. The 53 do not open PostgreSQL (45 DSN
  checks and 8 `.env` checks). The 15 database tests skip.
  The same command with
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`
  -> 67 passed, 1 xfailed, 846 deselected in 2.00s on the local
  PostgreSQL 16.15. The xfail is the #16 target test.
  `REQUIRE_POSTGRES=1` with the variable unset failed in fixture
  setup, exit 1.
  `black --check`, `isort --check-only`, and `flake8` passed on
  `conftest.py` and `tests/integration`.
  GitHub Actions
  [run 37836507848](https://github.com/Waber/Investment-AI-Companion/actions/runs/37836507848)
  on `c9b7302`: SQLite job 846 passed, 68 deselected in 17.49s,
  TOTAL 93%. PostgreSQL job 67 passed, 1 xfailed, 846 deselected
  in 2.68s on PostgreSQL 16.15 (Debian 16.15-1.pgdg13+2).
- Work-state next action: unchanged. #45 and #47 together, with
  #50 if that fix stays small. Then #24, #19, #25, and #26 (with
  #16 and #17). #8 and #16 stay open. #20 stays open until
  review accepts the PostgreSQL run.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not
  measured. Account usage was not available in this session; no
  percentage recorded.

## 2026-10-08 - PostgreSQL integration test harness (#9)

- Scope: issue #9, on a branch from `origin/master` `d568663`.
  Branch `cursor/postgres-integration-harness-fc54`.
  Implementation commit `e242341`. SQLite stays the default
  database. No new package. Alembic is unchanged.
- Decision, opt-in: tests under `tests/integration/` carry the
  existing `integration` marker. `addopts` still passes
  `-m "not integration"`. `python -m pytest` deselects them.
  `pytest -m integration` replaces that expression and runs them.
  A node id without `-m integration` stays deselected and exits 5.
- Decision, configuration: the database URL is
  `TEST_POSTGRES_DSN`. When it is unset, database fixtures skip
  with a message that names the variable and an example URL.
  `REQUIRE_POSTGRES=1` (the CI job) fails that case instead of
  skipping, so a missing CI variable cannot go green on skips.
  DSN comparison tests in `tests/integration/test_postgres_dsn.py`
  do not open a connection, so they still run when the variable
  is unset.
- Decision, refuse the application database: the harness compares
  the test URL with `settings.DATABASE_URL` and with the code
  default (database name `investment_ai` on localhost).
  The same host (localhost, 127.0.0.1, ::1, or a Unix socket),
  port, and database name match even when the role or the driver
  suffix differs. A match fails the run before any connection.
  The tests then drop and recreate only their own tables.
- Decision, schema: `Base.metadata.create_all` on the test
  engine. Issue #8 is still open. `alembic.ini` has
  `version_num_format = %04d`, which crashes Alembic commands
  (the value needs `%%04d`). There is no baseline revision. The
  integration test asserts `alembic_version` is absent and that
  `period_end` is `timestamp with time zone`.
- Decision, CI: a second job, `pytest (Python 3.12, PostgreSQL)`,
  uses a `postgres:16` service container and
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`.
  The SQLite job is unchanged: same checkout SHA,
  `persist-credentials: false`, hashed install from
  `requirements-dev.lock`, and the same pytest flags including
  `--cov-fail-under=80`. The PostgreSQL job does not pass
  coverage flags. No `pytest-postgresql` dependency.
- Decision, session zone: each transaction runs
  `SET TIME ZONE 'Europe/Warsaw'`. December is UTC+1 there, so a
  value shifted into the session zone does not read back as the
  UTC instant. The server default can stay UTC.
- Behaviour pinned on PostgreSQL: `+02:00`, `Z`, and naive
  `period_end` read back as the UTC instant through the API and
  the ORM, and as the UTC wall clock from
  `period_end AT TIME ZONE 'UTC'`. Five other spellings of
  `2025-12-31T00:00:00Z` return 400 with the uniqueness detail,
  and one row remains (issue #20). A direct ORM insert of that
  same instant raises `IntegrityError` on
  `uq_metrics_company_period`. A missing company is 400 from the
  API and `IntegrityError` from a direct insert. `DELETE FROM
  companies` is rejected by `financial_metrics_company_id_fkey`
  while metrics exist. Deleting the company through the ORM
  removes the metrics. After that constraint error, the same
  session can commit a new row.
- Issue #16 is recorded, not fixed. A second company with ticker
  `DUP` returns 500 and `{"detail":"Internal server error"}`.
  Ticker `dup` is stored as a second row.
- `tests/conftest.py` was not modified. The SQLite `client`
  fixture is untouched. PostgreSQL fixtures live in
  `tests/integration/conftest.py`: `postgres_engine` (session),
  `postgres_session_factory` (truncates `companies` and
  `financial_metrics` around each test), and `postgres_client`
  (async HTTP client, `init_database_on_startup=False`). The
  only edit under the existing tests tree is the docstring in
  `tests/test_known_defects.py`, which now points at the
  PostgreSQL duplicate-instant test.
- Out of this pull request: the disposable local cluster runner
  (`scripts/test_postgres.py`) and Alembic upgrade/downgrade.
  The runner would be a new script under `scripts/`, which is
  inside the coverage gate, and the task asked for the GitHub
  Actions service container instead of a Python-managed server.
  Migrations wait for #8.
- Verification, from the repository root, no `.env`,
  `DATABASE_URL` unset, Python 3.12.3, packages from
  `requirements-dev.lock`:
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 846 passed, 37 deselected in 13.55s, no warnings summary,
  TOTAL 92% (exact 92.58%). Same passed count as master
  `d568663`.
  Node id without the marker:
  `python -m pytest -q -p no:cacheprovider tests/integration/test_postgres.py::test_server_is_postgresql`
  -> 1 deselected, exit 5.
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`
  with `TEST_POSTGRES_DSN` unset -> 23 passed, 14 skipped,
  exit 0. The skip text is: PostgreSQL integration tests need
  `TEST_POSTGRES_DSN` set to a database that is not the
  application's `DATABASE_URL`.
  The same `-m integration` command with
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`
  -> 37 passed, 846 deselected in 1.06s.
  Server version from that run: `PostgreSQL 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1) on x86_64-pc-linux-gnu, compiled by gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0, 64-bit`.
  Pointing `TEST_POSTGRES_DSN` at the code default, and setting
  `REQUIRE_POSTGRES=1` with the variable unset, each failed in
  fixture setup before a connection, exit 1.
  `black`, `isort --check-only`, and `flake8` passed on
  `tests/integration` and `tests/test_known_defects.py`.
  The docs tree, measured before this commit: 846 passed,
  37 deselected in 13.00s, exact 92.58%.
  GitHub Actions on `8bfd7ba`
  ([run 37834076658](https://github.com/Waber/Investment-AI-Companion/actions/runs/37834076658)):
  SQLite job 846 passed, 37 deselected in 9.90s, TOTAL 93%.
  PostgreSQL job 37 passed, 846 deselected in 1.20s.
  Service version: `PostgreSQL 16.15 (Debian 16.15-1.pgdg13+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit`.
- Work-state next action: unchanged. #45 and #47 together, with
  #50 if that fix stays small. Then #24, #19, #25, and #26 (with
  #16 and #17). This harness is done. #8 and #16 stay open.
  #20's PostgreSQL check now has a test; the issue stays open
  until review accepts that run.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not
  measured. Account usage was not available in this session; no
  percentage recorded.

## 2026-10-08 - Security dependencies, hashed locks, and Actions SHAs (#11, #46)

- Scope: the security/deps part of #11, on a branch from
  `origin/master` `7120577`. Branch
  `cursor/security-deps-hashed-lock-79f1`.
  [PR #51](https://github.com/Waber/Investment-AI-Companion/pull/51).
  #46 is included because the workflow file changed. No Gemini
  adapter, no UI, and no yfinance cache or throttle adapter.
- Decision, one pull request: FastAPI 0.104.1 to 0.143.0 still uses
  Pydantic v2 (locked 2.13.5, floor `>=2.9.0,<3`). Starlette is
  locked at 1.7.0. The suite needed one test change. That is not a
  Pydantic major bump and not a broad behaviour rewrite, so black,
  pytest, yfinance, the removals, the split, and the lock stay in
  this pull request. A follow-up pull request was not opened.
- Decision, Starlette floor: the three named CVEs are fixed in
  0.36.2, 0.40.0, and 0.47.2. The direct pin is `starlette>=1.3.1`
  so resolution also clears the later Starlette advisories that
  pip-audit reports for the 0.x line, through CVE-2026-54283.
  FastAPI 0.135.2 is the first line whose own floors are
  `starlette>=0.46.0` and `pydantic>=2.9.0`. The lock selects
  FastAPI 0.143.0, which allows Starlette 1.7.0.
- Decision, pytest-asyncio: async tests and `tests/conftest.py`
  use `pytest_asyncio` fixtures, so the plugin stays. 0.21.1 does
  not run on pytest 8 or later. The dev file requires
  `pytest-asyncio>=1.0`. The lock installs 1.4.0, which accepts
  pytest 9. scikit-learn is removed. Nothing imports `sklearn`.
- Decision, jinja2 and python-multipart: not pinned. No module
  imports them, and there is no `/ui` template tree yet. D4 and D5
  add the pins when the UI needs them.
- Decision, google-genai: not pinned. It waits for the Gemini
  adapter. `pip install --dry-run google-genai` against the dev
  lock's environment would install `google-genai` 2.29.0. Installed
  FastAPI, Pydantic 2.13.5, httpx 0.28.1, and requests 2.34.2
  already satisfy it. The dry-run would downgrade `websockets`
  from 17.2 (pulled by yfinance 1.7) to 16.1.1, because
  google-genai 2.29.0 requires `websockets<17`. yfinance accepts
  `websockets>=13`, so 16.1.1 still fits. The adapter work should
  regenerate the lock with that constraint included.
- Decision, pandas and numpy: tests import pandas, so
  `requirements-dev.txt` pins `pandas>=1.3.0` (locked 3.0.6).
  numpy is only an `importorskip` in one test. The direct numpy
  pin is removed. yfinance pulls numpy 2.5.3, so that test runs.
  beautifulsoup4 is the same kind of transitive pin: removed as a
  direct requirement, present as 4.15.0 because yfinance needs it.
- Removed direct pins, after grep showed no import under `app/`,
  `main.py`, `scripts/`, or `tests/`: aiohttp, nltk, python-jose,
  passlib, bcrypt, openai, selenium, pandas-datareader, spacy,
  elasticsearch, redis, sphinx, sphinx-rtd-theme, scikit-learn.
  `REDIS_URL`, `ELASTICSEARCH_URL`, and `OPENAI_API_KEY` remain
  settings fields. They are strings, not client libraries.
- httpx stays, in the dev file. Tests use `httpx.AsyncClient` and
  `ASGITransport`. The application does not import httpx.
- Code change: `tests/test_validation_errors.py` calls
  `ValidationError.errors(include_url=False)`. FastAPI 0.143
  builds the request error that way, so the 422 body has no
  Pydantic documentation link. The custom handler still encodes
  the errors FastAPI passes in.
- Client-visible behaviour from FastAPI 0.143 and Starlette 1.7,
  checked against the installed app: when `BACKEND_CORS_ORIGINS`
  is set, every response includes `Vary: Origin`, including a
  request that sends no `Origin` header. An empty CORS list does
  not add that header. A CORS preflight's
  `Access-Control-Allow-Methods` includes `QUERY` (with DELETE,
  GET, HEAD, OPTIONS, PATCH, POST, and PUT). The OpenAPI
  `ValidationError` schema includes `input` and `ctx`. The
  `/api/v1/test-config` 200 schema sets `additionalProperties` to
  true. A 422 detail object has `type`, `loc`, `msg`, and `input`.
  It no longer includes `url`.
- Python 3.12 is the minimum. The locked numpy 2.5.3 declares
  `Requires-Python >=3.12`.
- `--strip-extras` on the runtime compile does not change pins or
  hashes, so `requirements.lock` was left as compiled without that
  flag. The same flag on the dev compile changes one line,
  `coverage[toml]==7.16.2` to `coverage==7.16.2`, and the hashes
  stay the same. `requirements-dev.lock` was regenerated with the
  flag. The documented commands pass `--strip-extras`.
- History: four commits, and each one passes the CI pytest
  command. The dependency commit carries the requirements split,
  both hashed locks, the workflow change to
  `pip install --require-hashes -r requirements-dev.lock`, and the
  `include_url=False` test fix. Action tags stay on that commit.
  The CI commit pins `actions/checkout` and `actions/setup-python`
  to commit SHAs. The style commit is the Black 26 reformat only.
  Docs are last. Per-commit results are in the verification
  section below.
- Black 26.10.0 reformatted 14 legacy files in its own commit.
  `black --check` then passes on `app`, `main.py`,
  `setup_database.py`, and `tests`. isort and flake8 still report
  the previous import-order, unused-import, and long-line findings
  on those paths. CI runs pytest and does not run the linters.
- Gaps between the floor in the text files and the locked install:
  FastAPI 0.143.0 (floor 0.135.2), Starlette 1.7.0 (floor 1.3.1),
  Pydantic 2.13.5 (was 2.6.1, floor `>=2.9.0,<3`), python-dotenv
  1.2.4 (floor 1.2.2), requests 2.34.2 (floor 2.33.0), pytest
  9.1.1 (floor 9.0.3), pytest-asyncio 1.4.0 (floor 1.0), pytest-cov
  7.1.0 (floor 4.1.0), black 26.10.0 (floor 26.3.1), httpx 0.28.1
  (floor 0.25.2), pandas 3.0.6 (floor 1.3.0), yfinance 1.7.0
  (floor 1.7), pip-tools 7.6.2 (floor 7.0). Exact pins that match
  the lock: uvicorn 0.24.0, pydantic-settings 2.1.0, SQLAlchemy
  2.0.23, psycopg2-binary 2.9.9, alembic 1.12.1, isort 5.12.0,
  flake8 6.1.0, mypy 1.7.1.
- The previous flat `requirements.txt` installs on Python 3.12.
  GitHub Actions run
  [37780801408](https://github.com/Waber/Investment-AI-Companion/actions/runs/37780801408)
  on master `7120577` installed that file on Python 3.12 and the
  Tests job succeeded. The new dev lock also installs on Python
  3.12. A clean venv whose pip was 24.0 accepted
  `pip install --require-hashes -r requirements-dev.lock` and the
  same command for `requirements.lock`.
- Verification, from the repository root, no `.env`,
  `DATABASE_URL` unset, Python 3.12.3, packages from the dev lock:
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 846 passed in 12.42s, no warnings summary, TOTAL 92% (exact
  92.58%). The 80% gate passed. `coverage report --precision=2`
  reports the same total. Collector tests are in that run and stay
  offline. `pip-audit -r requirements.lock` and
  `pip-audit -r requirements-dev.lock` both reported no known
  vulnerabilities. CI runs pytest only, so these checkouts were
  not asked to pass black, isort, or flake8. Each commit was
  checked out and the command above was run in a Python 3.12.3
  virtualenv installed with
  `pip install --require-hashes -r requirements-dev.lock` from
  that commit. The lock blob is the same on every commit
  (`9b70931`). No warnings summary on any run. Exact coverage
  is 92.58% on every run (`coverage report --precision=2`).
  `a585a01` (deps): 846 passed in 12.75s.
  `912c12b` (Actions SHAs): 846 passed in 12.57s.
  `3bbea71` (Black): 846 passed in 12.79s.
  The docs tree, measured before this commit: 846 passed in
  12.92s.
- Work-state next action: #45 and #47 together, with #50 if that
  fix stays small. Then #24, #19, #25, and #26 (with #16 and #17).
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not
  measured. Account usage was not available in this session; no
  percentage recorded.

## 2026-10-08 - Fetch-company 500 detail and debt_to_assets (#18, #21)

- Scope: bugs #18 and #21, on a branch from `origin/master` `a03ca24`.
  Branch `cursor/fetch-company-500-debt-to-assets-9f95`.
  [PR #49](https://github.com/Waber/Investment-AI-Companion/pull/49).
  No global exception middleware. No Yahoo change besides the
  `debt_to_assets` mapping. `fetch-financial-metrics` stays a
  placeholder.
- Decision for #18: the 500 detail is the fixed string
  `Error fetching company data`. The handler uses `logger.exception`,
  so the traceback stays in the server log, and the log message
  includes the ticker. The ticker is read before the `try`, so the
  log can name it. 404 (empty provider payload) and 400 (`ValueError`,
  including "Company name or ticker already exists") are the same
  handlers as before.
- Decision for #21: `debt_to_assets` is `totalDebt / totalAssets` when
  both values are already on the `info` dict that `fetch_key_metrics`
  just loaded. `totalDebtPerShare` is a currency amount per share, so
  the mapping never reads it. There is no second provider call. If
  either total is missing, is not an int or float (booleans count as
  not numbers, because `bool` is a subclass of `int`), or total assets
  is zero, the ratio is `None`. With yfinance 1.7, `info` has no
  `totalAssets` for equities. QA checked AAPL and PKN.WA, so
  `debt_to_assets` will be `None` for equities. For ETFs such as SPY,
  `totalAssets` is assets under management, not a balance-sheet
  figure. A real ratio needs `balance_sheet` ('Total Debt' /
  'Total Assets'), which is planned for #24.
- Reviewer nits on the ratio: NaN and infinity are None, and so are
  negative debt and a non-positive asset total. `OverflowError` from
  a huge int is caught, so the other metrics stay. `numbers.Real`
  accepts NumPy numbers and still rejects bool. Local suite after
  that: 846 passed in 15.09s, TOTAL 92% (exact 92.75%).
- Test-first commits, then the fix. On `6a7f533`, QA's two strict
  xfails were `2 xfailed`. With `--runxfail` both failed as
  `AssertionError`: the 500 body contained `hunter2`, and
  `debt_to_assets` was `7.5`. On `a06ca28` the further tests were
  `8 failed`, `2 passed`, `2 xfailed`. The failures were assertion
  failures: the error log did not contain the ticker `FAIL`, and
  `debt_to_assets` was still `7.5` instead of `0.25`, `0.0`, or
  `None`. `test_fetch_company_404_and_400_stay_unchanged` already
  passed. The fix commit removes both xfail markers.
- `app/api/data_collection.py` and
  `app/data_collectors/yahoo_finance.py` were reformatted in their own
  commit (`4bb8f1f`) because Black, isort, and flake8 have to pass on
  every file the fix touches, and both files already failed that
  check. Unused imports were removed in that same commit. The 500
  detail and the per-share mapping were still the old code there.
- Verification, from the repository root, no `.env`, `DATABASE_URL`
  unset:
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 838 passed in 15.33s, no warnings summary, TOTAL 92% (exact
  92.70%). The 80% gate passed. `coverage report --precision=2`
  reports the same total. Black, isort, and flake8 (line length 79)
  pass on the files this change touches. CI on `526990d`:
  [run 37778103776](https://github.com/Waber/Investment-AI-Companion/actions/runs/37778103776),
  838 passed in 23.14s, TOTAL 92% (exact 92.70%).
- Work-state next action, after the security review: #11, the
  security/deps part (FastAPI and Starlette CVE upgrade, `requests`,
  `python-dotenv`, `black`, `pytest`, removing unused pins,
  `yfinance>=1.7`, and a lock file with hashes). After it come #45
  and #47 together (secure config defaults and neutral defaults, one
  pull request), then #24, #19, #25 and #26 (with #16 and #17). #46
  (pin Actions to SHAs) goes into any pull request that touches CI.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not
  measured. Account usage was not available in this session; no
  percentage recorded.

## 2026-10-08 - SQLite UTC timestamps and foreign keys (D1, #23 and #20)

- Scope: demo slice D1 from `docs/product-requirements.md` section 5
  ("Other model points") and section 11 phase P1, together with bug #20.
  Rebased onto `origin/master` `f8266ea`.
  [PR #22](https://github.com/Waber/Investment-AI-Companion/pull/22)
  is merged as `778735e`.
  [PR #41](https://github.com/Waber/Investment-AI-Companion/pull/41)
  is merged as `07c30f6`.
  [PR #43](https://github.com/Waber/Investment-AI-Companion/pull/43)
  is merged as `f8266ea`. Branch
  `cursor/sqlite-utc-timestamps-foreign-keys-feb1`.
- `app/core/utc_datetime.py` adds `UTCDateTime`. On write it converts
  the value to UTC. On SQLite it then drops `tzinfo` and stores that
  UTC wall clock, because SQLite keeps the clock and throws away the
  offset. On read it attaches UTC. On PostgreSQL the bound value stays
  timezone-aware, so `timestamptz` is unchanged. `as_utc` is the shared
  helper: a naive datetime is treated as UTC, an aware one is converted
  with `astimezone` so the instant stays the same.
- Decision for naive `period_end`: treat it as UTC. The API already
  accepts offset-less strings such as
  `2024-12-31T00:00:00` (see `tests/test_metric_creation_conflicts.py`).
  Rejecting them would break that contract. The same instant sent as
  `Z` or as `+02:00` is a duplicate (400). On PostgreSQL, naive
  `period_end` input used to be interpreted in the session time zone
  and is now UTC. Responses now always use the `Z` suffix.
- The metrics repository calls `as_utc` before the uniqueness pre-check
  and before the insert or update. `FinancialMetricsUpdate` accepts an
  optional `period_end` so an update can move the period and still hit
  that check. A row is not a duplicate of itself (`exclude_id`).
  An explicit JSON null is rejected because the update field is a
  `datetime` with default `None` (HTTP 422). Omitting it leaves the
  field unset, so the column stays unchanged. OpenAPI drops that null
  default and shows `period_end` as a non-nullable date-time. On
  master, `PUT` with null `period_end` returned 200 and the value was
  ignored. At `c3c8911` null reached the database and came back as 400
  `constraint violation`. `PUT` can move `period_end`. Moving onto an
  existing company, period, and type is 400.
- `create_db_engine` in `app/core/database.py` runs
  `PRAGMA foreign_keys=ON` on each SQLite connection. The test client
  uses that function, so the pragma is not copied into `tests/conftest.py`.
  The foreign-key test builds its own engine and does not use the
  `client` fixture.
- `scripts/seed_demo.py` still requires an offset on fixture rows.
  Rows read back from the API may be naive; those are matched as UTC,
  so `python scripts/seed_demo.py --apply` (with the required
  `--base-url` and the repo on `PYTHONPATH`) can run twice against a
  fresh SQLite file. The second run creates nothing.
- Test-first commits, then the fix: the strict xfail for #20
  (`1 xfailed` on the parent of the fix), then eight failing #23/#20
  tests (`8 failed`), then this change removes the xfail marker.
  QA verified #20 on PostgreSQL 16 (session timezone Europe/Warsaw)
  at the application level: the same instant with `+02:00`, `Z`, or
  naive returns 400, and readback has no double shift. The formal
  harness is still #9. Out of scope: Alembic (#8), that harness, the
  instrument model (#26), and bugs #18, #19, and #21.
- `app/models/database_models.py`, `app/models/financial_metrics.py`,
  and `app/repositories/financial_metrics_repository.py` were
  reformatted because Black, isort, and flake8 have to pass on every
  file this change touches, and those three already failed that check.
  Untouched files with the same old debt were left alone.
- QA's carried-over nit: #43 added the README sentence "CI does not
  run these lint checks yet".
- Verification, from the repository root, no `.env`:
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 822 passed in 14.80s, no warnings summary, TOTAL 92% (exact
  92.36%) on the rebased head `c3c8911`. The 80% gate passed.
  After the null `period_end` follow-up, the same command is
  823 passed in 15.55s, no warnings summary, TOTAL 92% (exact 92.41%).
  Reviewer follow-up on this branch: 825 passed in 15.31s, no warnings
  summary, TOTAL 92% (exact 92.35%). `database.py` is fully covered,
  including the non-SQLite branch of `create_db_engine`.
- Work-state next action: bugs #18 and #21, then #24. Bug #19 can be
  slotted in.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not
  measured. Account usage was not available in this session; no
  percentage recorded.

## 2026-10-08 - Reviewer nits on the merged coverage gate

- Scope: [PR #43](https://github.com/Waber/Investment-AI-Companion/pull/43)
  on `cursor/reviewer-nits-minimal-c3a6`, rebased onto `origin/master`
  `07c30f6`. [PR #22](https://github.com/Waber/Investment-AI-Companion/pull/22)
  is merged as `778735e`. [PR #41](https://github.com/Waber/Investment-AI-Companion/pull/41)
  is merged as `07c30f6`. Master's journal and work-state sections from
  those pull requests are kept. No production `.py` edits.
- `actions/checkout` sets `persist-credentials: false`. The Tests job
  never pushes, so the checkout token is not stored in `.git/config`.
- isort `known_first_party` is `app`, `main`, and `scripts`.
- The README lint section no longer names a file that fails isort. It
  says older files still have formatting debt.
- Work-state no longer says Code Reviewer approved `63822cd` and is
  waiting on Raul. That line now says PR #22 is merged as `778735e`.
  The live next action is the product-requirements section at the top
  of `docs/work-state.md`.
- Verification: no `.env`, Python 3.12.3, pytest 7.4.3. Command:
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  Result on this head: `813 passed in 11.32s`, TOTAL exact `91.77%`.
  `--cov-fail-under=80` passed.
- Lint comparison, same interpreter, from the repository root.
  `python -m isort --check-only --diff .` still fails 12 files, and the
  diff is identical with or without `known_first_party`.
  `python -m black --check .` would reformat 15 files, and
  `python -m flake8 .` reports 388 findings. Those two counts do not
  change when the isort setting is removed. The setting matters when
  isort runs outside the repo root, for example an IDE or pre-commit
  whose settings file is not this repository. Without
  `known_first_party`, isort treats `app` as third-party and regroups
  `app/api/companies.py`, placing the `app` imports in the same group
  as FastAPI and SQLAlchemy. With the setting, those imports stay in
  the first-party group.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not measured.
  Account usage was not available in this session; no percentage recorded.

## 2026-10-08 - Product requirements and research docs

- Scope: documentation only. Add Raul's product requirements (draft v0.2,
  2026-10-08) and the two research notes from the same day. Paths match
  the Demo v1 issues (#23–#40, label `demo`):
  `docs/product-requirements.md`,
  `docs/research/market-data-sources.md`, and
  `docs/research/llm-comparison.md`. No `.py` files, workflows, or config
  files were edited.
- Decision: `docs/product-requirements.md` matches the PM's updated copy
  (2026-10-08), which fixes the research paths and makes N1 optional for
  A1. There were no `/workspace` paths.
- Work-state next action is Demo v1 issue #23 together with bug #20
  first, then bugs #18 and #21, then #24, then #25, then #26. Issues
  #8, #9, and #10 come after the demo.
- Verification: from the repository root, no `.env`,
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider`
  -> 758 passed in 6.48s, no warnings summary. This machine provides
  `python3` (3.12.3); `python` on `PATH` was that interpreter. Dependencies
  came from `requirements.txt` and were not changed.
- GitHub Actions Tests on `8ba25ee` succeeded:
  https://github.com/Waber/Investment-AI-Companion/actions/runs/37756800118
  Job `pytest (Python 3.12, SQLite)` completed with conclusion success.
  That run is from before this rebase. The final run on `973330b`
  succeeded:
  https://github.com/Waber/Investment-AI-Companion/actions/runs/37758000432
  The same job completed with conclusion success. Rebase-merge recorded
  that commit on master as `07c30f6`.
- After the rebase onto `778735e`, from the repository root, no `.env`:
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 813 passed in 11.50s, no warnings summary, TOTAL 92% (exact 91.77%).
  The 80% gate passed.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not measured.
  Account usage was not available in this session; no percentage recorded.
- Rebased onto `origin/master` `778735e`. PR #13 is merged as `a10e196`.
  PR #15 is merged as `b2541d7`. PR #22 is merged as `778735e`.
  PR #41 is merged as `07c30f6`.

## 2026-10-08 - Review notes on the coverage tests

- Scope: one commit on `cursor/coverage-threshold-80-c3a6` on top of
  `63822cd`. QA's two commits are unchanged. No production `.py` edits.
  The 80% gate is unchanged. Code Reviewer approved the earlier head.
  PR #22 is merged as `778735e`.
- `test_test_config_marks_missing_settings` only blanked four settings.
  `Settings` fills any name it was not given from the process environment,
  so `NEWS_API_KEY=x` made that optional mark present and the test failed.
  The test now calls `monkeypatch.delenv` for every name the endpoint
  reports and passes each of those fields (`None` or `""`). With
  `NEWS_API_KEY=x` exported, the test passes.
- `test_financial_statements_return_all_six_frames` now checks
  `set(STATEMENT_ATTRIBUTES) <= set(statements)`. A new statement key
  does not fail it. The entry below said an added key would fail; that
  was true before this commit.
- `debt_to_assets` is still not asserted. The comment now names GitHub
  issue #21.
- Each company-shaped pin listed in the entry below has the comment
  `# company-shaped pin, see #26`. Issue #26 is the instrument model.
- `datetime` imports in `tests/test_repository_edge_paths.py` are at the
  top of the module. The stray parentheses around `200` are gone.
- README: the copied command includes `--cov-fail-under=80`, so a subset
  run with that flag fails the gate. The README shows the same command
  without the flag.
- Raul explicitly chose the 80% coverage threshold on 2026-10-08 at
  10:48 Warsaw time, overriding the earlier 70% recommendation. The
  Project Manager relayed the decision. The gate stays
  `--cov-fail-under=80`. JUnit XML and the `MIN_TESTS` gate are still
  not enabled.
- The live next action is the product-requirements entry at the top of
  this journal: Demo v1 issue #23 together with bug #20 first, then bugs
  #18 and #21, then #24, then #25, then #26. Issues #8, #9, and #10 come
  after the demo.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not measured.
  Account usage was not available in this session; no percentage recorded.

## 2026-10-08 - Coverage gate at 80%

- Scope: QA's two commits, applied with `git am` on
  `cursor/coverage-threshold-80-c3a6` from `origin/master` `b2541d7`.
  Authorship stays `QA prototype <qa@local>`. No production `.py` edits.
  No test was rewritten after review. JUnit XML and the `MIN_TESTS` gate
  stay off.
- What the new tests cover: Yahoo Finance collector (a stand-in for
  `yfinance.Ticker`, so nothing is downloaded), `init_db` and
  `seed_sample_data` on a private in-memory SQLite engine, `get_db`
  closing its session, company and metrics delete/404/500 responses,
  repository paths the HTTP API does not hit by itself, CORS origin
  parsing, `/api/v1/test-config`, and the placeholder
  `fetch-financial-metrics` route. 55 new tests. The previous suite was
  758.
- Decision, 80% gate: `.github/workflows/tests.yml` and the README test
  command add `--cov-fail-under=80`. pytest-cov fails the process when
  the TOTAL for `app`, `main`, and `scripts` is below 80. `--cov-branch`
  counts branches as well as statements. The table rounds TOTAL to a
  whole percent; the sentence under the table is the exact figure the
  gate uses.
- Decision, tests left as QA wrote them. The `get_db` tests use a small
  stand-in session so they can see that the real generator yields that
  object and calls `close()`, including when the caller raises. The
  repository tests inject `IntegrityError` because SQLite's message does
  not contain the constraint name `uq_company_name_ticker`; they assert
  the `ValueError` (or the re-raised `IntegrityError`) and that
  `rollback` ran. The 500 tests inject a repository failure and assert
  the HTTP body, including that a password in the exception text is not
  returned. Those doubles drive a real branch. They are not assertions
  that a mock was configured.
- Company-shaped pins, left in place for the later instrument model
  (GPW/US/EU stocks plus ETFs/ETCs). Each one matches today's code.
  - `test_yahoo_finance_collector.py::test_company_info_maps_provider_fields`
    pins the mapped company keys and the fixture name `Apple Inc.`.
    Needed today. Extra keys would still pass.
  - `test_company_info_falls_back_to_short_name_and_usd` pins the
    `shortName` fallback and default currency `USD`. Needed today.
  - `test_financial_statements_return_all_six_frames` pins the exact set
    of six statement keys. Needed today. A new key would fail it.
  - `test_key_metrics_map_ratios_from_provider_info` pins the ratio keys
    the collector copies. It does not assert `debt_to_assets` (open
    issue #21). Needed today for the keys it lists.
  - `test_init_db.py::test_init_db_creates_tables_on_configured_engine`
    requires tables `companies` and `financial_metrics` to exist. It is
    a subset check. Needed today.
  - `test_seed_sample_data_inserts_companies_and_apple_metrics` requires
    the exact ticker list `AAPL`, `MSFT`, `TSLA` and two annual Apple
    metrics for 2022 and 2023. Needed today; this is the seed catalog.
  - `test_seed_sample_data_runs_once` requires 3 companies and 2 metrics.
    Needed today.
  - `test_delete_and_not_found_api.py` 404 tests require the detail
    `Company not found`. Needed today.
  - `test_delete_company_keeps_other_companies` requires the remaining
    ticker list `[KEEP]`. Needed today for that one-row case.
  - `test_create_company_business_error_returns_400` requires the detail
    `Company name or ticker already exists`, which the test raises
    itself. Needed today as a pass-through. It does not cover a real
    duplicate insert (open issue #16).
  - `test_data_collection_wiring.py::test_fetch_financial_metrics_is_a_documented_placeholder`
    requires the placeholder body and ticker `AAPL`, which is the
    request it sends. Needed today.
  - `test_repository_edge_paths.py::test_company_create_maps_named_constraint_to_value_error`
    requires `uq_company_name_ticker` in the error text. Needed today.
  - `test_company_is_unique_checks_name_or_ticker` requires uniqueness on
    name or ticker. Needed today.
- PR #13 is merged as `a10e196`. PR #15 is merged as `b2541d7`.
  PR #14 is merged as `db0cc12`. PR #22 is merged as `778735e`.
- Reviewer nits from PRs #14 and #15 (`persist-credentials: false`,
  isort `known_first_party`, README lint wording) are not in this
  change. They are a separate branch off master.
- Verification, from the repository root, no `.env` file, in a network
  namespace whose connect to `1.1.1.1:443` failed. Python 3.12.3,
  pytest 7.4.3, packages from `requirements.txt`. Command:
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  - This branch: `813 passed in 11.89s`, no warnings summary, TOTAL
    `92%`, exact total `91.77%`.
  - Same command on `b2541d7` (master, without these tests): `758 passed
    in 10.73s`, TOTAL `76%`, exact total `76.08%`, gate failed. That is
    the point of the threshold.
  - Random order seeds 7, 21, and 42, same flags: `813 passed` each,
    exact total `91.77%`, no warnings summary.
  - Each new test file collected and passed in its own process.
  - An open audit saw no read or write of a `.env` inside the
    repository. One existing test writes a `.env` under
    `/tmp/pytest-of-ubuntu/...` and reads that temporary file. pytest-cov
    writes a gitignored `.coverage` data file in the repo root; it was
    deleted and is not part of the commit. No `__pycache__` was written
    while `PYTHONDONTWRITEBYTECODE=1`.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not measured.
  Account usage was not available in this session; no percentage recorded.
- The next-action line that named Alembic and PostgreSQL (#8, #9, #10)
  as the next work was the order when this entry was written. The live
  next action is the product-requirements entry at the top of this
  journal.
- Published as [PR #22](https://github.com/Waber/Investment-AI-Companion/pull/22),
  merged as `778735e`.

## 2026-10-07 - Tooling configuration

- Scope: configuration and docs only. Black line length 79 with target
  Python 3.12, isort profile `black` at line length 79, flake8 max line
  length 79, and pytest `testpaths` plus a registered `integration` marker.
  No `.py` files edited. No new tools, dependency changes, or CI.
  Rebased onto `origin/master` `db0cc12` after PR #14 (minimal CI) was
  rebase-merged. The CI entry is next, then the deprecation entries.
  Both are kept. CI's `-W error::DeprecationWarning` and
  `-p no:cacheprovider` still apply: this config sets neither
  `filterwarnings` nor a cache plugin. With those flags and the coverage
  report, local `pytest -q` is 758 passed, no warnings summary, coverage
  total 76%. `addopts` `-m "not integration"` does not drop any current test.
- Why a separate `.flake8`: Black, isort, and pytest read `pyproject.toml`.
  flake8 does not. It only looks at `setup.cfg`, `tox.ini`, and `.flake8`.
  flake8 6 already defaults to 79 columns, so a no-flag `flake8` run is 79
  even without this file. `.flake8` records that 79 in a file flake8 reads.
  Black is the tool whose default (88) changes results unless
  `line-length = 79` is set.
- Decision, `--strict-markers`: adopted, in pytest `addopts`. An unregistered
  marker is a collection error instead of a warning the run can still pass.
  Checked with a throwaway test using `not_a_registered_marker`: collection
  stopped with that name not found in `markers`. The suite uses
  pytest-asyncio's registered `asyncio` marker and built-in `parametrize`
  only, including `tests/test_model_config_compatibility.py`. A misspelled
  `integration` marker cannot silently join the SQLite suite.
- Decision, default selection: `addopts` also passes `-m "not integration"`.
  A test marked `integration` is deselected unless the command line passes
  `-m integration` (that later `-m` replaces the addopts expression). A
  throwaway marked test was deselected by `pytest -q` and ran only with
  `-m integration`. There are no integration tests in the tree yet.
- Decision, flake8 `extend-ignore`: not set. flake8 6 already ignores W503
  and W504. E203 does not occur on the files that pass Black at 79 columns.
  No per-file ignores.
- Decision, pytest config boundary: `pyproject.toml` does not declare a
  pytest version, dependencies, or `filterwarnings`. pytest-asyncio 0.21.1
  breaks on pytest 8 or later, so versions stay in `requirements.txt`.
  `filterwarnings = error` is a pending decision and is not set here.
- Files checked with `black --check`, `isort --check-only`, and `flake8`
  and no extra flags. Results match `black --check --line-length 79`,
  default isort, and default flake8 on the same files, including isort
  `--profile black --line-length 79`. Pass means exit 0. Not reformatted.
  - Pass all three: `main.py`, `app/core/validation.py`,
    `tests/test_lifespan_cors.py`, `tests/test_validation_errors.py`,
    `tests/test_collection_updates.py`,
    `tests/test_metric_creation_conflicts.py`,
    `tests/test_financial_metric_updates.py`,
    `tests/test_model_config_compatibility.py`.
  - `tests/test_company_update_conflicts.py`: Black and flake8 pass. isort
    fails because `sqlalchemy.exc` is imported after the application
    imports. The black profile asks for the same move as default isort.
  - Production files from the deprecation cleanup, same before and after
    this config: isort passes `app/core/database.py`, `app/models/company.py`,
    `app/models/financial_metrics.py`, and `app/models/historical_data.py`.
    isort fails `app/api/data_collection.py`. Black 79 and flake8 still fail
    all five for pre-existing debt.
- `python3 -m isort --check-only .` with this profile fails 12 files, not
  only the cleanup files. None were reformatted. The list is
  `alembic/env.py`, `setup_database.py`, `app/api/companies.py`,
  `app/api/data_collection.py`, `app/api/financial_metrics.py`,
  `app/core/config.py`, `app/core/init_db.py`,
  `app/data_collectors/yahoo_finance.py`, `app/models/database_models.py`,
  `app/repositories/company_repository.py`,
  `app/repositories/financial_metrics_repository.py`, and
  `tests/test_company_update_conflicts.py`.
  `black --check tests` leaves 19 files unchanged and `flake8 tests`
  passes. `isort --check-only tests` fails only
  `tests/test_company_update_conflicts.py`. README lint commands now
  include `tests`.
- Default Black (88 columns) would reformat `main.py` and
  `tests/test_lifespan_cors.py`. Configured 79 leaves both unchanged.
- Verification, from the repository root, no `.env` (only `.env.example`):
  - Before this config, on `origin/master` `a10e196`:
    `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q` -> 758 passed, no
    warnings summary. `python3 -m pytest --collect-only -q` -> 758 collected.
  - After this config: the same command -> 758 passed in 9.34s, no warnings
    summary. `python3 -m pytest --collect-only -q` -> 758 collected.
    `python3 -m pytest --markers` lists `integration`.
  - This environment has no project `.venv`. The interpreter was Python 3.12
    with the pinned Black 23.11.0, isort 5.12.0, flake8 6.1.0, and
    pytest 7.4.3 from `requirements.txt`. README lint commands were run the
    same way via `python3 -m` and read the new config. `app/` and
    `setup_database.py` still fail those checks because of older debt.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not measured.
  Account usage was not available in this session; no percentage recorded.
- Published as [PR #15](https://github.com/Waber/Investment-AI-Companion/pull/15),
  merged as `b2541d7`.

## 2026-10-07 - Minimal pytest CI

- Scope: one GitHub Actions workflow for the existing SQLite pytest suite
  (issue #5). No lint gate, Postgres, Docker, dependency changes,
  or `pyproject.toml`. Coverage is reported and does not fail the job.
- Decision: `.github/workflows/tests.yml` on `pull_request` and `push` to
  `master`. Python 3.12, `python -m pip install -r requirements.txt` with
  the setup-python pip cache, `PYTHONDONTWRITEBYTECODE=1`, the job fails if
  `.env` exists, and the workflow does not read GitHub Actions secrets.
  Command adds a coverage report and does not write JUnit XML.
  PR #13 is rebase-merged, so the command now includes
  `-W error::DeprecationWarning`.
- The draft QA spec is applied. Pending Raul: the coverage threshold
  (`--cov-fail-under=70`), JUnit XML, and the `MIN_TESTS` gate.
- PR #14 is merged into master as `db0cc12`. Local Python 3.12.3 with
  no `.env`: `758 passed in 13.56s`, no warnings summary, coverage total
  `76%`.
  Negative check: commit `806faef` failed on purpose
  (https://github.com/Waber/Investment-AI-Companion/actions/runs/37681557386,
  `1 failed, 742 passed, 4 warnings`) and was dropped before merge.
- Verification: with `-W error::DeprecationWarning` and the coverage report,
  the suite is `758 passed`, 0 warnings, and `76%` coverage. GitHub Actions
  run 37682560920 is green:
  https://github.com/Waber/Investment-AI-Companion/actions/runs/37682560920
  Job log: `758 passed in 13.67s` and `TOTAL ... 76%`.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not measured.
- Delivery: [PR #14](https://github.com/Waber/Investment-AI-Companion/pull/14)
  on `cursor/minimal-pytest-ci-ed2f`. PR #14 is merged into master as
  `db0cc12`.

## 2026-10-07 - QA nits on the deprecation cleanup

- QA approved [PR #13](https://github.com/Waber/Investment-AI-Companion/pull/13)
  at `b05c79a` with three non-blocking notes. Fixed on
  `cursor/deprecation-cleanup-7154`. PR #13 is merged as `a10e196`.
- `docs/work-state.md` now says issue #5 and issue #6. Those numbers are
  GitHub issues, not pull requests. The pull request body matches.
- The suite command in the cleanup entry below is the portable form, run
  from the repository root: `.venv/bin/python -m pytest -q -p no:cacheprovider`.
- Code review of `330c1bd` asked to stop writing `.env` into the repo.
  The warning check still starts in a temporary directory with a minimal
  environment. The child asserts that its working directory is not the
  project root. `Settings` reads `.env` from that directory, so a repo-root
  `.env` is not loaded. The test does not write any file into the repo.
  `PYTHONPATH` still points at the repo.
- RED, with the pre-cleanup sources restored and this test kept: the check
  failed. The child raised `MovedIn20Warning` from `declarative_base()` in
  `app/core/database.py`.
- Full suite on the current sources: `758 passed in 6.39s`, no warnings
  summary. The targeted warning check is included.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not measured.
- PR #13 is merged as `a10e196`.

## 2026-10-07 - Pydantic and SQLAlchemy deprecation cleanup

- Scope: remove project-owned deprecated configuration without changing
  validation, ORM conversion, response fields, or OpenAPI examples.
  Tracked as GitHub issue #4. Branch `cursor/deprecation-cleanup-7154`,
  based on `origin/master` `a58dc8a`. No dependency upgrade, migration,
  schema redesign, live provider call, or private `.env`.
- Why this shape, for learning: Pydantic v1 stored model options in a nested
  `class Config`. Pydantic 2.6 still accepts that nested class, but warns and
  will remove it in v3. `model_config = ConfigDict(...)` is the same map of
  options, declared directly on the class. `from_attributes=True` is what
  lets `model_validate` read a SQLAlchemy row (or any object with attributes)
  instead of only a dict. Financial metrics already set
  `allow_inf_nan=False` on the shared base model. The response model sets
  that flag again next to `from_attributes=True`, so replacing the nested
  `Config` class cannot drop the Infinity/NaN ban. Pydantic 2.6 merges a
  subclass `model_config` with its parent; setting the flag explicitly does
  not rely on that merge. `FetchCompanyRequest` keeps
  `json_schema_extra={"example": {"ticker": "AAPL"}}`, which is the example
  FastAPI copies into the OpenAPI component. SQLAlchemy 2 moved
  `declarative_base` to `sqlalchemy.orm`. The function still builds one
  shared `Base`; only the import path changed. `CompanyDB` and
  `FinancialMetricsDB` still use that same `Base.metadata`.
- Decisions: do not reformat untouched legacy lines. `class Config` remains
  only where it existed. Create and update metric models stay without
  `from_attributes`. Historical prices still have no SQLAlchemy model; the
  new test uses a plain attribute object for that schema. The warning check
  runs in a fresh interpreter and turns the two targeted messages into
  errors. It does not ignore warnings.
- RED, before any production edit: `tests/test_model_config_compatibility.py::test_project_imports_do_not_emit_targeted_deprecations`
  failed. The child process raised `sqlalchemy.exc.MovedIn20Warning` at
  `app/core/database.py` while importing `declarative_base` from
  `sqlalchemy.ext.declarative`. A separate import of the five modules, with
  warnings recorded, showed five warnings: that SQLAlchemy warning plus four
  `PydanticDeprecatedSince20` warnings (`company`, `financial_metrics`,
  `historical_data`, `data_collection`). The normal suite showed four because
  it did not import `historical_data`. The other new behavior tests passed
  against the old code.
- GREEN: the warning check passes, and importing those five modules records
  zero warnings. Focused file plus JSON-overflow, lifespan/CORS, financial
  metric validation, and data-collection tests: 580 passed before the final
  unused-import cleanup. Final full suite is below.
- Baseline, clean environment, no `.env`, pinned requirements
  (`pydantic==2.6.1`, `sqlalchemy==2.0.23`), Python 3.12.3:
  `742 passed, 4 warnings in 5.67s`.
- Final full suite: `758 passed in 6.50s` before the pre-PR rebase, and
  `758 passed in 6.74s` after `git fetch` and `git rebase origin/master`.
  The branch was already on `a58dc8a`, so the rebase did not change files.
  Pytest printed no warnings summary either time. Sixteen new tests.
- Command, from the repository root:
  `.venv/bin/python -m pytest -q -p no:cacheprovider`
- Style: `black --check --line-length 79`, `isort --check-only`, and
  `flake8` pass for `tests/test_model_config_compatibility.py`. `isort`
  passes for `app/core/database.py`, `app/models/company.py`,
  `app/models/financial_metrics.py`, and `app/models/historical_data.py`.
  `isort` still fails `app/api/data_collection.py` for pre-existing import
  order. `black --line-length 79` still wants to reformat the five production
  files, and `flake8` still reports pre-existing long lines, whitespace, and
  unused imports on those files. None of the new lines are in that flake8
  list. `git diff --check` is clean. Repo-wide lint was not run. Full-file
  reformatting was skipped because it would rewrite untouched lines.
- Status corrections kept alongside the older entries below: PR #2
  (`fix/startup-lifespan-cors`) is merged as `b10d06e`. PR #3 (rebase
  workflow) is rebase-merged as `a58dc8a`. Sentences below that still say
  those pull requests were open are the record of that moment, not the
  current state.
- AI model: Grok 4.7 (Cursor cloud agent). Wall clock started about
  19:49 UTC; elapsed time was not stopwatch-measured. Account usage was not
  available in this Cursor session; no percentage was recorded and no reset
  was redeemed.
- Published as [PR #13](https://github.com/Waber/Investment-AI-Companion/pull/13),
  merged as `a10e196`.
- After that delivery: guarded Alembic baseline and isolated PostgreSQL
  tests. Issues #5 (minimal CI) and #6 (tooling config) are separate and
  do not own this journal or `docs/work-state.md`. PR #15 is merged as
  `b2541d7`. PR #22 is merged as `778735e`.

## 2026-10-07 - Rebase workflow rule

- Scope: documentation only. Record that this project keeps a linear history
  with rebase. No production code, tests, or GitHub repository settings.
- Decision: add a dedicated `## Git Workflow` section to AGENTS.md, after
  Working Agreements. Feature branches rebase onto `origin/master`
  (`git fetch`, then `git rebase origin/master`). Pulls use `git pull --rebase`.
  Own unpublished or feature-branch commits may be tidied with interactive
  rebase before a pull request. After rebasing an already-pushed feature
  branch, push only with `--force-with-lease`, and only on that author's own
  feature branch. Never rewrite `master` or shared branches. Pull requests
  are integrated with GitHub "Rebase and merge". That option is enforceable
  only when the repository has "Allow rebase merging" enabled; changing
  repository settings is the user's decision, not an agent's. Agents still
  must not merge a pull request unless the user explicitly authorizes it.
  `git config pull.rebase true` in this repository makes later pulls rebase.
  On a branch someone else also pushes to, coordinate before rebasing, or
  rebase only right before merge. Rebase conflicts are resolved by preserving
  both sides' intent, then the relevant tests are rerun; if unsure, stop and
  report.
- Why, for learning: a straight line of commits is easier to read, bisect,
  and review than merge-commit knots.
- Verification: reviewed the documentation diff. Pytest was not run because
  no code behavior changed. Account usage from the previous ChatGPT tooling
  was not available in this Cursor session; no usage percentage was recorded.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not measured.
- Delivery: one commit on `cursor/rebase-workflow-rule-0803`, based on
  `origin/master` (`b10d06e`, merge of pull request #2). Pull request opened
  against `master` and left unmerged. Deprecation cleanup is in progress on
  a separate Developer branch. This pull request and that one both edit the
  top of the journal and work-state; whichever merges second rebases and
  resolves those conflicts carefully.
- Update: PR #3 was rebase-merged as `a58dc8a` on 2026-10-07. The deprecation
  cleanup entry above is the later edit to these docs.

## Next Iteration Handoff - 2026-10-07

Status update: PR #2 is merged as `b10d06e`. PR #3 is rebase-merged as
`a58dc8a`. The deprecation cleanup this handoff describes is implemented on
`cursor/deprecation-cleanup-7154`
([PR #13](https://github.com/Waber/Investment-AI-Companion/pull/13));
see the 2026-10-07 cleanup entry above.
The bullets below stay as the original handoff.

### Resume Here

- User requested documentation only for this handoff. Do not treat it as an
  instruction to start implementation now. PR #2 is open against master:
  https://github.com/Waber/Investment-AI-Companion/pull/2
- Delivered branch: `fix/startup-lifespan-cors`, last implementation `5bd286c`,
  publication checkpoint `4fa939d`. This documentation commit follows both.
- Primary repository: `~/projects/Investment-AI-Companion`.
  Current worktree: `$TMPDIR/investment-metric-updates`. The configured
  PycharmProjects directory is not the authoritative repository. Temporary
  worktrees may disappear; recover committed work from Git, not stale paths.
- Read AGENTS.md and docs/work-state.md, inspect status/worktrees, fetch origin
  and check PR #2 before editing. If merged, branch from updated origin/master.
  If still open, use an explicit dependent branch from its current head and
  document the dependency; do not assume master contains these changes.
- Preserve user changes and the primary checkout's untracked `.python-version`.
  Do not assume any historical demo server/database remains available.
- No agents or implementation tasks remain active. Stop reason: user chose to
  defer further implementation and requested a reusable handoff, not exhaustion.
  Last checked usage before handoff: 42% five-hour / 7% weekly. Recheck live usage
  on resume; default checkpoint threshold is 80% unless explicitly overridden.

### Next Bounded Task: Deprecation Cleanup

Goal: remove project-owned Pydantic/SQLAlchemy deprecated configuration/imports
without changing validation, ORM conversion, response fields or OpenAPI examples.
Use a dedicated branch, a developer agent and an independent reviewer.

Files to inspect (do not mechanically replace configuration without tests):
- `app/core/database.py`: import declarative_base from sqlalchemy.orm; preserve
  the shared Base, engine and session behavior.
- `app/models/company.py`, `app/models/financial_metrics.py`,
  `app/models/historical_data.py`: migrate class Config to ConfigDict while
  retaining from_attributes. Financial metrics already inherits
  ConfigDict(allow_inf_nan=False); preserve that restriction when adding config.
- `app/api/data_collection.py`: migrate FetchCompanyRequest's json_schema_extra
  and retain its ticker example in generated schema.

Execution and acceptance:
1. Establish the full-suite baseline: last verified 742 passed, four warnings.
   Explicitly import historical_data in focused tests; it may not be loaded by
   the normal app suite, so four warnings are not an exhaustive file count.
2. Add regression coverage for model_validate on attribute/ORM objects, response
   serialization, rejection of nonfinite metrics and schema example preservation.
   Add a warning-as-error check for the targeted deprecations and demonstrate
   failure before migration. Do not suppress warnings to make tests pass.
3. Apply only minimal configuration/import changes; no dependency upgrades,
   migrations, schema redesign, provider calls or unrelated formatting.
4. Run focused tests, full suite, targeted warning checks and scoped style checks.
   Existing JSON-overflow, lifespan and CORS regressions must remain green.
5. Independent review, fix findings, then commit and update this journal and
   work-state with actual results, remaining warnings, branch and next action.
   Confirm publication scope with the next user instruction; this handoff only
   authorizes adding documentation to the existing PR.

Known test command (run from `$TMPDIR`, replace worktree path if changed):
```bash
/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=$TMPDIR/investment-metric-updates \
  ~/projects/Investment-AI-Companion/.venv/bin/python \
  -m pytest -q -p no:cacheprovider $TMPDIR/investment-metric-updates/tests
```
This avoids loading private .env configuration. Verify the interpreter still
exists. Run style checks from the worktree, not /tmp; the previous scoped checks
used Black with explicit --line-length 79, isort and flake8. Do not claim default
Black or repository-wide lint passed unless actually verified.

### Subsequent Backlog

After the small cleanup: guarded Alembic baseline/adoption and automated isolated
PostgreSQL tests, then editable investor profiles, then source-aware AI analysis.
Use the September research-workflow plan/spec for requirements, but reconcile its
old checkboxes with current code and this journal. CRUD/collector regressions,
JSON-safe overflow errors and lifespan/CORS are already delivered in PR #2.
Never merge the historical dependency WIP blindly: its OpenAI pin conflicted
with the FastAPI dependency set. Financial-metrics ingestion remains a placeholder.

## 2026-10-07 - Lifespan, CORS And Publication

- Dedicated branch `fix/startup-lifespan-cors` in the existing isolated worktree.
  User requested completion, push and PR; no merge. Includes five unpublished
  ancestor commits from the October 4 regression/validation work.
- Kierkegaard implemented lifespan using existing `init_db()`, propagation of
  initialization failures, disabled initialization mode and exact CORS matching
  without the URL-added root slash. No new database creation path or migrations.
- RED: 7 failed / 18 passed before implementation. GREEN: 25 focused cases;
  coordinator full isolated suite 742 passed with four preexisting warnings
  (SQLAlchemy and Pydantic). Deprecated FastAPI startup warnings are gone.
- Full command from `$TMPDIR`: `/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$TMPDIR/investment-metric-updates ~/projects/Investment-AI-Companion/.venv/bin/python -m pytest -q -p no:cacheprovider $TMPDIR/investment-metric-updates/tests`.
- Scoped checks: `black --check --line-length 79 main.py tests/test_lifespan_cors.py`,
  `isort --check-only` and `flake8` on the same files, plus `git diff --check`.
  Black's default 88-column check differs; explicit 79 matches default flake8.
- Updated IDE startup guide and stale remaining-work items. No user database,
  live provider, dependency upgrade or service restart. Migration/PG integration,
  profiles, AI and remaining deprecations deferred.
- Carver independently approved code/tests and the ancestor integration scan;
  reviewer reran 25 focused cases. Stop at completed scope, not quota. Commit,
  push and PR follow verification; no merge. Usage 6% at start, 29% after implementation.
  Agent model inherited; precise model identifier and elapsed time not measured.
- Published implementation `5bd286c` and prior slices in
  [PR #2](https://github.com/Waber/Investment-AI-Companion/pull/2) targeting master.
  No merge; agents closed. Final account usage 40% five-hour / 6% weekly.

## 2026-10-04 - JSON overflow validation fix

- Started from `2374acf` at50% five-hour/8% weekly usage. Dedicated branch
  `fix/json-overflow-validation`; bounded part of approved Task1, not full hardening.
- Plan: failing raw-overflow POST/PUT tests, minimal JSON-safe422 handler preserving
  ordinary error structure, persistence checks, full tests and independent review.
- Developer owns new validation module/tests and minimal main registration;
  coordinator owns documentation. No live calls, migrations or dependency changes.
- Faraday RED evidence:5 failed/4 passed, including four raw overflow500 responses
  and a nested nonfinite serialization failure. GREEN9 focused passed; coordinator
  independently ran full717 passed with six existing warnings using the clean-env
  command from prior entries. New-file Black/isort/flake8 checks passed.
- Nash approved independent spec/quality review and ran9 focused tests. Ordinary
  error detail structure remains unchanged; nonfinite float values become strings
  after jsonable encoding. No request body added to error responses. Main changes
  limited to registering the handler; no broad legacy formatting.
- Both agents closed at commit. Final review usage77% (below session90% ceiling).
  Stop at three completed slices with checkpoint buffer; do not start lifecycle
  work now. No push/merge or reset redemption. Inherited model, effort not timed.

## 2026-10-04 - Fake collector refresh regressions

- Separate branch `test/collector-refresh-regressions` based on reviewed `d9e56ce`.
  Developer owns only `tests/test_collection_updates.py`; no live provider calls.
- Scope: existing-company refresh, identity preservation, repeat without duplicates,
  missing provider result404 without writes, unrelated company/metrics preservation.
  Coordinator handles full tests/docs, followed by independent spec/quality review.
- Cicero delivered6 cases; coordinator full708 passed/six legacy warnings and
  scoped Black/isort/flake8 passed. Epicurus approved spec/quality without findings.
  No production changes or live provider calls. Both agents closed at commit.
  Characterization completes the planned collector refresh/not-found coverage.

## 2026-10-04 - Resume after user reset: metric creation conflicts

- User performed reset (coordinator did not redeem credit), usage0% both windows.
  Session-specific limit90%; AGENTS now permits an explicit session override.
- Branch `test/metric-creation-conflicts`, base `0008b0c`. Helmholtz owns a bounded
  test file: duplicate tuple rejection, each key component distinguishing records,
  real FK/unique constraint rollback with same-session reuse and persisted state.
- No production edits planned; characterize correct behavior. Coordinator owns
  continuity/full verification; independent review before commit. Collector follows
  as a separately committed slice if usage permits. Inherited model, time not timed.
- Results:6 new cases passed against unchanged production code. Full702 passed,
  six existing warnings, using prior clean-env pytest command. Poincare approved
  spec/quality with no findings. Black/flake8 passed; coordinator worktree-local
  isort found grouping drift from developer's temporary CWD check and corrected it.
  Usage20% five-hour/3% weekly; commit before starting collector work.

## 2026-10-04 - Company update conflicts and rollback

- Continued at60% five-hour usage with a small characterization slice on
  `test/company-update-conflicts`, based on `569a89e`. Same isolated worktree.
- Kant owns only the new conflict tests. Scope: duplicate name/ticker API
  rejection without mutation, then successful update; real constraint failure
  and recovery using the SAME repository session. No collector/metrics expansion.
- Coordinator will run full tests and independent review before local commit.
  At80% stop and notify user; no automatic reset. Inherited model, effort not timed.
- Completed3 characterization cases without production changes; coordinator full
  isolated pytest run696 passed, six existing warnings. Same env-i command as
  metric slice. Kant reports scoped Black/isort/flake8 passed; Raman static review
  approved specification/quality with no findings. No live database/provider calls.
- Usage rose60% ->75% ->82% between checks. Stop reason: user80% threshold reached;
  save local checkpoint and wait for explicit continuation, no reset redeemed.
  Agents closed. Next scope: metrics creation conflicts/rollback, then collector.

## 2026-10-04 - Financial metric update characterization

- User confirmed PR1 merged and authorized continuation with an80% account-usage
  stop threshold. Recorded this policy in AGENTS; no reset may be redeemed without
  authorization. Start usage29% five-hour/4% weekly consumed.
- New branch `test/financial-metric-updates`, base `1e05ab1`, worktree
  `$TMPDIR/investment-metric-updates`. Primary checkout/user files untouched.
- Hubble owns only new update tests; coordinator handles docs and full verification;
  independent reviewer follows. Scope: partial updates/null/zero/omission and invalid
  updates, not all remaining Task2 work. Existing correct code need not change.
- Inherited agent model; exact model identity and elapsed effort not measured.
- Results:82 new API characterization cases across all20 numeric fields. All pass
  against existing production code; no newly reproduced/fixed defect is claimed.
  Tests compare PUT/GET, fresh persisted snapshots, identity and unrelated rows;
  rejected422 payloads preserve timestamps as well as values.
- Coordinator full suite:693 passed, six existing warnings. Command from
  `$TMPDIR`: `/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$TMPDIR/investment-metric-updates ~/projects/Investment-AI-Companion/.venv/bin/python -m pytest -q -p no:cacheprovider $TMPDIR/investment-metric-updates/tests`.
- Black/isort/flake8 checks passed for the new test file. Independent Aristotle
  review approved spec compliance and quality without actionable findings.
- Hubble and Aristotle closed at delivery. Verification usage50% five-hour/8%
  weekly consumed; no reset. Stop at completed bounded scope, not exhaustion.
  Local commit only; remaining Task2 uniqueness/rollback/collector work not complete.

## 2026-10-04 - Recover and publish recent work

- User requested commit, push and PR. Recovered committed fixture/API/test work
  from `69258b9` onto `docs/demo-and-ide-delivery` in a new temporary worktree.
- Previous IDE documentation agents hit the usage limit before commit/review.
  The old temporary worktree now contains no files. Reconstructed the guide;
  do not describe it as an exact recovery of the uncommitted file.
- README links the guide. Current-state notes distinguish historical runtime
  observations from the present, unverified service state.
- No production behavior, dependency, database or primary-checkout changes.
  GUI startup and fresh installation remain untested. Verification and review
  results will be recorded before publication. No merge requested.
- Model inherited from session; exact identity and elapsed effort not measured.
- Verification: full isolated pytest suite passed611 cases with six existing
  warnings; `git diff --check` passed. Independent reviewer Ptolemy approved
  reconstructed documentation without actionable findings. Review was read-only;
  no GUI/provisioning/live provider validation is claimed.
- Publication includes the prior unpublished ancestor commits (404 behavior,
  website-update tests, API demo, fixtures and planning docs), but excludes the
  separate dependency-conflict WIP branch. Latest usage12% five-hour/2% weekly
  consumed; no reset redeemed. Scope ends with push and PR, not merge.

`CONVERSATION.md` contains legacy project history. This journal is the forward-looking delivery log for new agentic development.

## 2026-07-04 - Iteration 1 (project guidance and baseline tests)

### Scope
- Add repository-level agent/developer guidance.
- Add baseline automated tests.
- Fix financial metrics schema alignment.
- Add test seams for local API work without live providers.

### Status
- Delivered.

### Verification
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider` -> passed, 4 tests, 6 legacy warnings.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m black --check tests` -> passed, 5 test files unchanged.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m isort --check-only tests` -> passed.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m flake8 tests` -> passed.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m black --check app main.py setup_database.py tests` -> failed on legacy formatting debt in application files; this was already present in the pre-edit baseline. New tests were formatted separately and pass `black --check tests`.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m isort --check-only app main.py setup_database.py tests` -> failed on legacy import-order debt in application files; this was already present in the pre-edit baseline.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m flake8 app main.py setup_database.py tests` -> failed on legacy style/import issues in application files; `tests/` passes separately.

### AI model
- ChatGPT Codex (GPT-5).
- Subagents used: spec reviewer, plan reviewers, and a documentation implementation worker.

### Time tracking
- Task window: 2026-07-04 17:46-18:05 CEST, about 19 minutes for implementation and verification after plan approval.
- Team/subagents used: yes.
- Coordinator effort: about 19 minutes wall-clock in this implementation window, plus earlier spec/plan orchestration on this branch.
- Developer effort: documentation worker completed Task 1; remaining implementation was coordinated in-session with TDD checkpoints.
- Reviewer effort: one spec review and three plan review passes before implementation; final code review was pending at delivery and was completed on 2026-09-08 (see follow-up below).

### Notes
- `.python-version` existed before this iteration as an untracked local file and was left unmodified/uncommitted.
- Local `.venv` has `httpx 0.28.1` while `requirements.txt` pins `httpx==0.25.2`; tests use `httpx.ASGITransport` to avoid the incompatible legacy `TestClient` path in this environment.
- Full application lint/format cleanup should be handled as a separate technical-debt iteration to avoid mixing broad style churn with this baseline test/refactor slice.

## 2026-09-08 - Baseline review and corrective changes

### Scope and status
- Completed the independent senior engineer/architect review of the full baseline iteration, not only the latest documentation commit.
- Fixed all three actionable findings on dedicated branches and integrated the approved commits into `feature/project-guidance-and-baseline-tests`.
- Independent reviewer Noether accepted each fix. No reported blockers remain for this iteration.
- Full findings, evidence, and remaining limitations: [baseline review](reviews/2026-09-08-baseline-review.md).

### Changes
- Configuration: represent CORS origins as a JSON array in `.env.example`; add a smoke test that loads the actual template in an isolated environment.
- Financial metrics: reject non-finite values before persistence across all 20 numeric fields, preserving finite numbers, nulls, and omitted update fields.
- Test database: enable SQLite foreign keys on every physical connection before schema creation; test missing-company rejection, valid persistence, and replacement connections.

### Team and branches
- Coordinator: Codex (GPT-6), integration, independent verification, and documentation.
- Noether: senior engineer/architect, baseline review and independent review of each corrective change.
- Descartes: configuration fix on `fix/config-template-startup` (source commit `2c7fae8`).
- Linnaeus: database/QA fix on `fix/test-database-integrity` (source commit `00d346b`).
- Ohm: financial validation fix on `fix/finite-financial-metrics` (source commit `bc7c724`).
- Developers worked in separate worktrees; the database and validation fixes ran in parallel. Agents inherited the coordinator model.
- Integrated application commits: `5597a00`, `5f1b2fb`, and `719f691`. At review delivery these were on the development branch; subsequent publication is recorded below.

### Verification
- Combined suite at `719f691`: **537 passed, 6 existing deprecation warnings**. This includes parameterized unit cases and API regression tests, not 537 distinct workflows.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m black --check tests`: passed, 8 files unchanged.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m isort --check-only tests`: passed with default settings.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m flake8 tests`: passed with default settings.
- Each corrective code commit passed `git diff --cached --check` before commit.
- The combined suite ran from `$TMPDIR` with a clean environment and the repository on `PYTHONPATH`, without reading the developer's `.env`. Exact command:

```bash
/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=~/projects/Investment-AI-Companion ~/projects/Investment-AI-Companion/.venv/bin/python -m pytest -q -p no:cacheprovider ~/projects/Investment-AI-Companion/tests
```

- An earlier coordinator test launcher disabled dotenv loading globally and caused the template smoke test to fail. Removing that launcher override, without changing application code, produced the final result above.
- No live PostgreSQL instance or market-data providers were used. Full legacy application lint cleanup and dependency upgrades were not part of this follow-up.

### Time tracking and continuity
- Recorded local commit checkpoints (CEST): configuration at 20:16, database at 20:21, validation at 20:24 on 2026-09-08.
- Exact per-agent durations were not measured; no synthetic effort totals are reported.
- A usage-limit interruption stopped Ohm before final verification; work resumed from the existing files after the user reset the limit.
- The existing untracked `.python-version` was preserved.

### Publication after user approval
- On 2026-09-08 the user authorized committing, pushing, and merging the reviewed iteration into the default branch.
- Confirmed GitHub's default branch is `master`; fetching showed no divergent remote commits.
- Pushed `feature/project-guidance-and-baseline-tests`, then fast-forwarded local `master` through all 14 iteration commits to `08fc2fe` without conflicts.
- Re-ran the full isolated suite on `master`: **537 passed, 6 existing warnings**.
- Pushed `master` and independently confirmed the remote ref at `08fc2fe72fa6dce61b5856d36a120c6d99b52bc5`.
- This documentation-only follow-up records that completed publication; it does not change the tested application or test files.

## 2026-09-08 - Remaining-work iteration (in progress)

- User authorized continuing the remaining work listed in the baseline review.
- Created `feature/research-workflow-and-hardening` from published `master` at `6e1f2fc` in an isolated worktree.
- Added explicit session checkpoint rules and `docs/work-state.md` at the user's request, so later sessions can identify what is done, what is unfinished, and why work stopped.
- This is a documentation checkpoint while work continues, not a usage-limit stop. The current usage check did not indicate a reached limit.
- Product clarification received: horizon over ten years, broad markets including Poland/US/Europe/Asia, moderate-to-high risk, stocks/bonds/ETFs/ETCs, excluding direct derivatives such as futures/CFDs. The user requires an editable demo profile and support for different preferences, not hardcoded personal assumptions.
- Coordinator: Codex (GPT-6). No implementation agents dispatched for this new iteration yet. Precise elapsed time is not being measured; implementation and verification will be logged at delivery.
- No application or test files changed in this checkpoint. The previously published baseline passed 537 test cases; tests are not being represented as a new run for documentation-only changes.

## 2026-09-08 - WIP partial checkpoint: Task 2 CRUD regressions (paused)

### State and stop reason
- Worktree: `$TMPDIR/investment-crud-regressions`.
- Branch: `fix/crud-update-regressions`; pre-checkpoint HEAD: `10ab10d6bf1ba15e9105dc85d86b32c1816a5835`.
- User-requested pause to preserve state before the next iteration after context/usage pressure. The user reports that the previous run encountered a usage-limit error and that credits have now been reset. No credit balance or reset result was independently checked in this task.
- Task 2 remains incomplete and paused. The checkpoint is not approval to resume implementation or integrate changes.

### Actual work and decisions
- Confirmed the requested worktree, branch, and base commit; located AGENTS, the approved plan/design, and relevant source/test paths.
- Read the workflow skills for TDD, systematic debugging, plan execution, and verification; read AGENTS and the existing journal for this checkpoint.
- No application or test edits were made. Neither `tests/test_updates_api.py` nor `tests/test_collection_updates.py` was created. The only checkpoint edit is this journal entry.
- No implementation/design decisions or behavior corrections have been established. No delegation, integration, push, or worktree deletion was performed.
- All commands launched by this task had exited; no owned implementation or testing process remained running.

### Verification actually performed
- `pwd`: confirmed `$TMPDIR/investment-crud-regressions`.
- `git status --short --branch`: clean worktree on `fix/crud-update-regressions` before the journal edit.
- `git log -1 --format='%H %s'`: confirmed the pre-checkpoint HEAD above (`docs: clarify migration and analysis contracts`).
- `git diff --stat`, `git diff`, and `git diff --cached`: all empty before the journal edit.
- `git diff --check`: passed after adding this checkpoint entry.
- No pytest, red/green cycle, full suite, formatter, or linter was run. Earlier journal test results are historical, not verification of Task 2.

### Pending work, blockers, and exact next action
- The intentional user pause is the current stop condition; implementation blockers have not yet been investigated. Parent and Russell reviews remain pending before any final implementation commit or integration; the user separately authorized this WIP checkpoint commit.
- On explicit resumption, first inspect git status, read `docs/work-state.md`, the latest journal entry, `docs/superpowers/plans/2026-09-08-research-workflow-and-hardening.md` (Task 2), and `docs/superpowers/specs/2026-09-08-research-workflow-and-hardening-design.md`. Then inspect the assigned APIs/repositories, existing tests/conftest, and configuration without reading `.env` or a private database.
- Write the first failing regression test before production edits. Cover missing-update 404, company URL omitted/changed/null, metrics partial updates/null, conflicts, rollback/recovery, relevant cascade behavior, and fake-collector existing-company/404 paths. Investigate deterministic duplicate-ticker 400 semantics only as supported by regression evidence and existing constraints.
- Implementation ownership remains limited to `app/api/companies.py`, `app/api/financial_metrics.py`, `app/repositories/company_repository.py`, `app/repositories/financial_metrics_repository.py`, `tests/test_updates_api.py`, and `tests/test_collection_updates.py`. Do not edit data collection API, main, models, conftest, or unrelated files.
- Pending test invocation after confirming isolation: `/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 ~/projects/Investment-AI-Companion/.venv/bin/python -m pytest -q -p no:cacheprovider`, from this worktree. Use deterministic fakes, no live providers, no `.env`, and no private database. Record exact red/green and full-suite results when actually run.

### Model and time tracking
- Agent: Codex (GPT-6); no subagents used.
- Exact elapsed time was not measured. This entry records a partial checkpoint, not delivery of Task 2.

## 2026-09-22 - Missing-update responses (bounded iteration, completed locally)

### Scope and plan
- User authorized only the missing-record update fix, regression tests, independent review, a local commit, and journal. Other remaining-work tasks stay paused.
- Created `fix/missing-update-not-found` at `$TMPDIR/investment-update-404` from CRUD checkpoint `83bb7ed`. Old temporary worktrees are absent, but commits remain in Git. No old registrations/branches removed.
- Both update routes raise intended HTTP 404 inside a broad exception handler that converts it to 500. Start with failing API regressions, apply the smallest fix, verify 400/500 and successful-update behavior remains intact.
- Carson implements two routes and focused tests. Coordinator handles baseline/final verification, usage checks, and documentation; separate review follows implementation.
- No migrations, dependency updates, profiles, broad formatting, push, or merge.

### Baseline and resource checks
- Fresh baseline: 537 passed, six existing warnings. Command, from `$TMPDIR`:

```bash
/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$TMPDIR/investment-update-404 ~/projects/Investment-AI-Companion/.venv/bin/python -m pytest -q -p no:cacheprovider $TMPDIR/investment-update-404/tests
```

- Usage: before work, 8% five-hour and 2% weekly used; after preparation, 14% and 3%. These are not remaining-context measurements. No exact context counter is exposed; no reset/purchase performed.
- After implementation usage: 33% five-hour/6% weekly used; initial verification: 40%/7%; review and formatting completion: 48%/9%. These account-wide snapshots do not measure task cost or context capacity.
- Coordinator and agents use the configured inherited Codex model; exact model identity and elapsed effort were not independently measured in this iteration.

### Changes and verification
- Both update routes now re-raise HTTPException before the broad exception handlers. Missing company and financial-metrics updates preserve their existing 404 messages rather than returning 500. No repository/model/dependency changes.
- Added eight cases in `tests/test_missing_updates_api.py`: missing-record exact 404 and no DML/data changes, existing successful persisted updates, business errors mapped to 400, unexpected errors mapped to generic 500 without leaking their message.
- Carson reported RED: two tests failed with 500 instead of 404, six passed. After the fix, eight passed; full suite 545 passed. The coordinator did not independently reproduce RED.
- Hume independently reviewed specification compliance and code quality: approved, no actionable findings. His focused test run passed all eight cases.
- Coordinator's first style check found new-test formatting/import/line-length issues. Carson corrected only test formatting; no functional changes.
- Coordinator reran the full command above after formatting: **545 passed, six existing deprecation warnings**.
- Default checks passed for all nine test files: `.venv/bin/python -m black --check tests`, `-m isort --check-only tests`, `-m flake8 tests` (using the primary repository interpreter from this worktree).
- Tests use isolated SQLite, with repository exceptions injected only for error mapping. No live database/provider verification or application-wide lint cleanup was performed. Legacy warnings remain out of scope.

### Delivery and next action
- Carson and Hume were closed after final reports. No owned long-running process remains from this iteration.
- This change and documentation are saved together in a local commit on `fix/missing-update-not-found`; no push or merge. Primary `master` and the user's untracked `.python-version` remain unchanged.
- Stop reason: approved bounded scope completed, not resource exhaustion. No account reset or credit purchase was needed or performed.
- Next authorized iteration: integrate this reviewed fix as appropriate, then add failing Task 2 regressions for URL omission/change/null. Broader CRUD, lifecycle, PostgreSQL, profiles, and AI work remain unfinished; see [work-state](work-state.md).

## 2026-09-22 - Company website updates (bounded test-only task, completed locally)

- User authorized the next small task with resource checks; scope is only website omission, replacement, null clearing, and invalid URL rejection. No broader CRUD/migration/AI work.
- Branch `test/company-website-updates` at `$TMPDIR/investment-website-updates`, based on reviewed `3a2b0af`; parent suite verified in this session: 545 passed, six legacy warnings.
- Existing update code already handles `exclude_unset` and optional URL serialization. Contrary to the earlier generic next-step wording, characterization tests can legitimately pass immediately; do not invent a failing bug or change correct production behavior.
- Ohm owns only `tests/test_company_website_updates.py`; coordinator owns documentation and final verification. Separate independent review follows.
- Initial resource check: 59% five-hour and 10% weekly used. These account-wide percentages are not a context measurement or a completion guarantee. No reset/purchase.
- No push/merge; preserve prior branches and the primary checkout's unrelated `.python-version`.

### Results and handoff
- Added only `tests/test_company_website_updates.py` plus coordinator documentation. Four cases verify omission, normalized replacement, null clearing, and invalid URL rejection without mutation through PUT responses, GET readback, and fresh database sessions. Production code was already correct and remains unchanged.
- Ohm reported focused four passed/full 549 passed, six existing warnings. Dalton independently approved spec and quality, no findings, and ran all four focused cases successfully.
- Coordinator independently ran the full suite: 549 passed, six existing warnings. Command from `$TMPDIR`: `/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$TMPDIR/investment-website-updates ~/projects/Investment-AI-Companion/.venv/bin/python -m pytest -q -p no:cacheprovider $TMPDIR/investment-website-updates/tests`.
- Coordinator's repository-local isort check required one blank line between third-party and application imports despite the developer's reported pass; corrected that formatting-only issue after review. Default Black/isort/flake8 checks and the suite are rerun before commit.
- Usage after preparation: 65% five-hour/11% weekly used; after implementation and full verification: 78%/13%. No exact context counter, reset, or purchase. Stop at completed scope to conserve the remaining allowance, not because a limit was reached.
- Agents Ohm and Dalton closed at delivery. Same configured inherited model; exact identity and elapsed effort not independently measured. No agent-owned long-running process.
- SQLite-only characterization; no PostgreSQL/provider calls and no claim of fixing a newly reproduced bug. Existing warnings remain.
- Next separately authorized slice: metric partial-update/null regression coverage. The full Task 2 remains incomplete. Keep this local branch for later integration; no automatic push/merge.
- Final post-format verification: 549 passed, six existing warnings; default Black/isort/flake8 passed for all ten test files. After review and final verification, usage was 85% five-hour/14% weekly consumed. Scope completed with remaining allowance; both agent shutdowns confirmed.

## 2026-09-26 - Local API demo and request guide

- User approved running the latest tested backend with an isolated database and documenting API requests. Worktree `$TMPDIR/investment-api-demo`, branch `chore/local-api-demo`, base `731c513`. No production behavior/dependency changes or merge/push.
- Design: reuse installed Python environment and existing app; fresh owner-only PostgreSQL cluster, Unix socket only, loopback HTTP, synthetic data. Avoid real `.env`, API credentials and developer database. Provide a curl walkthrough and repeatable HTTP smoke client; review them independently.
- Coordinator initialized PostgreSQL14.19 at `$TMPDIR/iac-demo.h7TbGw/data`, role `demo`, DB `investment_demo`, socket directory `$TMPDIR/iac-demo.h7TbGw`, port15432, host authentication rejected and TCP listening disabled.
- API runs detached on `127.0.0.1:8081` with clean environment and DEBUG=False. Logs/PID reside in the runtime directory; these intentionally running services remain available to the user. Temporary files are not durable storage or backups.
- Verified startup schema creation, company POST and financial-metrics POST on PostgreSQL, Swagger HTML200, and diagnostic endpoint403. Seeded one synthetic `DEMO` company and one metrics row (IDs1 initially); no external providers called.
- Fresh isolated regression suite: 549 passed, six existing deprecation warnings. Command from `$TMPDIR`: `/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$TMPDIR/investment-api-demo ~/projects/Investment-AI-Companion/.venv/bin/python -m pytest -q -p no:cacheprovider $TMPDIR/investment-api-demo/tests`.
- Curie develops only `docs/api-demo.md` and `scripts/smoke_demo.py`; coordinator owns runtime, README and state/journal. Independent review and final live smoke results follow below.
- Initial usage60% five-hour/26% weekly; after launch73%/28%. No context-capacity inference, reset or purchase. Exact agent model/effort duration not independently measured.
- This manually tested local PostgreSQL runtime does not replace the remaining automated migration/integration-test work. AI/profile functionality remains unimplemented; provider metrics route remains a placeholder.
- Curie's smoke and coordinator repeat passed against live PostgreSQL, including CRUD, persisted updates, 422/404 and own-record cleanup. Script passed Black79/isort/flake8.
- Ohm's review found one proxy/config inheritance concern; all curl examples now use `-q --noproxy '*'`. Otherwise approved by static review. Restart commands documented but not exercised.
- A usage-limit error blocked the final documentation/commit on the previous turn. Existing files and running services were preserved. User then authorized continuation; limits now report 0% used. No reset was redeemed by the coordinator.
- Demo documentation checkpoint completed before adding reusable fixtures. No production code changed, no push/merge. Intentional API/PostgreSQL services remain available; agents are closed after their reports.

## 2026-09-26 - Reusable synthetic demo fixtures (completed locally)

- User requested persistent/reproducible test data for API and future frontend testing. Worktree `$TMPDIR/investment-demo-fixtures`, branch `feature/reusable-demo-fixtures`, base `83940ea`.
- Decision: versioned JSON plus create-only HTTP seeder; keep the running API unchanged and avoid direct DB/private settings access. Default preview is GET-only; --apply explicit. Existing records/values remain unchanged; partial failures can be resumed by rerun, not rolled back across requests.
- Coordinator fixture: six explicitly synthetic companies, five currencies, 20 financial rows across2023-2025 annual/Q12026. Profit/loss/zero/null/no-reports scenarios. No real security data or unsupported ETF/bond claims.
- Existing live records include original `DEMO` and a user-created `string` ticker. Neither may be modified or removed by seeding.
- Developer Laplace owns `scripts/seed_demo.py` and `tests/test_seed_demo.py`; coordinator owns fixture/schema tests/documentation. Independent review follows before live writes.
- Fixture schema/scenario verification: two tests passed, six existing warnings. Full seed behavior tests/review/live application pending.
- Usage restarted at0% five-hour/weekly as reported by tool, not reset by coordinator; after preparation24% five-hour/4% weekly used. No exact context counter available.

### Verification and review
- Laplace implemented only seeder and unit tests. Initial TDD run failed collection because the implementation module did not exist; subsequent60 focused cases passed. This is new functionality, not a claim of reproducing an old application bug.
- Volta independently reviewed fixture, script, tests and guide: approved without actionable findings; 62 focused cases passed. Tests cover dry run, creation, repeatability, edits/unrelated records, timezone equivalence, pagination, collisions before writes, invalid fixtures and partial-failure resumption.
- Coordinator reran full isolated suite: **611 passed, six existing warnings**. Exact command from `$TMPDIR`: `/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$TMPDIR/investment-demo-fixtures ~/projects/Investment-AI-Companion/.venv/bin/python -m pytest -q -p no:cacheprovider $TMPDIR/investment-demo-fixtures/tests`.
- Default Black/isort/flake8 checks passed for `scripts/seed_demo.py`, `tests/test_seed_demo.py`, and `tests/test_demo_fixture.py` from the worktree. No production app/style/dependency changes.
- Live CLI dry run against verified loopback demo planned6companies/20metrics and performed no writes. First `--apply` created6companies/20metrics; second `--apply` created0/0 and skipped all6/20. UTC matching worked against PostgreSQL's offset timestamps.
- Compared pre-seed JSON snapshots against fresh API reads: both preexisting companies (including user-created ticker `string`) and original metrics row were unchanged. At verification total8companies/21metrics; fixture IDs6-11. IDs are not portable and docs do not rely on them.
- One initial coordinator curl snapshot command was rejected by shell globbing before any request; quoting the URL corrected the launcher. No data writes were involved in that error.

### Delivery and continuity
- Both agents closed. API and PostgreSQL intentionally remain running for the user. No other long-running process.
- Dataset/scenarios and commands: [demo-data](demo-data.md). API request/lifecycle examples: [api-demo](api-demo.md). JSON fixture is versioned and can repopulate a new isolated demo; temporary DB files are not backups.
- At final verification70% five-hour/11% weekly allowance was used. Completed this scope without another limit failure; no reset/purchase. Exact effort/model identity not independently measured; agents used inherited model.
- Work saved locally on `feature/reusable-demo-fixtures`; no push/merge. Remaining technical tasks are unchanged. Next separately authorized task can cover metric partial updates/null; do not reset the user's running demo to develop it.
