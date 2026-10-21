# Current Work State

## Price bars QA delta (PR #94): 2026-10-21

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
  conversion the upgrade applies: PostgreSQL `ROUND` is half
  away from zero, SQLite quantizes the real's text half-even.
  A float keeps about 15 significant digits. The default source
  is the latest `retrieved_at`, then Python code-point order
  (`fake` beats `[IAC-DEMO-V2]`). New copy does not add a
  not-investment-advice notice.
- Tests: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset.
  CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 1715 passed, 216 deselected, coverage 96.35%
  (4316 statements, 131 miss, 1186 branches, 54 partial).
  Local PostgreSQL 16.15, `REQUIRE_POSTGRES=1`, and
  `-m integration` -> 216 passed, 1715 deselected.
  Scoped black, isort, and flake8 passed. No live market-data
  calls. The Actions run id goes on the pull request, not in a
  later docs-only commit.
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Next action: both GitHub Actions jobs on this head. The pull
  request stays ready for review.
- History: older snapshots are in `docs/development-journal.md`.
  They are not repeated here.
