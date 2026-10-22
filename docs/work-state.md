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
  is copied, with foreign keys off for the copy. Downgrade
  restores the column index and the pair constraint.
- Incomplete: re-chain `0007` onto `0006` after #94 merges.
  That is a later request, not this pull request.
- Tests: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1697 passed, 212 deselected, coverage 96.47% (4143
  statements, 122 miss, 1126 branches, 48 partial).
  Local PostgreSQL 16, `TEST_POSTGRES_DSN` on
  `investment_test`, `REQUIRE_POSTGRES=1`,
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`
  -> 212 passed, 1697 deselected. Scoped black, isort, and
  flake8 passed. No live market-data calls. GitHub Actions is
  recorded in the pull request, not in a later commit.
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Next action: the owner reviews the pull request. Agents do
  not merge.

## Open work elsewhere

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
