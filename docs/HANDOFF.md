# Handoff for an external coding agent

This guide lets a coding agent outside Grok Bot (Claude Code, Codex,
Cursor IDE) pull `master` and continue the work. State is as of
2026-11-20: `master` has the backend instrument score (#135) and the
code-reviewer agent (#138). If `master` has moved, trust
`docs/work-state.md` and GitHub over this file.

## 1. Start here

Read in this order before choosing a task:

1. `AGENTS.md`: working agreements, Git workflow, domain rules, quality gates.
2. `docs/work-state.md`: the newest section at the top.
3. `docs/development-journal.md`: the newest entry at the top.
4. `docs/RUN_DEMO.md`: how to run the local `/ui` demo.
5. `docs/product-requirements.md` when a task touches product behavior.

Przemek (also called Przemo) is the owner. Answer him in the language he uses (usually Polish).
Code, identifiers and documentation stay in English. He is learning
Python, so explain non-obvious choices.

### Setup (from README)

```bash
git pull --rebase            # on master
python3.12 -m venv .venv     # once per machine
source .venv/bin/activate
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
```

Run the demo: `python -m scripts.run_demo` (see `docs/RUN_DEMO.md`).

### Tests (CI command)

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  -W error::DeprecationWarning --cov=app --cov=main --cov=scripts \
  --cov-branch --cov-report=term-missing --cov-fail-under=80
```

PostgreSQL tests: `pytest -m integration` with `TEST_POSTGRES_DSN` set
to a local throwaway database whose name contains `test` as its own
word (see README "Tests And Quality Checks" for the safety rules).
Style: `black --check`, `isort --check-only`, `flake8` on
`app main.py setup_database.py tests`. CI runs pytest on SQLite and
PostgreSQL; it does not run the style checks.

### Git workflow

- One branch per slice, PR to `master`. Rebase onto `origin/master`;
  never merge `master` into a branch. Force-push only with
  `--force-with-lease` on your own branch.
- Integrate with "Rebase and merge". **Agents never merge.** Przemek
  approves every merge explicitly.
- Every PR updates `docs/work-state.md` (replace stale state, don't pile
  up snapshots) and adds a top entry to `docs/development-journal.md`
  (scope, decisions, verification, AI model, time).
- Keep coverage >= 80% (currently ~96%). Tests never call live market
  data providers; use deterministic fakes.
- Never commit secrets, `.env`, or local configuration.

## 2. Current state (2026-11-20)

Merged since the first version of this guide (`a21d912`): #83 (price
bars, demo-v2 fixture), #87 (unique ticker index, shared company names,
`scripts.check_duplicate_tickers`), #89 (instrument-type select on the
company forms), #90 (watchlist backend, #32), #91 (notes and theses
backend, #33), #94 (price-bar follow-ups, Decimal OHLC, #85), #97
(case-insensitive ticker index on `upper(ticker)`, #92), #98 (shared
free-text validator `app.validation.text.clean_text`, Refs #86), #101
(the `/ui/watchlist` page and the heart toggle, closes #96, merged
2026-10-28), #108 (watchlist batch reads, merged). #106 (the `/ui`
company name on `clean_text`, Refs #86) is merged.

Merged after 2026-10-30: #107 (price-bar follow-ups), #104 (notes and
theses on the instrument page and their JSON API, Refs #33, revision
`0008`), #125 (the security-audit skill), #124 (`REVIEW.md`), #126
(the owner's name), #127 (company and metric provenance, revision
`0009`), #128 (ETF and ETC attributes and price-derived metrics,
revision `0010`), #130 (delete fund attributes), #132 and #134
(review nits and tests), #138 (the code-reviewer agent and
`/review-pr`, Refs #102), and #135 (the backend instrument score and
weight sets, revision `0011`, Refs #35).

`alembic/versions` on master runs `0001` to `0011` in one chain
(`0011_score_weights.py` is the head). Run `alembic heads` to check; a
new revision revises the current head. The chain upgrades an existing
database: `0001` expects `companies` to exist. A new database is built
by `create_all` and then `alembic stamp head` (`app/core/init_db.py`).
Issue #8 is the open baseline revision.

#33 (notes and theses): the backend (#91) and the UI and JSON API
(#104, merged 2026-11-07) are on `master`. The issue is still open.

Known local issues: with SQLite 3.54 two `0006` float boundary tests in
`tests/test_price_bar_migration.py` fail locally on `master`. That
SQLite casts a float to text with more digits than the SQLite in CI.
A git-ignored `demo/` directory left by a local demo run makes
`tests/test_run_demo.py::test_child_process_does_not_inherit_dotenv_database`
fail; a clean checkout does not have it. CI is green.

## 3. Prioritized queue

Each item: own branch, PR, tests, work-state + journal updated.

a. **#33 notes and theses UI and HTTP API**: merged in #104 on
   2026-11-07. The issue is still open.
b. **#102 Code Reviewer agent** (priority high): a reusable review
   agent for every pull request. Merged in #138:
   `.claude/agents/code-reviewer.md`, the `/review-pr` skill (pending
   GitHub review with `--post`), and path rules in
   `.agents/review/instructions.toml`. #102 stays open until Przemek
   accepts the draft. Run `/review-pr <N>`
   on every PR before asking Przemek to merge it. GitHub Actions
   automation stays out of scope (API key and cost decision).
c. **#86 remainder**: pull request #106 moves
   `normalized_company_name` onto `clean_text`. Merged.
d. **#95** price-bar repository follow-ups (skipped bars, batch
   duplicates, currency length).
e. **#34 remainder**: `source=manual` column and a synthetic marker
   that survives a description edit.
f. Then, in order: #28 and #139 (a fund-attribute update can keep an
   AUM without its date or currency, found in the #135 review), #30
   and #31 (need #28), #35 (the backend score and weight sets are
   merged in #135; the `/ui` part remains), #36, #37 (needs
   #36; ignore the disclaimer wording in the issue, see below), #8
   remaining baseline, #38, #39, #40.

Watchlist follow-ups: #99 (named lists), #100 (on-demand AI summary
per row).

Post-demo: #54, #55, #56, #57, #58, #48, #62, #73, #52, #53, #10, #12,
#20, #65, #76, #93. #103 (comments on buy and sell transactions,
shown in the transaction history) is deferred until #57 brings
transactions.

## 4. Constraints

- The app is a research tool. Show source, freshness, assumptions,
  risks and uncertainty.
- Disclaimer: requirements section 12 dropped the "not investment
  advice" requirement on 2026-10-10. The existing `/ui` banner stays;
  add no new disclaimer copy.
- Demo is local (loopback), no authentication, AI analysis mocked
  (deterministic PL/EN mock).
- UI: server-rendered Jinja2 + HTMX, Polish and English.
- Database: PostgreSQL in production, SQLite for tests and the demo;
  CI runs both.
- Never commit secrets.
