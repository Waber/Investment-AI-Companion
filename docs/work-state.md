# Current Work State

## Ticker uniqueness follow-ups (#92): 2026-10-22

- Branch `cursor/ticker-uniqueness-followups-08b9`, from
  `origin/master` `1223be6`. One pull request to `master`.
  Not merged. `templates/`, `static/`, and `app/ui/` were not
  edited. Issue #86 still owns `normalize_name` on the forms.
- Completed: the duplicate-ticker command prints the fixed URL
  line for `ImportError` and `ValueError`, and it does not
  create a missing SQLite file. Revision `0003` keeps its SQL
  in the file and does not import `scripts`. Revision `0007`
  revises `0005` (one Alembic head; `0006` stays on unmerged
  PR #94). It refuses rows that collide on `upper(ticker)`,
  replaces `uq_companies_ticker` with that expression, and
  drops `uq_company_name_ticker`. On SQLite only `companies`
  is copied. The copy uses Alembic's `autocommit_block`, then
  an explicit `BEGIN`/`COMMIT`, and restores the foreign-key
  pragma. A new foreign-key violation rolls that copy back.
  `ix_companies_ticker` is a non-unique index on the column
  so `ticker == value` lookups are not full scans. Downgrade
  restores the column unique index and the pair constraint,
  and drops the plain index. SQLite
  cannot reflect that expression index. The reflection warning
  is filtered by its message at the reflection calls, and the
  empty-autogenerate checks read `sqlite_master` or
  `pg_indexes` for the unique `upper(ticker)` index.
- Incomplete: re-chain `0007` onto `0006` after #94 merges.
  That is a later request, not this pull request.
- Tests: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1703 passed, 212 deselected, coverage 96.47% (4145
  statements, 122 miss, 1128 branches, 48 partial). No
  reflection warning for ``uq_companies_ticker``.
  Local PostgreSQL 16, `TEST_POSTGRES_DSN` on
  `investment_test`, `REQUIRE_POSTGRES=1`,
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`
  -> 212 passed, 1703 deselected. Scoped black, isort, and
  flake8 passed. No live market-data calls. GitHub Actions is
  recorded in the pull request, not in a later commit.
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Next action: the owner reviews the pull request. Agents do
  not merge.

## Open work elsewhere

Master's work-state still lists the items below. This section
keeps those and the notes added on this branch. The long
historical sections stay on `master`. When `0007` is re-chained
onto `0006`, union this list with #94's list as well.

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
  price profiles. The `/ui` synthetic badge still matches only
  `[IAC-DEMO-V1]`.
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
  length on SQLite. #94 is open and not merged. Its revision
  is `0006`, which revises `0005`. This branch does not
  contain `0006`. `0007` revises `0005` until #94 merges.
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
