# Development Journal

`CONVERSATION.md` contains legacy project history. This journal is the forward-looking delivery log for new agentic development.

## 2026-07-04 - Iteration 1 (project guidance and baseline tests)

### Scope
- Add repository-level agent/developer guidance.
- Add baseline automated tests.
- Fix financial metrics schema alignment.
- Add test seams for local API work without live providers.

### Status
- Delivered.

### Verification
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider` -> passed, 4 tests, 6 legacy warnings.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m black --check tests` -> passed, 5 test files unchanged.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m isort --check-only tests` -> passed.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m flake8 tests` -> passed.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m black --check app main.py setup_database.py tests` -> failed on legacy formatting debt in application files; this was already present in the pre-edit baseline. New tests were formatted separately and pass `black --check tests`.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m isort --check-only app main.py setup_database.py tests` -> failed on legacy import-order debt in application files; this was already present in the pre-edit baseline.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m flake8 app main.py setup_database.py tests` -> failed on legacy style/import issues in application files; `tests/` passes separately.

### AI model
- ChatGPT Codex (GPT-5).
- Subagents used: spec reviewer, plan reviewers, and a documentation implementation worker.

### Time tracking
- Task window: 2026-07-04 17:46-18:05 CEST, about 19 minutes for implementation and verification after plan approval.
- Team/subagents used: yes.
- Coordinator effort: about 19 minutes wall-clock in this implementation window, plus earlier spec/plan orchestration on this branch.
- Developer effort: documentation worker completed Task 1; remaining implementation was coordinated in-session with TDD checkpoints.
- Reviewer effort: one spec review and three plan review passes before implementation; final code review was pending at delivery and was completed on 2026-09-08 (see follow-up below).

### Notes
- `.python-version` existed before this iteration as an untracked local file and was left unmodified/uncommitted.
- Local `.venv` has `httpx 0.28.1` while `requirements.txt` pins `httpx==0.25.2`; tests use `httpx.ASGITransport` to avoid the incompatible legacy `TestClient` path in this environment.
- Full application lint/format cleanup should be handled as a separate technical-debt iteration to avoid mixing broad style churn with this baseline test/refactor slice.

## 2026-09-08 - Baseline review and corrective changes

### Scope and status
- Completed the independent senior engineer/architect review of the full baseline iteration, not only the latest documentation commit.
- Fixed all three actionable findings on dedicated branches and integrated the approved commits into `feature/project-guidance-and-baseline-tests`.
- Independent reviewer Noether accepted each fix. No reported blockers remain for this iteration.
- Full findings, evidence, and remaining limitations: [baseline review](reviews/2026-09-08-baseline-review.md).

### Changes
- Configuration: represent CORS origins as a JSON array in `.env.example`; add a smoke test that loads the actual template in an isolated environment.
- Financial metrics: reject non-finite values before persistence across all 20 numeric fields, preserving finite numbers, nulls, and omitted update fields.
- Test database: enable SQLite foreign keys on every physical connection before schema creation; test missing-company rejection, valid persistence, and replacement connections.

### Team and branches
- Coordinator: Codex (GPT-6), integration, independent verification, and documentation.
- Noether: senior engineer/architect, baseline review and independent review of each corrective change.
- Descartes: configuration fix on `fix/config-template-startup` (source commit `2c7fae8`).
- Linnaeus: database/QA fix on `fix/test-database-integrity` (source commit `00d346b`).
- Ohm: financial validation fix on `fix/finite-financial-metrics` (source commit `bc7c724`).
- Developers worked in separate worktrees; the database and validation fixes ran in parallel. Agents inherited the coordinator model.
- Integrated application commits: `5597a00`, `5f1b2fb`, and `719f691`. At review delivery these were on the development branch; subsequent publication is recorded below.

### Verification
- Combined suite at `719f691`: **537 passed, 6 existing deprecation warnings**. This includes parameterized unit cases and API regression tests, not 537 distinct workflows.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m black --check tests`: passed, 8 files unchanged.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m isort --check-only tests`: passed with default settings.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m flake8 tests`: passed with default settings.
- Each corrective code commit passed `git diff --cached --check` before commit.
- The combined suite ran from `/private/tmp` with a clean environment and the repository on `PYTHONPATH`, without reading the developer's `.env`. Exact command:

