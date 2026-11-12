# Current Work State

## Fund attribute forms (#28, #34): 2026-11-12

- Branch `cursor/ui-fund-attributes-forms-98e5`, from
  `origin/master` `1dab8fc` (pull request #128 is merged).
  One pull request to master. Refs #34 and Refs #28. Both
  issues stay open. The agent does not merge. No Alembic
  revision. `0009` and `0010` were not edited. Models, the
  schema, collectors, scoring, AI adapters, and the Yahoo
  collector were not edited. Pull request #130 on master
  adds `FundAttributesRepository.delete` and the JSON
  DELETE. This checkout does not have that method, and this
  slice has no UI delete form yet.
- Completed: `GET` and `POST /ui/companies/{id}/fund-attributes/new`
  and `.../edit`. The forms validate with
  `FundAttributesCreate` and `FundAttributesUpdate` and write
  through `FundAttributesRepository`. They do not call the
  JSON API and they do not read the demo-seed header. Create
  stores `manual` and `is_synthetic` false. Update stores
  `manual` and keeps `is_synthetic`. Posted `source` and
  `is_synthetic` are ignored. `as_of` is required on create.
  The edit page shows `updated_at`.
- TER is a percent on the form (0 to 100; `0.07` means 0.07%)
  and a fraction in the row. One comma is a decimal mark, so
  `1,5` is 1.5 percent. Two separators are a 422. The
  conversion uses `Decimal` both ways, including the bounds
  and a null TER. The edit field still shows a period. The
  `Float` column is unchanged, so the stored value is still
  a float after the model accepts the fraction.
- Detail links: add when an ETF or ETC has no row, edit when
  it has one, nothing for a stock. Invalid input is 422.
  A repository `ValueError` is 400. A bad id, an unknown id,
  or a stock is the HTML 404. CSRF is `require_same_origin`.
  Redirects use `safe_next`.
- Leftover: an ETF or ETC changed to STOCK while a row
  exists keeps the row. The detail page still shows it and
  has no form link. The form routes answer 404. The JSON
  DELETE exists on master in #130. This slice has no UI
  delete form yet. `GET /new` when a row already exists
  redirects to the edit form. `POST /new` in that case is
  still 400. The detail page formats TER with `Decimal`
  so 0.00001 percent is not shown as 0. Yahoo still does not
  implement `FundAttributes`.
- Tests: no `.env`. `DATABASE_URL` was not a personal
  database. SQLite 3.45.1, CI pytest command: 2247 passed,
  254 deselected, coverage 96.97%. PostgreSQL 16.15,
  `REQUIRE_POSTGRES=1`, DSN
  `postgresql://postgres:postgres@127.0.0.1:5432/investment_test`:
  254 passed, 2247 deselected. black, isort, and flake8 passed
  on the Python files this change touches. No live market-data
  calls. The HTML was checked through the test client. A
  desktop browser was not driven.
- Account usage: this session cannot read the meter. No
  percentage is recorded. No reset was redeemed.
- Active agents: none. Blockers: none for this slice. This
  note is not approval and not a merge.
- Next action: GitHub Actions on this head, then review.
  Do not merge. A UI delete form needs a rebase onto master
  `883718e` (owner approval) before it can call
  `FundAttributesRepository.delete`. Do not copy that method
  onto this branch. The small-TER display is on this branch.

## Real stock metrics from Yahoo, TTM snapshot: 2026-11-27, merged

- Pull request #151 was merged by Przemek on 2026-11-27 with
  "Rebase and merge" (`9e114a6` is the master head after it).
- Branch `feat/yahoo-ttm-metrics`, pull request #151, rebased on
  `origin/master` `37675ef` (first cut from `8d8c4ca`).
  Refs #54, Refs #35. Design
  `docs/superpowers/specs/2026-11-27-yahoo-ttm-metrics-design.md`,
  plan `docs/superpowers/plans/2026-11-27-yahoo-ttm-metrics.md`.
  Approach A, chosen by Przemek; built subagent-driven, his choice.
- Done: `POST /api/v1/data-collection/fetch-financial-metrics` is no
  longer a placeholder. It stores Yahoo `info` ratios as one row with
  `period_type="ttm"`, dated by `mostRecentQuarter`, source
  `yahoo_finance` (or `fake`). A refresh in the same quarter replaces
  the values; a row from another source (for example `manual`, any
  case of `ttm`) gives 409 and stays. 404 for an unknown company or
  no data, 400 for a fund, 502 for a provider error.
- Live probe (2026-11-27, needs #144's fix, so run on a temporary
  copy with it): AAPL, PKN.WA, CDR.WA all scored `4 of 4`.
- Tests: the full suite with `-W error::DeprecationWarning` on the
  round-2 fixes gave 2460 passed and 3 failed, the known local ones
  (two 0006 float tests, #122, and the `run_demo` `.env` test, which
  passes in a clean checkout).
- Review round 1 on #151 (code-reviewer, terminal only, on
  `0ef88d7`): 1 Critical (the API guide said P/E and P/B follow
  `updated_at` and left out EV/EBITDA and the cache; "one TTM row per
  company"; base commit and test count), 3 Minor (a huge int failed
  the whole fetch; `.first()` without ORDER BY when two rows match;
  untested error details and `updated_at`). All fixed, with tests
  that fail without the code fixes. Four questions went to Przemek.
- Review round 2 (terminal only, on `f91f263`): 0 Critical,
  0 Important, 2 Minor (journal layout; the 409 detail from an
  unordered query). Both fixed; the lookup orders by id.
- Not done, follow-ups: the `FinancialMetrics` response has no
  `source` field (the score shows each figure's source); a second
  concurrent fetch of a new quarter answers 502; a future
  `mostRecentQuarter` is accepted; history from the statements
  (approach B); ETF typing and fund attributes from Yahoo.
- Active agents: none. Blockers: none (#144 is merged, so real
  fetches work on this branch). This is not approval.
- Next action: Przemek reviews and merges this pull request. Then
  ETF typing and fund attributes from Yahoo.

## Real Yahoo calls failed on a positional timeout: 2026-11-26, merged

- Pull requests #144 (this fix) and #145 (the AGENTS.md usage
  threshold for the Grok bot only) were merged by Przemek on
  2026-11-27 with "Rebase and merge" (`37675ef` is the master head
  after both).
- Branch `fix/yahoo-positional-timeout`, from `origin/master`
  `8d8c4ca`. Refs #54. Przemek's goal (2026-11-26): use the app
  himself on real data as soon as possible. UI work waits for a
  dedicated UI agent; backend work goes first.
