# Current Work State

## Merging #88, #97, and #98: 2026-10-23

- The owner asked to merge #88, #97, and #98 in that order and
  to resolve the conflicts. #88 (`docs/HANDOFF.md`) merged as
  `1d684c6`. #97 is rebased onto it; #98 follows.
- #97 (`cursor/ticker-uniqueness-followups-08b9`, Closes #92):
  revision `0007` now revises `0006` (#94's price revision), so
  the chain is `0001` to `0007` with one head. The `0007` tests
  use `0006` as the revision before `0007`.
  `test_revision_0006_stores_sqlite_prices_as_text` stops at
  `0006`, because `0007` rebuilds `companies` on SQLite and that
  test checks `companies` is unchanged. What `0007` does: it
  refuses rows that collide on `upper(ticker)`, replaces
  `uq_companies_ticker` with a unique index on `upper(ticker)`,
  drops `uq_company_name_ticker`, and adds the non-unique
  `ix_companies_ticker`. On SQLite only `companies` is copied,
  inside Alembic's `autocommit_block`, and an open caller
  transaction is refused before the copy.
- Tests: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset. CI
  command on SQLite, local SQLite 3.54.1: 2 failed, the rest
  passed. Both failures
  (`test_floats_that_round_to_1e12_abort_the_sqlite_upgrade`,
  `test_sqlite_boundary_float_upgrades_below_1e12`) also fail on
  a clean `master` `1d684c6` with the same SQLite. That SQLite
  casts a float to text with more digits than the SQLite in CI,
  so the expected strings differ. Not caused by this merge. No
  local PostgreSQL; GitHub Actions runs both jobs before each
  merge. No live market-data calls.
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Next action: merge #97 after both CI jobs pass, then rebase
  and merge #98.

## Open work elsewhere

- #33: notes and theses are on master (revision `0005`). Master's
  work-state still lists the `/ui` forms and any HTTP API as
  incomplete. Those belong to the Frontend Developer.
- #32: the watchlist backend is on master (revision `0004`).
  The `/ui` watchlist page, the stale-price marker, and the
  PL/EN strings are still open.
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
- #96: the watchlist `/ui` page (UI part of #32).
- #86: #98 adds the shared text validator. The `/ui` helper
  moves onto it with the Frontend Developer.
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
