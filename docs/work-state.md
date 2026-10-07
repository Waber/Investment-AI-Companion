# Current Work State

## Resume Instructions

Latest delivery is the 2026-10-07 rebase workflow rule (docs only; see the
journal entry above the handoff). No production code changed. Account usage
from the previous ChatGPT tooling was not available in that Cursor session.

Pydantic/SQLAlchemy deprecation cleanup is in progress on a separate branch
by the Developer. Migrations/PostgreSQL still follow that cleanup. The
**Next Iteration Handoff - 2026-10-07** in [the development journal](development-journal.md)
remains the checklist for that work.

This pull request and the Developer's deprecation-cleanup pull request both
edit the top of the journal and `docs/work-state.md`. Whichever merges second
must rebase onto the updated `origin/master` and resolve those conflicts
carefully, keeping both sides' intent.

`origin/master` contains `b10d06e` (Merge pull request #2 from
`Waber/fix/startup-lifespan-cors`). The note below that PR #2 was still open
is historical. Branch new work from updated `origin/master` and rebase feature
branches onto it. Do not merge the rebase-workflow pull request unless the
user explicitly authorizes it.

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
  five-hour / 6% weekly. Next action: review/merge PR before subsequent development.
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
  and JSON overflow handling are complete. Lifespan/CORS is now complete;
  Pydantic/SQLAlchemy deprecation cleanup remains deferred.
- Editable profiles and source-aware AI analysis remain unimplemented. Demo preferences are preserved in the approved September8 design/plan, not yet implemented.
- Prior WIP dependency pin on `feature/research-workflow-and-hardening` conflicts with FastAPI and is NOT in this branch. Do not merge blindly.
- This manually exercised PostgreSQL demo is not completion of the migration/integration-test task. Financial-metrics provider ingestion is still a placeholder.
- After lifespan/CORS delivery: guarded migrations and automated PostgreSQL
  integration tests. Do not assume the old demo runtime still exists.