```bash
/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/przemkowy/IdeaProjects/Investment-AI-Companion /Users/przemkowy/IdeaProjects/Investment-AI-Companion/.venv/bin/python -m pytest -q -p no:cacheprovider /Users/przemkowy/IdeaProjects/Investment-AI-Companion/tests
```

- An earlier coordinator test launcher disabled dotenv loading globally and caused the template smoke test to fail. Removing that launcher override, without changing application code, produced the final result above.
- No live PostgreSQL instance or market-data providers were used. Full legacy application lint cleanup and dependency upgrades were not part of this follow-up.

### Time tracking and continuity
- Recorded local commit checkpoints (CEST): configuration at 20:16, database at 20:21, validation at 20:24 on 2026-09-08.
- Exact per-agent durations were not measured; no synthetic effort totals are reported.
- A usage-limit interruption stopped Ohm before final verification; work resumed from the existing files after the user reset the limit.
- The existing untracked `.python-version` was preserved.

### Publication after user approval
- On 2026-09-08 the user authorized committing, pushing, and merging the reviewed iteration into the default branch.
- Confirmed GitHub's default branch is `master`; fetching showed no divergent remote commits.
- Pushed `feature/project-guidance-and-baseline-tests`, then fast-forwarded local `master` through all 14 iteration commits to `08fc2fe` without conflicts.
- Re-ran the full isolated suite on `master`: **537 passed, 6 existing warnings**.
- Pushed `master` and independently confirmed the remote ref at `08fc2fe72fa6dce61b5856d36a120c6d99b52bc5`.
- This documentation-only follow-up records that completed publication; it does not change the tested application or test files.

## 2026-09-08 - Remaining-work iteration (in progress)

- User authorized continuing the remaining work listed in the baseline review.
- Created `feature/research-workflow-and-hardening` from published `master` at `6e1f2fc` in an isolated worktree.
- Added explicit session checkpoint rules and `docs/work-state.md` at the user's request, so later sessions can identify what is done, what is unfinished, and why work stopped.
- This is a documentation checkpoint while work continues, not a usage-limit stop. The current usage check did not indicate a reached limit.
- Product clarification received: horizon over ten years, broad markets including Poland/US/Europe/Asia, moderate-to-high risk, stocks/bonds/ETFs/ETCs, excluding direct derivatives such as futures/CFDs. The user requires an editable demo profile and support for different preferences, not hardcoded personal assumptions.
- Coordinator: Codex (GPT-6). No implementation agents dispatched for this new iteration yet. Precise elapsed time is not being measured; implementation and verification will be logged at delivery.
- No application or test files changed in this checkpoint. The previously published baseline passed 537 test cases; tests are not being represented as a new run for documentation-only changes.

## 2026-09-08 - WIP partial checkpoint: Task 2 CRUD regressions (paused)

### State and stop reason
- Worktree: `/private/tmp/investment-crud-regressions`.
- Branch: `fix/crud-update-regressions`; pre-checkpoint HEAD: `10ab10d6bf1ba15e9105dc85d86b32c1816a5835`.
- User-requested pause to preserve state before the next iteration after context/usage pressure. The user reports that the previous run encountered a usage-limit error and that credits have now been reset. No credit balance or reset result was independently checked in this task.
- Task 2 remains incomplete and paused. The checkpoint is not approval to resume implementation or integrate changes.

### Actual work and decisions
- Confirmed the requested worktree, branch, and base commit; located AGENTS, the approved plan/design, and relevant source/test paths.
- Read the workflow skills for TDD, systematic debugging, plan execution, and verification; read AGENTS and the existing journal for this checkpoint.
- No application or test edits were made. Neither `tests/test_updates_api.py` nor `tests/test_collection_updates.py` was created. The only checkpoint edit is this journal entry.
- No implementation/design decisions or behavior corrections have been established. No delegation, integration, push, or worktree deletion was performed.
- All commands launched by this task had exited; no owned implementation or testing process remained running.