- Found by a manual probe with `DATA_COLLECTOR=yahoo` against real
  Yahoo (AAPL, PKN.WA, VWCE.DE): every `fetch-company` was 502.
  `_with_capped_timeout` added `timeout=` as a keyword, but yfinance
  1.7 `YfData.cache_get` passes it by position, so `Ticker.info`
  raised `TypeError: got multiple values for argument 'timeout'`.
  The offline tests only called the wrapped methods with a keyword.
- Done: the wrapper binds the call with `inspect.signature` and
  replaces the timeout wherever it was passed. A new test fails on
  master with the same `TypeError`. After the fix the probe stored
  the three instruments and about 250 daily bars each.
- Gaps the probe showed (not fixed here, the next backend work):
  - `POST /data-collection/fetch-financial-metrics` is still a
    placeholder, so a real stock's score is `0 of 4`.
  - A fetched ETF (VWCE.DE) is stored as `STOCK`, and Yahoo fund
    attributes (TER, AUM) are not collected.
  - The price refresh fetches one year, so `return_3y` is always
    `insufficient_history`; AAPL's `return_1y` was too.
- Tests: the CI command gave 2422 passed and 3 failed, coverage
  97.38%. The failures are local only and fail on master too: the
  two 0006 float tests (#122) and
  `test_run_demo::test_child_process_does_not_inherit_dotenv_database`
  (the ignored `demo/` folder in this checkout). Lint passed.
- Pull request #144. Review round 1 (code-reviewer, terminal only):
  0 Critical, 0 Important, 2 Minor, both fixed (a test on the real
  yfinance `cache_get` chain, a docstring line).
- Pull request #145 (separate): the AGENTS.md usage threshold
  applies to the Grok bot only, Przemek's decision of 2026-11-26.
- Active agents: none. Blockers: none. This is not approval.
- Next action: Przemek reviews #144 and #145. Then the real
  financial metrics from Yahoo.

## Fund-attribute AUM trio on PUT (#139): 2026-11-23, merged

- Pull request #141 was merged by Przemek on 2026-11-27 with
  "Rebase and merge" (`e4a06fb` on master). Closes #139.
- Branch `fix/fund-attributes-aum-partial-139`, from `origin/master`
  `8d8c4ca`.
- Done: `FundAttributesRepository._check_aum` decides by the keys a
  PUT sends. `aum_currency` or `aum_as_of` without `aum` is 400,
  also as `null`. `{"aum": null}` clears all three on an update too;
  before, it kept the currency and the date, which #139 did not
  list. `{"as_of": null}` is 400 too, the rule `create` already had
  (found in review round 2). `docs/api-demo.md` and the PUT
  docstrings state both rules.
- Not done: rows already stored with a broken trio are not repaired.
  The score treats them as no data or `unsupported_currency`.
- Tests: the CI command gave 2426 passed and 2 failed (the local-only
  0006 float tests, #122), coverage 97.40%. Lint passed.
- Not run: PostgreSQL locally (GitHub Actions runs it).
- PR #140 was merged by Przemek on 2026-11-23 (`8d8c4ca`, the same
  tree as `c889ebf`), and its branch was deleted at his request.
- Active agents: none. Blockers: none. This is not approval.
- Review round 1 (code-reviewer, terminal only): 1 Critical, the
  PUT docstrings said omitted fields stay as stored. Fixed.
- Review round 2: 0 Critical, 0 Important, 3 Minor, all fixed, plus
  the `as_of` case it asked about.
- Review round 3 (terminal only, on `01c7117`, 2026-11-25):
  0 Critical, 0 Important, 2 Minor (the `as_of` sentence in
  `docs/api-demo.md` read as if a POST gives 400, but it gives 422;
  this file still listed the AUM question as open), plus "two" for
  four changed Python files in the journal. All fixed.
- Decided by Przemek on 2026-11-25: AUM is a money amount, so the
  `Decimal` rule applies. The `Float` column is pre-existing and is
  not changed here; issue #142 tracks it.
- Next: #142 (AUM as `Decimal`).

## Code Reviewer agent draft (#102): 2026-11-19, merged

- Pull request #138 (branch `feat/code-reviewer-agent-102`) was
  merged by Przemek on 2026-11-19 (`ac23710` on master). Refs #102.
  #102 stays open until Przemek accepts the draft.
- Completed: `.claude/agents/code-reviewer.md`, the `/review-pr`
  skill, `.agents/review/instructions.toml`,
  `scripts/review_instructions.py`, `scripts/pending_review.py`,
  their tests, and the AGENTS.md, REVIEW.md, and HANDOFF.md notes.
  Details are in the 2026-11-19 journal entry.
- Checks: the planted-defect acceptance run found all four defects.
  GitHub Actions passed both jobs on `735d04f` (run 44485683800) and
  on `696a83b` (run 44488391248). The CI command locally on the
  round-2 fixes: 2291 passed, coverage 97.20%; the 3 failures are
  local only (two 0006 SQLite 3.54.1 tests and the ignored `demo/`
  folder in this checkout). The two new test files: 62 passed.
- Round 1 on #138 by the code-reviewer agent: 0 Critical,
  4 Important, 3 Minor, all fixed on this branch:
  - the posted review now keeps `other_locations`, a suggestion
    outside the diff, and earlier-finding statuses;
  - the path rules and REVIEW.md come from a freshly fetched base
    branch;
  - the round rules follow `previous-review.md`, so a rebase keeps
    them;
  - this file and the journal;
  - the marker test uses a literal;
  - the drift test checks each filter against `git ls-files`;
  - `COVERAGE_FILE` keeps `.coverage` out of the worktree.
  Changed file names reach the path-rule script through a file,
  never a command line. A PENDING draft no longer blocks a
  terminal-only rerun. The three score filters are added by #135.
- Round 2 on #138 (`696a83b`): all seven round-1 findings fixed;
  2 Important and 3 Minor new ones, fixed on this branch: finding ids
  in every posted label, earlier rounds read from the review body
  too, thread state from GraphQL `reviewThreads`, the matcher copied
  from the base branch and run with `python -I`, multi-paragraph
  bodies kept inside their list item, these numbers, and Comment as
  the only choice on one's own PR. Only a posted review counts as a
  round.
- PR #135 review (instrument score): 3 Critical, 7 Important,
  3 Minor. Posted as PENDING review 5971406643 on head `d041b1c`,
  with 12 inline comments and the summary. This was the first real
  pending-review post. All findings were fixed on the branch, and
  Przemek had the draft deleted on 2026-11-20 without submitting it,
  because its comments were on the pre-fix head.
- Not done: the head marker after a real submit is still unchecked
  (the #135 draft was deleted, not submitted); no GitHub Actions
  trigger; no thread replies; no CODEOWNERS entry for
  `.agents/review/`.
- PR #131 (fund-attribute forms) conflicts with master and waits
  for the owner's rebase. It was not reviewed.
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Next action: run `/review-pr <N>` on the next pull request, and
  check once that the head marker survives a real submit. Agents do
  not merge.

## Backend instrument score (PR #135, Refs #35): merged 2026-11-20

- Pull request #135 (branch `cursor/instrument-score-s1-90ae`) was
  merged on 2026-11-20 with "Rebase and merge". The agent ran the
  merge on Przemek's explicit instruction (AGENTS.md allows that),
  pinned to the tested head `3f3a402`. The merge put master at
  `4ea0514`, the same tree. GitHub Actions passed both jobs on that
  head (run 44564202972). Refs #35, Refs #136: both stay open. No `/ui` change
  yet. Alembic head is `0011`.
- What the score does now (details in `docs/scoring.md`):
  - A stock has profitability (ROE, net margin), valuation (P/E,
    P/B), balance sheet (debt-to-equity, current ratio), and growth
    (revenue YoY). An ETF and an ETC share cost (TER), size (AUM),
    volatility, and max drawdown, with a weight row per type.
  - Ratios are fractions. Debt-to-equity is a percent, the Yahoo
    unit (`45` is 0.45 times equity; 0 scores 100, 200 scores 0).
    TER is a fraction. The legacy ROE `15.6` would clamp (Refs #136).
  - Freshness from UTC today: 548 days for a statement, 366 days for
    TER and AUM, 92 days for volatility and drawdown. The exact last
    day counts. AUM is dated by `aum_as_of` only.
  - AUM is scored only in EUR or USD (`unsupported_currency`
    otherwise). A price window longer than 458 days is
    `window_too_long`. `period_type` is case-insensitive.
  - A demo instrument keeps `is_synthetic` and the source `demo` on
    every figure, also after an edit. A synthetic fund row on a real
    company marks the score synthetic too.
  - Totals and contributions use exact fractions. The total rounds
    half up. The cents come from a largest-remainder split, never
    negative, tie to the earlier component.
  - Version 1 is the built-in equal set. The first PUT stores
    version 2, each later PUT adds 1, and the answer is the version
    and weights that request wrote.
- Round 1 (review 5971406643 by the code-reviewer agent on
  `d041b1c`, deleted unsubmitted on 2026-11-20): 3 Critical,
  7 Important, 3 Minor. All fixed on 2026-11-19, the Undo steps
  through the PR body edit, plus two of the three Minor findings
  dropped under the cap (`-0.00`, a Content-Length of thousands of
  digits). The third, `alembic upgrade 0010:0011 --sql`, is not
  fixed: `0010` and earlier revisions fail offline the same way.
- Round 2 (a workflow on `20a55ae`: code-reviewer, 34 mutants, five
  adversarial verifiers): round 1 confirmed fixed. New: 1 Critical
  (a re-sent weight set was not written, so a concurrent PUT's
  weights stayed under the new version), 2 Important, and Minor
  findings. All fixed with tests that fail without them.
- Open questions for Przemek: an FX source or a stated conversion
  for other currencies (size is EUR and USD only for now, an
  agent's call); a formula version and a computed time on the
  response (US6.1); keeping old weight versions so a score can be
  recomputed.
- Follow-up: issue #139. A partial fund-attribute update
  `{"aum_as_of": null}` or `{"aum_currency": null}` keeps the AUM
  amount (`FundAttributesRepository._check_aum`, pre-existing). The
  fix is pull request #141.
- Databases: this machine has no `.env` and no PostgreSQL on
  `localhost:5432`, so only the demo file exists. The old
  `demo/investment_demo.db` (built by `create_all` on 2026-10-28,
  without `fund_attributes` or `score_weights`) was rebuilt with the
  `run_demo` reset and the demo-v2 seed; its one watchlist row
  (`DEMO_PL_TECH`) was put back. A copy of the old file is
  `demo/investment_demo.db.bak-2026-11-20`. Revision `0011` was
  checked on a database built by `ac23710` and stamped `0010`:
  upgrade, downgrade one step, and upgrade again. Any other
  Alembic-managed database needs `alembic upgrade head`.
- Tests: the CI command on SQLite 3.54.1 passes except the known
  local-only failures (two 0006 float tests, the ignored `demo/`
  folder). Counts are in the 2026-11-19 journal entry.
- Account usage: this session cannot read the meter.
- Active agents: none. Blockers: none. This is not approval.
- Next action: Przemek decides the open questions above. The score
  page in `/ui` is the next piece of work (#139 is in pull request
  #141).

## Test debt from the cleanup pull request (#133): 2026-11-18

- Branch `cursor/test-debt-133-8a99`, from `origin/master`
  `1db5931`. One pull request to master. Refs #133. The agent
  does not merge. No Alembic revision. No live market data.
  Production code was not edited.
- Completed: the fund-attribute DELETE `OperationalError`
  response is the plain text `Internal Server Error`. The
  driver text `database is locked` is not in the body. The
  repository test checks that `OperationalError` propagates,
  that it is not `FundAttributesDeleteError`, and that a
  fresh session still has the row. It does not count
  `session.rollback()` calls. The unhandled panel error is
  checked with `HX-Request` and without it, for note add and
  for a thesis status change. Both are the plain 500 and
  have no `HX-Research-Panel` marker.
- Decision: CR: no rollback in delete; get_db close handles
  it. `FundAttributesRepository.delete` still catches only
  `IntegrityError`. Production code was not edited.
- Already on master, checked again, no new test:
  `test_delete_result_ignores_the_demo_seed_header` fails
  when DELETE reads `request.scope["headers"]` and raises
  (`8d0636d`, master `35338dd`, same tree).
  `test_unhandled_research_error_has_no_panel_marker` with
  `thesis-status` fails when `_set_thesis_status` catches
  `Exception` (`d8c3d3e`, master `1db5931`, same tree).
  `_set_thesis_status` still catches only
  `ResearchStorageError`.
- Tests: no `.env`. `DATABASE_URL` was not set. SQLite
  3.45.1, CI command: 2232 passed, 256 deselected, coverage
  97.19%. PostgreSQL 16.15, `REQUIRE_POSTGRES=1`, DSN
  `postgresql://postgres:postgres@127.0.0.1:5432/investment_test`:
  256 passed, 2232 deselected. black, isort, and flake8
  passed on the Python files this change touches. No live
  market-data calls. Each new assertion was failed by its
  mutant, then the mutant was reverted. The CR follow-up
  drops the rollback-call assert and re-ran the same
  commands with the same counts.
- Account usage: this session cannot read the meter. No
  percentage is recorded. No reset was redeemed.
- Active agents: none. Blockers: none. This note is not
  approval and not a merge.
- Next action: GitHub Actions on this head, both jobs. Then
  Code Reviewer review, QA check, and CR merges under
  Przemek's standing merge rule (non-critical change). The
  run id is not written here, because this file is part of
  the commit the run tests.

## QA follow-up on the cleanup pull request: 2026-11-18

- Branch `cursor/cleanup-104-130-nits-f107`. Pull request #132.
  New commits on top of `cd513ec`. No rebase, no force-push,
  no pull-request edit. Refs #104. Refs #28. The agent does
  not merge. No live market data.
- QA of `cd513ec` did not approve. Completed: tests pin
  `OperationalError` on fund-attribute delete (repository and
  HTTP 500, row kept). The demo-seed header does not change
  the delete result. The unhandled panel error is parametrized
  over note add and thesis status. `_set_thesis_status`
  already catches only `ResearchStorageError`, so
  `research_forms.py` was not edited. Delete production code
  was not edited.
- Tests: no `.env`. `DATABASE_URL` was not set. SQLite
  3.45.1, CI command: 2230 passed, 256 deselected, coverage
  97.19%. PostgreSQL 16.15, `REQUIRE_POSTGRES=1`, DSN
  `postgresql://postgres:postgres@127.0.0.1:5432/investment_test`:
  256 passed, 2230 deselected. black, isort, and flake8
  passed on the Python files this change touches. No live
  market-data calls.
- Account usage: this session cannot read the meter. No
  percentage is recorded. No reset was redeemed.
- Active agents: none. Blockers: none. This note is not
  approval and not a merge.
- Next action: GitHub Actions on this head, both jobs. Then
  Code Reviewer review, QA check, and CR merges under
  Przemek's standing merge rule (non-critical change). The
  run id is not written here, because this file is part of
  the commit the run tests.

## Review nits from #104 and the attribute delete (#28): 2026-11-12

- Branch `cursor/cleanup-104-130-nits-f107`, from `origin/master`
  `883718e` (pull request #130, merged). One pull request to
  master. Refs #104. Refs #28. Does not finish either issue.
  The agent does not merge. No Alembic revision. No live market
  data. The detail template and `app/ui/templating.py` were not
  edited.
- Completed: a failed thesis status change carries
  `HX-Research-Panel: 1`. An unhandled note-add error is the
  plain 500 and has no marker. The helpers in `tests/ui_html.py`
  are public. `docs/api-demo.md` and `README.md` record DELETE
  400 `{"detail": "Delete failed due to constraint violation"}`.
  The HTTP 400 test flushes, raises `IntegrityError`, and checks
  that the same id and issuer remain. The happy path reads
  `ThesisDB`. DELETE does not read `X-IAC-Demo-Seed`.
- `FundAttributesRepository.delete` rolls back `IntegrityError`
  and raises `FundAttributesDeleteError` (`RuntimeError`) after
  the handler. The route returns the fixed sentence and does not
  copy `str(error)`. A different `ValueError` is a plain 500.
  `OperationalError` is not caught, the same as create and
  update. `get_db` closes the session.
- Tests: no `.env`. `DATABASE_URL` was not set. SQLite 3.45.1,
  CI command: 2226 passed, 256 deselected, coverage 97.19%.
  PostgreSQL 16.15, `REQUIRE_POSTGRES=1`, DSN
  `postgresql://postgres:postgres@127.0.0.1:5432/investment_test`:
  256 passed, 2226 deselected. black, isort, and flake8 passed
  on the Python files this change touches. No live market-data
  calls. Each new guard was failed by its mutant, then the
  mutant was reverted. The journal lists those failures.
- Account usage: this session cannot read the meter. No
  percentage is recorded. No reset was redeemed.
- Active agents: none. Blockers: none. This note is not
  approval and not a merge.
- Next action: GitHub Actions on this head, both jobs. Then
  Przemek reviews. Do not merge. The run id is not written
  here, because this file is part of the commit the run tests.

## Delete fund attributes, QA gaps (#28): 2026-11-12

- Branch `cursor/delete-fund-attributes-ddd6`. Pull request
  #130. Refs #28. Does not close #28. The agent does not
  merge. No amend, no force-push, no rebase. No Alembic
  revision. No live market data.
- `7bf3e3f` had green GitHub Actions run 43249146900 (SQLite
  and PostgreSQL both success). QA did not approve: 4 of 16
  mutants survived. Those four are now killed by tests, and
  each was re-applied and reverted after the matching test
  failed.
- Completed: a keeper and a victim. Delete removes only the
  victim. An ETC happy path is 204, and an ETC with no row
  is 404 `Fund attributes not found`. DELETE does not call
  `request_is_demo_seed`. A failed commit rolls back and
  raises `ValueError`; the route returns 400
  `Delete failed due to constraint violation`. The stock PUT
  detail is the exact ETF/ETC sentence. The HTTP happy path
  keeps the thesis as well as the note and the prices.
- Tests: no `.env`. `DATABASE_URL` was not set. SQLite
  3.45.1, CI command: 2222 passed, 256 deselected, coverage
  97.19%. PostgreSQL 16.15, `REQUIRE_POSTGRES=1`, DSN
  `postgresql://postgres:postgres@127.0.0.1:5432/investment_test`:
  256 passed, 2222 deselected. black, isort, and flake8
  passed on the Python files this change touches. No live
  market-data calls.
- Account usage: this session cannot read the meter. No
  percentage is recorded. No reset was redeemed.
- Active agents: none. Blockers: none. This note is not
  approval and not a merge.
- Next action: GitHub Actions on this head, both jobs. Then
  Przemek reviews. Do not merge. The run id is not written
  here, because this file is part of the commit the run tests.

## Delete fund attributes (#28): 2026-11-12

- Branch `cursor/delete-fund-attributes-ddd6`, from `origin/master`
  `1dab8fc` (pull request #128, merged 2026-11-12T15:20:38Z).
  One pull request to master. Refs #28. Does not close #28.
  The agent does not merge. No Alembic revision. Head stays
  `0010`. No live market data. No UI change.
- Completed: `FundAttributesRepository.delete` removes the one
  attribute row. The company, its prices, and its notes stay.
  A missing company raises `CompanyNotFoundError`. No row,
  including a stock, returns False and deletes nothing.
  `DELETE /api/v1/instruments/{instrument_id}/fund-attributes`
  is 204 with an empty body. A missing instrument is 404
  `{"detail": "Instrument not found"}`. No attribute row is
  404 `{"detail": "Fund attributes not found"}`. An id of 0,
  a negative id, or `2**63` is 422, the same body as GET on
  that id. The demo-seed header is not read. A valid token
  still deletes. A 64-character Latin-1 header is 204, not
  500. The header stays honored on creates only.
- Decision: a stock is 404, not 400. POST and PUT reject a
  stock because a stock must not gain a row. DELETE of a
  missing row is the same 404 an ETF with no row already
  gets. The table does not need a new revision: the row is
  removed with the existing foreign key, and that key
  cascades from the company to the attributes, not the
  reverse.
- Tests: no `.env`. `DATABASE_URL` was not set. SQLite 3.45.1,
  CI command: 2216 passed, 256 deselected, coverage 97.19%.
  PostgreSQL 16.15, `REQUIRE_POSTGRES=1`, DSN
  `postgresql://postgres:postgres@127.0.0.1:5432/investment_test`:
  256 passed, 2216 deselected. black, isort, and flake8 passed
  on the Python files this change touches. No live market-data
  calls.
- Account usage: this session cannot read the meter. No
  percentage is recorded. No reset was redeemed.
- Active agents: none. Blockers: none. This note is not
  approval and not a merge.
- Next action at `7bf3e3f`: GitHub Actions run 43249146900
  succeeded for both jobs. QA then found four surviving
  mutants. That follow-up is the section above. This
  section is the record of the first delete commit.

## ETF and ETC attributes and price metrics (#28): 2026-11-10

- Branch `cursor/etf-etc-attributes-28-0a55`, from `origin/master`
  `b4873c6`. One pull request to master. Refs #28. The agent
  does not merge. `0009` was not edited. No live market data.
- Completed: Alembic `0010` revises `0009` and is the only head.
  `fund_attributes` is one row per company. Fact columns are
  nullable. TER and AUM have no server default and a CHECK that
  rejects a negative number. `is_synthetic` defaults to false.
  `source` defaults to `manual` and has no CHECK. Upgrade does
  not invent values. Downgrade drops the table and keeps
  companies, metrics, and price bars. A second upgrade starts
  empty. A `create_all` database can upgrade without creating
  the table twice.
- Price metrics are computed from the default stored series:
  1-year and 3-year total price return, annualized volatility,
  and maximum drawdown. The formulas are in `app/price_metrics.py`.
  A short series is null with `insufficient_history`. No usable
  close is `no_prices`. Each value carries the series source
  and the as-of date.
- Public JSON cannot set `source` or `is_synthetic`. Creates
  and updates are `manual`. The demo-seed header is the only
  HTTP way to store `demo`, and only on create. An update
  records `manual` and leaves the flag. A stock is rejected.
- The fixture label is `demo`. `DEMO_ETF_GPW` has a null TER.
  Price bars in the fixture still use source `[IAC-DEMO-V2]`.
  The fake collector's provenance source stays `fake`.
- The `/ui` detail page shows the attributes and the four
  metrics. Edit forms are not in this slice. Yahoo still does
  not implement `FundAttributes`.
- GET `/api/v1/instruments/{id}` for a stock is 200.
  `fund_attributes` is null and every price metric is
  `no_prices`. Only POST and PUT of attributes on a stock
  are 400.
- A public update of a demo attribute row records
  `source=manual` and leaves `is_synthetic` true. The
  demo-seed header on that update does the same. The flag
  stays because the row was created as demo data. The header
  is not applied to updates.
- Tests: no `.env`. `DATABASE_URL` was not the personal
  database. SQLite 3.45.1, CI command: 2181 passed, 254
  deselected, coverage 97.16%. PostgreSQL 16.15,
  `REQUIRE_POSTGRES=1`, DSN
  `postgresql://postgres:postgres@127.0.0.1:5432/investment_test`:
  254 passed, 2181 deselected. black, isort, and flake8 passed
  on the Python files this change touches. The detail HTML was
  checked through the test client. A desktop browser was not
  driven.
- Account usage: this session cannot read the meter. No
  percentage is recorded. No reset was redeemed.
- Active agents: none. Blockers: none for the slice. This note
  is not approval and not a merge.
- Security review of `31a7ce5` was approve with nits. The
  fixes are on this branch, each behind a failing test:
  instrument ids use `ItemId` so `2**63` is 422; TER is a
  fraction capped at 1 (the page shows percent) and AUM is
  capped at `1e15`; the five text fields use `clean_text`; a
  blank price source is `no_prices` instead of 500; the seeder
  comment names fund-attribute creates.
- Tests after those fixes: no `.env`. SQLite 3.45.1, CI
  command: 2194 passed, 254 deselected, coverage 97.07%.
  PostgreSQL 16.15, `REQUIRE_POSTGRES=1`: 254 passed, 2194
  deselected. black, isort, and flake8 passed on the Python
  files this change touches. No live market-data calls.
- Tests for the QA gaps: SQLite 3.45.1, CI command: 2206
  passed, 254 deselected, coverage 97.18%. PostgreSQL 16.15,
  `REQUIRE_POSTGRES=1`: 254 passed, 2206 deselected. black,
  isort, and flake8 passed on the Python files this change
  touches. No live market-data calls.
- QA test-gap round: the surviving mutants are locked by
  tests (three-close volatility, TER and AUM caps including
  the repository guard, text `max_length`, and `ter=0` /
  `aum=0` on both databases). The anchor has no maximum gap;
  that behavior is tested and described, not changed.
- Next action at the time of that pin: GitHub Actions, then
  QA, code review, and the security check. Pull request #128
  merged at `1dab8fc`. This section is the record of that
  slice, not the current task. The current task is the fund
  attribute forms section above.

## Provenance slice A (#105): 2026-11-08

- Branch `cursor/provenance-slice-a-105-e700`, from `origin/master`
  `e71c098`. Pull request #127. Refs #105. Does not close #105
  until Przemek says the slice is accepted, and does not close #34.
  #28 and revision `0010` are not in this branch. Price bars were
  not edited. Pull request #126 is merged on master at `ce77aa2`.
  This branch did not edit that pull request. No other #105 branch,
  pull request, or cloud run was open when this work started.
- Completed: Alembic `0009` revises `0008` and is the only head.
  `companies.is_synthetic` is boolean, NOT NULL, server default
  false. `companies.source` and `financial_metrics.source` are
  `String(64)`, NOT NULL, server default `manual`. No CHECK.
  Allowed values `manual`, `demo`, and `fixture` are checked by
  `require_record_source` next to the models (the TTM metrics branch
  added `yahoo_finance` and `fake` on 2026-11-27). Backfill marks a
  description that starts with `[IAC-DEMO-` as synthetic `demo`.
  Other companies stay false and `manual`. A metric is `demo`
  only when its company is synthetic. Upgrade and downgrade were
  run on SQLite 3.45.1 and PostgreSQL 16.15. Downgrade drops the
  columns in place. A batch copy of `companies` was not used,
  because that copy drops the table while other tables point at
  it. Child metric rows stayed.
- Owner decision, 2026-11-08 17:56, not in the GitHub issue body:
  one label `demo` replaces `demo-v1` and `demo-v2`. The runtime
  badge reads `is_synthetic`. It does not parse the description.
  Templates were not edited. A manual company does not show the
  word `manual`.
- UI and API creates store `manual` and `is_synthetic` false,
  even when the description starts with the old prefix or the
  JSON body names `source` or `is_synthetic`. An update stores
  `manual` and does not change the flag. The header is ignored
  on update. Both `seed_demo` modes set true and `demo`.
  `--database-url` passes the repository arguments.
  `--base-url` sends `X-IAC-Demo-Seed`, the HMAC of the shared
  `SECRET_KEY`. The server honors it only when
  `DEMO_SEED_ENABLED` is true and the peer is `127.0.0.1` or
  `::1`. The flag defaults to false. A value that is not 64
  lowercase hex characters stays manual and does not return 500.
  Uvicorn's default proxy headers rewrite `request.client` from
  `X-Forwarded-For` when the TCP peer is `127.0.0.1`. `::1` is
  not in that default allow list. A remote forwarded address
  stays manual. The migration file was not changed for this.
- A `fetch-company` update uses the same repository update, so it
  records `manual` and leaves `is_synthetic` as stored.
- Plan: `docs/superpowers/plans/2026-11-08-provenance-slice-a.md`.
- Tests: no `.env`. `DATABASE_URL` was not the personal
  database. SQLite CI command on 3.45.1 after the QA gaps:
  2141 passed, 253 deselected, coverage 97.00%. PostgreSQL
  16.15, `REQUIRE_POSTGRES=1`, DSN
  `postgresql://postgres:postgres@127.0.0.1:5432/investment_test`:
  253 passed, 2141 deselected. black, isort, and flake8 passed
  on the Python files this change touches. No live market-data
  calls. The `/ui` pages were not driven in a browser.
  QA of `6052f4c` was not an approval. The added tests kill
  an update that keeps `source=demo`, a fetch-company update
  that clears `is_synthetic`, trust of `X-Forwarded-For` or
  `X-Real-IP` from a remote peer, and dropping `::1`. Each
  mutant was reverted after the matching test failed.
- Account usage: this session cannot read the meter. The
  coordinator reported 68.4% at dispatch, under the 80% stop.
  No reset was redeemed. No full security audit was started.
- Active agents: none on this branch. Blockers: none for the
  slice. Normal QA, security review, and code review are still
  required. This note is not approval and not a merge.
- Rebase: Przemek approved, on 2026-11-09 at 21:02
  Europe/Warsaw, rebasing this branch onto `ce77aa2` and
  `git push --force-with-lease`. No merge. The conflicts were
  `docs/development-journal.md` and `docs/work-state.md`. Both
  top sections stayed. No application, test, or migration file
  conflicted. Revision `0009` was not edited.
- Security review of `0a76960` was approve with nits. Those
  nits are committed. QA of `6052f4c` was not an approval.
  The gap tests are the following commit. The agent does not
  merge.
- Next action: none on this slice. Pull request #127 is merged
  on master at `b4873c6`. GitHub Actions run 42793437467 succeeded
  on that commit (SQLite and PostgreSQL). This section is the
  record. The next implementation is issue #28.

## Current owner name (Przemek): 2026-11-08

- Branch `cursor/current-owner-przemek-a83c`, from `origin/master`
  `e71c098cbc965822db23b50aa565ee095b0bf671`. Documentation only.
  No merge. No open pull request for this rename existed before
  this branch.
- The current owner is Przemek (also called Przemo). Living owner
  lines now say Przemek. Dated journal entries, the 2026-10-08
  requirements quote, and the dated "Raul decided" lines stay as
  written. The journal entry for this date lists them.
- Live GitHub, checked before the edit, after `git fetch origin
  master`. `origin/master` is `e71c098`. Merged pull requests:
  #124 at that SHA (2026-11-08T13:05:32Z; both Actions jobs
  succeeded), #125 at `0ce9703` (2026-11-07T21:02:44Z), #104 at
  `c051ced` (2026-11-07T07:30:50Z), #107 at `25af8c2`
  (2026-11-07T07:16:56Z), #106 at `da6579d` (2026-10-30T14:17:21Z),
  and #108 at `67974c5` (2026-10-30T10:19:46Z). Issue #86 is
  closed since 2026-10-30T14:17:23Z. GitHub's closing reference
  is pull request #106. Issues #33, #95, #102, #28, #34, and
  #105 are open. No open pull requests. The Snyk draft was not
  posted.
- Issue #105 was read. It is not implemented, and this branch
  does not add requirements to it. Accepted scope is the issue
  body: `companies.is_synthetic`, `companies.source`, and
  `financial_metrics.source`; Alembic `0009` revising `0008`;
  the backfill from the `[IAC-DEMO-` description prefix; UI and
  API writes set `source` to `manual` and do not change
  `is_synthetic`; seeders and demo fixtures set the synthetic
  flag and `source` to `demo`. Templates stay unchanged. It does
  not close #34. #28 is not a blocker. The tree has no revision
  `0009` or `0010`. The Alembic head is `0008`.
- Not started: that migration and the repository changes the
  issue describes. The issue says the badge helper stops reading
  the description prefix, and it also says the current badges
  still render the same. It does not say how the `demo-v1` /
  `demo-v2` label is kept. Allowed `source` values in the issue
  are `manual`, `demo`, and `fixture`.
- Tests: documentation only against `e71c098`. Pytest was not
  run. No live market-data calls. The only workflow is pytest on
  SQLite and PostgreSQL. It does not lint docs. QA, code review,
  and the security check of this branch are not done. The agent
  does not merge.
- Active agents: none besides this session. Blockers: none. The
  owner reported account usage at 61.8% before this change. Stop
  threshold 80%. This session did not read the meter.
- Next action: the owner reviews this branch. Do not merge. After
  it is on master, the next implementation step is Alembic `0009`
  with `down_revision = "0008"`, as issue #105 states. Do not
  start that in this branch. This section is the record of the
  rename. The current task is the #105 section above.


## REVIEW.md for pull request reviews (#124): 2026-11-08

- Branch `docs/review-md`, rebased onto `origin/master`
  `0ce9703`. The tip before this rebase was `f010cfb`. Refs #102.
  #102 stays open. No second pull request was opened for that
  rebase. The agent does not merge. Pull request #125 is merged
  at `0ce9703`. Pull request #124 later merged at `e71c098`
  (2026-11-08T13:05:32Z). Both Actions jobs on that commit
  succeeded. This section is the record, not the current task.
- Completed: `REVIEW.md` at the repository root, and one line in
  `AGENTS.md` Quality Gates. The security-audit section from
  #125 stays in `AGENTS.md`. The review fixes stayed. An action
  needs a path that works without JavaScript. A create POST must
  not repeat itself. `data-plain-fallback` posts the form again
  after an HTMX error, so a create must not carry it, and a
  missing one is not this failure. Severity is Critical,
  Important, and Minor. A minor never blocks. Pre-existing is a
  mark, not a fourth label.
- Rebase conflicts were the journal and work-state. Both sides
  stayed. Skill files, `skills-lock.json`, and the symlink were
  not changed. `computedHash` was not recomputed.
- Not in this pull request: the Code Reviewer agent file that
  #102 asks for (`.claude/agents/code-reviewer.md`), and the
  HANDOFF note for when to run it. #102 stays open.
- Tests: docs only against `0ce9703`. Pytest was not run
  locally. No live market-data calls. GitHub Actions runs both
  jobs on this head.
- Active agents: none. Blockers: none. The owner reported
  account usage at 55.1% before this rebase. Stop threshold 80%.
- Next action at the time of that rebase: GitHub Actions on
  that head, then the owner's review. The agent does not merge.
  GitHub now records #124 as merged at `e71c098`. This section
  is the record, not the current task. The current task is the
  #105 section above.

## Security-audit skill (#125): 2026-11-07, rebased

- Branch `chore/security-audit-skill`, rebased onto
  `origin/master` `c051ced1d909278cb2c0aee897e9c72e1e909ef1`.
  The owner approved this history rewrite on 2026-11-07 at
  21:40 Europe/Warsaw, including `git push --force-with-lease`.
  No merge. The published tip before the rebase was
  `46ca45e5e62fbe0027ea12082b42804bbc27a8c8`.
- Conflicts were the journal on the skill commit and the
  work-state on the Snyk-note commit. Both sides stayed. This
  section is the #125 note. The sections below started as the
  `c051ced` text. This branch already recorded #104 and #107 as
  merged, and that record stayed. The branch's older
  `da6579d` snapshot was not copied over them. Skill files,
  `skills-lock.json`, and the symlink were not changed.
  `computedHash` was not recomputed and is not claimed to match
  the tree.
- Code review of `46ca45e` approved that docs delta only. That
  is not integration approval and not merge approval. The Snyk
  draft stays outside the repository, pending the owner's
  decision. It was not posted. #124 was not edited.
- Tests: no `.env`. `DATABASE_URL` and `SECRET_KEY` unset. CI
  pytest command on local SQLite 3.45.1: 2060 passed, 252
  deselected, coverage 97.00%. Personal-path `git grep` exited
  1 with no matches. Validator self-tests: 65 pass, 0 fail.
  No local PostgreSQL, so integration tests were not run here.
  No live market-data calls. Fresh GitHub Actions on the pushed
  head are still the SQLite and PostgreSQL CI record.
- Account usage: the owner reported 45.5% at the start of this
  rebase, gate 80%. This session did not read the meter.
- Active agents: none on #124 in this session. Blocker for the
  rebase: none. Merge is not approved.
- #125 is merged at `0ce9703`. Do not post the Snyk draft.
  #104 and #107 are merged. They are not the next action.
  #124 later merged at `e71c098`. The current task is the #105
  section at the top.

## Notes and theses (#33): 2026-10-30, PR #104 merged

- Branch was `feat/notes-theses-33`, rebased onto `origin/master`
  `25af8c2` (#107 is on master). Pull request #104 merged on
  2026-11-07 at `c051ced`. The rebase conflicts were only in
  `docs/work-state.md` and `docs/development-journal.md`. Both
  sides stayed. Thesis labels and the N1/N2 panel fixes stayed.
  The head before the review fixes below was `43fb9c8`; both
  GitHub Actions jobs (SQLite and PostgreSQL) succeeded on it.
- Design: `docs/superpowers/specs/2026-10-28-notes-theses-design.md`.
  Plan: `docs/superpowers/plans/2026-10-28-notes-theses.md`, 10 tasks,
  run with subagent-driven development. The per-task ledger (rulings,
  deferred review findings, status) is the git-ignored
  `.superpowers/sdd/2026-10-28-notes-theses/progress.md`.
- Completed, each task reviewed: Tasks 1 to 9, and Task 10 in
  `d74ba7f` and `7c5f99b` (the rebase onto `da6579d` rewrote the
  earlier SHAs; `git log` has the current ones):
  - Task 1: `theses.closed_at` (revision `0008`);
  - Task 2: startup refuses a `theses` table without `closed_at` and
    names the Alembic commands;
  - Task 3: a failed note or thesis insert is `ResearchStorageError`;
  - Task 4: the JSON API under `/api/v1/instruments/{id}/notes` and
    `/theses`;
  - Task 5: note and thesis times in Polish time (`Europe/Warsaw`);
  - Task 6: HTMX swaps a 422, marked links fall back to a plain
    request, and a stale `autofocus` is cleared;
  - Task 7: the sticky-note button and the read-only panel on
    `/ui/instruments/{id}`;
  - Task 8: add, edit, and delete notes in the panel;
  - Task 9: add, edit, close, reopen, and delete theses in the panel;
  - Task 10: the company delete warning names notes and theses, two
    persistence tests, the EN "Close thesis" label, the new-thesis
    "Anuluj" link lands on the panel without JavaScript, the docs, and
    the Chrome check on the demo.
- The final whole-branch review (four lenses, 2026-10-30) said "With
  fixes": no Critical or Important finding, and five Minor fixes
  before the pull request. The fix wave made them in five commits
  (SHAs after the rebase onto `da6579d`):
  - F1 `0f332fc`: "Anuluj" for a note or thesis deleted in another
    tab now puts the focus on the panel heading, not on the page;
  - F5 `fb14390`: "Najwyżej 10 000 znaków." keeps a no-break space
    between 10 and 000;
  - F2 `ea850a8`: a test pins that a thesis update with the stored
    texts still moves `updated_at`;
  - F3 `7cf0f4e`: docstrings and `docs/api-demo.md` that contradicted
    the code;
  - F4 `f17bb4b`: this file and the journal.
- Code review on #104, fixed on this branch (frontend only):
  - M1 `0dc4bff`: the note add and the new-thesis post are not
    repeated after a failed HTMX request. A storage 500 swaps into
    `#research` only when it carries `HX-Research-Panel: 1`;
  - L4 `94e6c33`: each text-validation code has its own panel
    message;
  - nits `3e1976a`: `dir="auto"` on user text, the shared UI
    helpers are public, and the HTMX list keeps its catch-all.
- Incomplete: filing FU1 to FU7 (FU5 is done for the panel; the
  company name still uses `error.invalid`). GitHub Actions on
  this review-fix head follows the push.
- Tests: CI command on local SQLite 3.45.1 after the rebase onto
  `25af8c2`: 2060 passed, 252 deselected, coverage 97.00%. This
  SQLite is 3.45.1, so the two `0006` float boundary tests passed
  (they fail on SQLite 3.54). No local `demo/` directory, so the
  `run_demo` dotenv test passed. No local PostgreSQL. No live
  market-data calls. black, isort, and flake8 passed on the Python
  files this branch changes. Master's older API files still fail
  isort and flake8; they were not edited.
- Proposed follow-up issues, not filed yet. Filing publishes outside
  this repository, so it waits for the owner's approval:
  - FU1, required by the Task 8 ruling: stop SQLite from reusing
    deleted row ids, so a stale form cannot edit or delete a newer
    note, thesis or company (`AUTOINCREMENT` plus one migration, or a
    row token on forms that can go stale).
  - FU2, required by the Task 9 ruling: in `ui.js`, focus the clicked
    control before an HTMX request, so the id restore works after a
    mouse click in Safari and Firefox. Until then, after a mouse close
    or reopen in those browsers on macOS, the focus is expected to
    fall to the page (expected from those browsers' click-focus
    behaviour; not driven, only Chrome was).
  - FU3: serve `ui.css` and `ui.js` with `Cache-Control` or versioned
    file names, so a cached copy does not hide an update.
  - FU4: tighten the `alembic stamp` advice for old `create_all`
    databases: the `0002` and `0004` docstrings, the "before
    2026-10-21 19:35" sentence, and a database stamped `0008` without
    `closed_at`.
  - FU5: done for notes and theses (L4 above). The company name
    form still says "Ta wartość jest nieprawidłowa." for a control
    character, a bidi character, or a surrogate.
  - FU6: let Cmd, Ctrl or Shift-click on panel links open a new tab
    instead of swapping in place.
  - FU7: fail the SQLite CI job when node is missing
    (`REQUIRE_NODE=1`), instead of skipping `tests/test_ui_js.py`, and
    say so in the README.
- Stop reason at merge: the #104 review fixes landed with that
  pull request. Filing the follow-ups still waits for the owner.
- Active agents: none. The Developer who was going to update the
  stale docs is paused; those doc fixes are in this section.
  Blockers: none. Account usage was not available in this session.
- Done on master at `c051ced`. This section is the record of that
  work, not the current task. Do not file FU1 to FU7 until the
  owner asks.

## Price-bar repository follow-ups (#95): 2026-10-30

- Branch was `cursor/price-bar-followups-95-ce0a`. Pull request
  #107 merged on 2026-11-07 at `25af8c2`. **Refs #95**. Item 1
  is deferred, so #95 stays open. No Alembic revision; head stays
  `0007`. `app/ui`,
  `templates/`, and `static/` were not edited. PR #104 was not
  touched. #106 and #108 are merged.
- PR #108 is merged on that master. It added
  `PriceBarRepository.recent_closes_for`,
  `WatchlistRepository.list_items(with_company=True)`, and a
  scoped ignore of the `uq_companies_ticker` reflection
  SAWarning (`upgrade_head_over_create_all`). This branch keeps
  those and the price-bar follow-ups. `_pick_default` is the one
  tie rule for `_default_source` and `_default_sources_for`.
  The batch path is locked with a stand-in whose SQL order
  would pick `[IAC-DEMO-V2]`; `recent_closes_for` still
  returns `fake`. Rendered HTML is unchanged.
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
    `remember_skip`. The update is under one `threading.Lock`,
    so a full dict cannot make two threads pop the same oldest id.
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
  integration suite after the rebase and `_pick_default`:
  233 passed, 1899 deselected. SQLite CI command on this head:
  1899 passed, 233 deselected, coverage 96.46%. No live
  market-data calls. black, isort, and flake8 passed on
  the changed Python files. Mutation checks, each reverted:
  cap 1025 fails `assert 1025 == 1024`; cap 1023 fails
  `assert 1023 == 1024`; `bar_count=len(payload)` fails
  `assert 2 == 1`; `_default_source` without Python `max`
  returns `[IAC-DEMO-V2]` instead of `fake`.
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Done on master at `25af8c2`. #95 stays open until skipped-bar
  visibility (#93) is done. This section is the record, not the
  current task.

## Company name on `clean_text` (#86 remainder, #106 merged)

- Merged in #106 at `da6579d`. Branch was
  `cursor/ui-company-name-clean-text-86`, rebased onto
  `67974c5`. Refs #86. #86 is closed (completed) since
  2026-10-30. GitHub records #106 as the closing reference.
  The remainder under Open work elsewhere was written while
  the issue was still treated as open.
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
  #86 is closed (completed) since 2026-10-30T14:17:23Z.
  GitHub's closing reference for #86 is pull request #106.
  The remainder written while the issue was treated as open:
  when the ticker and the ISIN are both duplicates, report both;
  `watchlist_stale_price_days` still has no `ge=1` check.
  Stripping Cf characters at the edges stays undone on purpose:
  a format character beside a letter is kept, including at an
  edge.
- #108 is merged. `recent_closes_for` and
  `list_items(with_company=True)` are on master. The
  `uq_companies_ticker` reflection warning is a scoped ignore,
  not an open fix.
- #107 merged at `25af8c2`. Refs #95. Item 1 stays deferred.
- #33: the notes and theses tables, repositories, API, and `/ui`
  panel are on master. Pull request #104 merged at `c051ced`.
- #32: the watchlist backend, the `/ui` page, and the batch read
  (#108) are on master. #96 merged as PR #101 on 2026-10-28.
  Named lists are #99. The on-demand summary is #100.
- #98 review nits still open (see the section above): truncated
  422 keys in `app/core/validation.py`, copying `exc.errors()`
  before editing, docs for surrogate keys and the watchlist
  `too_long` gate, and a 201 test for an extra surrogate key.
- #102 stays open. `REVIEW.md` is on master (pull request #124
  merged at `e71c098`). The Code Reviewer agent file is still
  not committed.
- #103: comments on buy and sell transactions, deferred until #57
  brings transactions.
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
- #28: this branch adds the attribute table, the price-derived
  metrics, the detail API, and the read-only detail section.
  Edit forms are still later. Yahoo still does not implement
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
- #95 stays open. Items 2–5 are on master with #107. Item 1
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
