# Current Work State

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
  `None`. Booleans are not treated as numbers, and total assets of
  zero is `None`. The mapping never reads `totalDebtPerShare` and
  makes no extra provider call. No other Yahoo field changed.
- Incomplete: the queue in the next-action line is still open.
  Alembic (#8) and the PostgreSQL harness (#9) stay later.
- Tests: no `.env`, `DATABASE_URL` unset, the CI command
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 838 passed in 15.33s, no warnings summary, TOTAL 92% (exact
  92.70%). On `6a7f533`, the two strict xfails were `2 xfailed`
  (both `AssertionError` under `--runxfail`). On `a06ca28` the
  further behaviour tests were `8 failed` at assertion level. The
  404/400 pin already passed on that commit.
- Active agents: none.
- Blockers: none.
- Next action: #11, the security/deps part. That is the FastAPI and
  Starlette CVE upgrade, `requests`, `python-dotenv`, `black`,
  `pytest`, removing unused pins, `yfinance>=1.7`, and a lock file
  with hashes. On 2026-10-08 the Project Manager moved this
  security/deps part ahead of the demo after the Security Engineer's
  review found CVEs: `fastapi==0.104.1` forces `starlette==0.27.0`
  (CVE-2024-24762, CVE-2024-47874, CVE-2025-54121), and
  `requests==2.31.0` is also affected. This overrides
  `docs/product-requirements.md` around line 254, which still lists
  #11 after the demo. That requirements file is unchanged. After #11
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

- Branch `fix/startup-lifespan-cors`, worktree `/private/tmp/investment-metric-updates`.
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
  `fix/json-overflow-validation` in `/private/tmp/investment-metric-updates`.
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
  `/private/tmp/investment-metric-updates` worktree. Start usage60% five-hour.
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
- Branch `test/financial-metric-updates`, `/private/tmp/investment-metric-updates`.
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
  into `/private/tmp/investment-pr-delivery` for the user-requested commit/push/PR.
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
- Current branch: `feature/reusable-demo-fixtures`, based on demo documentation commit `83940ea`. Tooling worktree: `/private/tmp/investment-demo-fixtures`. Running application remains in `/private/tmp/investment-api-demo`; no restart needed for HTTP-based seeding.
- Primary repo remains `/Users/przemkowy/IdeaProjects/Investment-AI-Companion`; its `master` and untracked `.python-version` are untouched.
- Demo: `http://127.0.0.1:8081/docs`, API on port8081 loopback only, no authentication. Never expose publicly.
- PostgreSQL14.19: fresh cluster `/private/tmp/iac-demo.h7TbGw/data`, private socket directory `/private/tmp/iac-demo.h7TbGw`, port15432, no TCP listener, role `demo`, database `investment_demo`.
- API runs detached with PID in `/private/tmp/iac-demo.h7TbGw/api.pid`, log `api.log`; database log `postgres.log` in the same directory. These are intentional demo services, not unfinished test processes. Stop/restart commands are in [the demo guide](api-demo.md).
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