### Verification actually performed
- `pwd`: confirmed `/private/tmp/investment-crud-regressions`.
- `git status --short --branch`: clean worktree on `fix/crud-update-regressions` before the journal edit.
- `git log -1 --format='%H %s'`: confirmed the pre-checkpoint HEAD above (`docs: clarify migration and analysis contracts`).
- `git diff --stat`, `git diff`, and `git diff --cached`: all empty before the journal edit.
- `git diff --check`: passed after adding this checkpoint entry.
- No pytest, red/green cycle, full suite, formatter, or linter was run. Earlier journal test results are historical, not verification of Task 2.

### Pending work, blockers, and exact next action
- The intentional user pause is the current stop condition; implementation blockers have not yet been investigated. Parent and Russell reviews remain pending before any final implementation commit or integration; the user separately authorized this WIP checkpoint commit.
- On explicit resumption, first inspect git status, read `docs/work-state.md`, the latest journal entry, `docs/superpowers/plans/2026-09-08-research-workflow-and-hardening.md` (Task 2), and `docs/superpowers/specs/2026-09-08-research-workflow-and-hardening-design.md`. Then inspect the assigned APIs/repositories, existing tests/conftest, and configuration without reading `.env` or a private database.
- Write the first failing regression test before production edits. Cover missing-update 404, company URL omitted/changed/null, metrics partial updates/null, conflicts, rollback/recovery, relevant cascade behavior, and fake-collector existing-company/404 paths. Investigate deterministic duplicate-ticker 400 semantics only as supported by regression evidence and existing constraints.
- Implementation ownership remains limited to `app/api/companies.py`, `app/api/financial_metrics.py`, `app/repositories/company_repository.py`, `app/repositories/financial_metrics_repository.py`, `tests/test_updates_api.py`, and `tests/test_collection_updates.py`. Do not edit data collection API, main, models, conftest, or unrelated files.
- Pending test invocation after confirming isolation: `/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 /Users/przemkowy/IdeaProjects/Investment-AI-Companion/.venv/bin/python -m pytest -q -p no:cacheprovider`, from this worktree. Use deterministic fakes, no live providers, no `.env`, and no private database. Record exact red/green and full-suite results when actually run.

### Model and time tracking
- Agent: Codex (GPT-6); no subagents used.
- Exact elapsed time was not measured. This entry records a partial checkpoint, not delivery of Task 2.

## 2026-09-22 - Missing-update responses (bounded iteration, completed locally)

### Scope and plan
- User authorized only the missing-record update fix, regression tests, independent review, a local commit, and journal. Other remaining-work tasks stay paused.
- Created `fix/missing-update-not-found` at `/private/tmp/investment-update-404` from CRUD checkpoint `83bb7ed`. Old temporary worktrees are absent, but commits remain in Git. No old registrations/branches removed.
- Both update routes raise intended HTTP 404 inside a broad exception handler that converts it to 500. Start with failing API regressions, apply the smallest fix, verify 400/500 and successful-update behavior remains intact.
- Carson implements two routes and focused tests. Coordinator handles baseline/final verification, usage checks, and documentation; separate review follows implementation.
- No migrations, dependency updates, profiles, broad formatting, push, or merge.

### Baseline and resource checks
- Fresh baseline: 537 passed, six existing warnings. Command, from `/private/tmp`:

```bash
/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/investment-update-404 /Users/przemkowy/IdeaProjects/Investment-AI-Companion/.venv/bin/python -m pytest -q -p no:cacheprovider /private/tmp/investment-update-404/tests
```

- Usage: before work, 8% five-hour and 2% weekly used; after preparation, 14% and 3%. These are not remaining-context measurements. No exact context counter is exposed; no reset/purchase performed.
- After implementation usage: 33% five-hour/6% weekly used; initial verification: 40%/7%; review and formatting completion: 48%/9%. These account-wide snapshots do not measure task cost or context capacity.
- Coordinator and agents use the configured inherited Codex model; exact model identity and elapsed effort were not independently measured in this iteration.

