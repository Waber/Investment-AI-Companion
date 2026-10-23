# Current Work State

## Merged #88, #97, and #98: 2026-10-23

- The owner asked to merge #88, #97, and #98 in that order and to
  resolve the conflicts. All three use "Rebase and merge". #88
  (`docs/HANDOFF.md`) and #97 (Closes #92) are on `master`. #98
  (Refs #86) merges with this commit as its last one.
- Master after the merges: Alembic chain `0001` to `0007`, one
  head. `0007` revises `0006` (#94's prices) and puts the unique
  index on `upper(ticker)`. `app.validation.text.clean_text` is
  the shared free-text checker for company names, watchlist
  labels, notes, and theses. Codes: `blank`, `too_long`,
  `control_char`, `bidi`, `surrogate`. Length constants:
  `COMPANY_NAME_MAX` 255, `WATCHLIST_LABEL_MAX_LENGTH` 80,
  `NOTE_BODY_MAX` 10000, `THESIS_TITLE_MAX` 200,
  `THESIS_BODY_MAX` 10000, `THESIS_BREAKERS_MAX` 5000. The 422
  contract is in `docs/api-demo.md`.
- Conflict decisions: #97 `test_revision_0006_stores_sqlite_prices_as_text`
  stops at `0006`, because `0007` rebuilds `companies` on SQLite.
  The `0007` tests use `0006` as the revision before it. #98 kept
  both imports in `app/models/database_models.py` (#94's
  `PriceAmount` and its `COMPANY_NAME_MAX`).
- Tests: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset. CI
  command on #98's rebased head, local SQLite 3.54.1: 1823
  passed, 2 failed, 221 deselected, coverage 96.30%. Both
  failures (`test_floats_that_round_to_1e12_abort_the_sqlite_upgrade`,
  `test_sqlite_boundary_float_upgrades_below_1e12`) also fail on a
  clean `master` with that SQLite: it casts a float to text with
  more digits than the SQLite in CI. Not caused by these merges.
  No local PostgreSQL; both GitHub Actions jobs passed on each
  pull request before its merge. No live market-data calls.
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Next action: the queue in `docs/HANDOFF.md` section 3, starting
  with #96.

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
- #86: the shared validator is on master (#98). The `/ui` helper
  (`normalized_company_name` in `app/ui/form_fields.py`) moves
  onto it with the Frontend Developer, and the form maps
  `exc.code` to a catalog key. A name made only of combining
  marks is still rejected by the form and accepted by the API.
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
