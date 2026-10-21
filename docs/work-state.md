# Current Work State

## Price bars review delta (PR #94): 2026-10-21

- Master: `origin/master` `1223be6` (#91, notes and theses).
  That revision is `0005`. This branch is
  `cursor/price-bar-followups-85-5c38`. Revision `0006` revises
  `0005`. Not merged.
- Open pull requests:
  - [#94](https://github.com/Waber/Investment-AI-Companion/pull/94)
    price bar follow-ups. Ready. Closes #85.
  - [#88](https://github.com/Waber/Investment-AI-Companion/pull/88)
    `docs/handoff-external-agent`. Ready. Not part of this change.
- Queue: the owner merges #94 with "Rebase and merge". Agents do
  not merge. Skipped price bars are logged once per id and are
  not in the response; showing them stays with the PM. Editable
  profiles and source-aware AI analysis remain unimplemented.
  Financial-metrics provider ingestion is still a placeholder.
- Key decisions: OHLC is `Decimal`, and the JSON price is an
  8-place string. Parse it with `Decimal`, not float math.
  `NUMERIC(20, 8)` is the limit. The `0006` preflight uses the
  conversion the upgrade applies, and SQLite text `NaN` is
  rejected with `is_finite` because `quantize` does not raise.
  A lost connection or a locked database is a `DBAPIError`.
  The repository rolls it back and re-raises it, so the API
  answers 500. Only a bind `ValueError` becomes the fixed
  sentence. The default source reads `max(retrieved_at)`, then
  the distinct source names at that instant, then Python
  `max` (`fake` beats `[IAC-DEMO-V2]`). It does not load the
  tied rows. Autogenerate would render `NUMERIC` on SQLite
  for a future table; the live column is still TEXT. New copy
  does not add a not-investment-advice notice.
- Tests: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1718 passed, 216 deselected, coverage 96.35%
  (4318 statements, 131 miss, 1188 branches, 54 partial).
  Local PostgreSQL 16.15, `REQUIRE_POSTGRES=1`, and
  `-m integration` -> 216 passed, 1718 deselected.
  Scoped black, isort, and flake8 passed. No live market-data
  calls. The Actions run id goes on the pull request, not in a
  later docs-only commit.
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Next action: both GitHub Actions jobs on this head. The pull
  request stays ready for review.
- History: older snapshots are in `docs/development-journal.md`.
  They are not repeated here.

## Open work elsewhere

- #33: notes and theses `/ui` forms and HTTP API. The backend
  merged in #91.
- #32: the Frontend Developer watchlist page, stale-price
  marker, and PL/EN strings. The backend merged in #90.
- #8/#10: the instrument baseline planned as `0001_baseline.py`
  for instruments, prices, and ETF/ETC attributes. Prices, the
  watchlist, and notes now have later revisions. `init_db`
  still uses `create_all` (#10).
- #86: the shared text validator for names, labels, notes, and
  theses, covering Tag, U+206A–U+206F, U+061C, and the Cs gap,
  with Co/Cn treated as blank. The `/ui` part is to be agreed
  with the Frontend Developer.
- #28: ETF/ETC attribute columns, fund attributes, and the
  attribute forms. Yahoo still does not implement
  `FundAttributes`.
- #54: a yfinance failure hidden by `hide_exceptions` can look
  like no data, and the balance-sheet ratio stays in R1 #54.
- #26: the company row is not renamed to Instrument, there is
  no unique `(ticker, exchange)`, the company list has no
  filters, and metrics are not limited to stocks.
- #34: a `source=manual` column, and a synthetic marker that
  survives a description edit. The badge still matches a
  description that starts with `[IAC-DEMO-`.
- The fake collector still serves demo-v1 profiles from
  `fixtures/demo-v1.json`. `run_demo` uses demo-v2.