### Changes and verification
- Both update routes now re-raise HTTPException before the broad exception handlers. Missing company and financial-metrics updates preserve their existing 404 messages rather than returning 500. No repository/model/dependency changes.
- Added eight cases in `tests/test_missing_updates_api.py`: missing-record exact 404 and no DML/data changes, existing successful persisted updates, business errors mapped to 400, unexpected errors mapped to generic 500 without leaking their message.
- Carson reported RED: two tests failed with 500 instead of 404, six passed. After the fix, eight passed; full suite 545 passed. The coordinator did not independently reproduce RED.
- Hume independently reviewed specification compliance and code quality: approved, no actionable findings. His focused test run passed all eight cases.
- Coordinator's first style check found new-test formatting/import/line-length issues. Carson corrected only test formatting; no functional changes.
- Coordinator reran the full command above after formatting: **545 passed, six existing deprecation warnings**.
- Default checks passed for all nine test files: `.venv/bin/python -m black --check tests`, `-m isort --check-only tests`, `-m flake8 tests` (using the primary repository interpreter from this worktree).
- Tests use isolated SQLite, with repository exceptions injected only for error mapping. No live database/provider verification or application-wide lint cleanup was performed. Legacy warnings remain out of scope.

### Delivery and next action
- Carson and Hume were closed after final reports. No owned long-running process remains from this iteration.
- This change and documentation are saved together in a local commit on `fix/missing-update-not-found`; no push or merge. Primary `master` and the user's untracked `.python-version` remain unchanged.
- Stop reason: approved bounded scope completed, not resource exhaustion. No account reset or credit purchase was needed or performed.
- Next authorized iteration: integrate this reviewed fix as appropriate, then add failing Task 2 regressions for URL omission/change/null. Broader CRUD, lifecycle, PostgreSQL, profiles, and AI work remain unfinished; see [work-state](work-state.md).

## 2026-09-22 - Company website updates (bounded test-only task, completed locally)

- User authorized the next small task with resource checks; scope is only website omission, replacement, null clearing, and invalid URL rejection. No broader CRUD/migration/AI work.
- Branch `test/company-website-updates` at `/private/tmp/investment-website-updates`, based on reviewed `3a2b0af`; parent suite verified in this session: 545 passed, six legacy warnings.
- Existing update code already handles `exclude_unset` and optional URL serialization. Contrary to the earlier generic next-step wording, characterization tests can legitimately pass immediately; do not invent a failing bug or change correct production behavior.
- Ohm owns only `tests/test_company_website_updates.py`; coordinator owns documentation and final verification. Separate independent review follows.
- Initial resource check: 59% five-hour and 10% weekly used. These account-wide percentages are not a context measurement or a completion guarantee. No reset/purchase.
- No push/merge; preserve prior branches and the primary checkout's unrelated `.python-version`.

### Results and handoff
- Added only `tests/test_company_website_updates.py` plus coordinator documentation. Four cases verify omission, normalized replacement, null clearing, and invalid URL rejection without mutation through PUT responses, GET readback, and fresh database sessions. Production code was already correct and remains unchanged.
- Ohm reported focused four passed/full 549 passed, six existing warnings. Dalton independently approved spec and quality, no findings, and ran all four focused cases successfully.
- Coordinator independently ran the full suite: 549 passed, six existing warnings. Command from `/private/tmp`: `/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/investment-website-updates /Users/przemkowy/IdeaProjects/Investment-AI-Companion/.venv/bin/python -m pytest -q -p no:cacheprovider /private/tmp/investment-website-updates/tests`.
- Coordinator's repository-local isort check required one blank line between third-party and application imports despite the developer's reported pass; corrected that formatting-only issue after review. Default Black/isort/flake8 checks and the suite are rerun before commit.
- Usage after preparation: 65% five-hour/11% weekly used; after implementation and full verification: 78%/13%. No exact context counter, reset, or purchase. Stop at completed scope to conserve the remaining allowance, not because a limit was reached.
- Agents Ohm and Dalton closed at delivery. Same configured inherited model; exact identity and elapsed effort not independently measured. No agent-owned long-running process.
- SQLite-only characterization; no PostgreSQL/provider calls and no claim of fixing a newly reproduced bug. Existing warnings remain.
- Next separately authorized slice: metric partial-update/null regression coverage. The full Task 2 remains incomplete. Keep this local branch for later integration; no automatic push/merge.
- Final post-format verification: 549 passed, six existing warnings; default Black/isort/flake8 passed for all ten test files. After review and final verification, usage was 85% five-hour/14% weekly consumed. Scope completed with remaining allowance; both agent shutdowns confirmed.
