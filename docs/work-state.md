# Current Work State

## Checkpoint

- Date: 2026-09-22.
- Status: website-update regression task completed locally with this delivery commit. Other remaining-work tasks stay paused; no push or merge.
- User authorized the next small task with usage checks: verify website omission, replacement, explicit null, and invalid URL rejection; independent review, local commit, and journal. No push or merge requested.
- Branch: `test/company-website-updates`, based on verified `3a2b0af` (missing-update fix).
- Worktree: `/private/tmp/investment-website-updates`.
- Primary repository: `/Users/przemkowy/IdeaProjects/Investment-AI-Companion`. The saved project directory under `PycharmProjects` is not this repository.
- Previous temporary worktrees are absent and Git marks their registrations prunable. Their committed checkpoints remain recoverable from Git. No old branch or registration was deleted.

## Current Iteration

1. Preparation: inspected existing website serialization and `exclude_unset` behavior. The parent revision passed 545 tests with six legacy warnings in this session.
2. Ohm owns only `tests/test_company_website_updates.py`: response, read-back, and stored-value checks for omission/replacement/null and rejection without mutation for invalid URLs. Existing behavior is expected to pass; these are characterization tests, not a newly claimed bug fix.
3. Dalton independently approved specification and quality with no findings; four focused cases passed. Coordinator full suite: 549 passed, six existing warnings.
4. Production code unchanged. Coordinator corrected one import-group blank line after review; final style/test checks accompany the local commit.

Previous slice `3a2b0af` is complete and included in this branch: missing updates return404, eight added cases, independent Hume approval, 545 total passing. Carson and Hume were closed.

The coordinator owns this file and the journal. No repository/model changes, provider calls, real database migrations, dependency upgrades, or broad formatting cleanup belong to this iteration.

## Usage And Continuity

- User requested usage checks after every stage. Website-task start: 59% five-hour and 10% weekly allowance used. Account usage windows are not remaining conversation context or per-task cost attribution.
- After preparation: 65%/11% used; implementation and full verification: 78%/13%. Scope was not expanded so there remained capacity for review and checkpointing.
- After review and final verification: 85%/14% used. Final suite 549 passed with six existing warnings; all ten test files pass default Black/isort/flake8. Both agents closed. No further task started.
- No exact remaining-context counter is available; do not infer guaranteed completion from usage percentages. No reset or purchase is authorized.
- Last full pause was user-requested after context/usage pressure on September 8. All previous agents were closed. Only this small scope is now resumed.

## Previous Checkpoints

- `d3dcbaf` on `feature/research-workflow-and-hardening`: full prior checkpoint and failed dependency-upgrade attempt. Recover with `git show d3dcbaf:docs/work-state.md`.
- `1d203c3` on `fix/runtime-validation-lifespan`: runtime task journal only.
- `83bb7ed` on `fix/crud-update-regressions`: CRUD task journal only; base of this iteration.
- `55bc514` on `test/postgresql-migrations`: database task journal only.
- `10ab10d`: approved design/plan after Russell's six findings were resolved; not implementation approval.
- The WIP OpenAI 3.9.0 pin conflicts with FastAPI 0.104.1's AnyIO requirement. It is NOT included in this branch; do not merge it blindly.

## Remaining Work After This Slice

- Other Task 2 regressions: metric partial updates, uniqueness and rollback, collection update paths. URL omission/change/null and invalid-URL rejection coverage is complete in this branch.
- Task 1: JSON overflow validation, lifespan/startup modernization, CORS, deprecations.
- Task 3: migration-only initialization, guarded legacy adoption, isolated PostgreSQL tests and cleanup.
- Task 4: persistent editable investor profiles. Demo preferences: horizon over ten years, Poland/US/Europe/Asia, moderate-to-high risk, stocks/bonds/ETFs/ETCs, no direct derivatives such as futures/CFDs. These are editable defaults, never inferred holdings or global restrictions.
- Task 5: source-aware AI analysis after profile contracts and a verified compatible dependency set.
- Task 6: integrated verification, remaining style debt, and independent review before future merge.

The approved [plan](superpowers/plans/2026-09-08-research-workflow-and-hardening.md) and [design](superpowers/specs/2026-09-08-research-workflow-and-hardening-design.md) remain the broader reference. This slice does not complete the entire CRUD task.

## Verification Environment

- Interpreter: `/Users/przemkowy/IdeaProjects/Investment-AI-Companion/.venv/bin/python`.
- Run from `/private/tmp` with a clean environment, this worktree on `PYTHONPATH`, `PYTHONDONTWRITEBYTECODE=1`, and pytest cache disabled. Tests use in-memory SQLite and no live providers.
- Preserve the primary checkout's unrelated untracked `.python-version`.
- Previous missing-update slice: developer reported RED two failed/six passed, then GREEN eight passed; coordinator verified full 545 tests after formatting. Website characterization: four passing cases for already-correct behavior, not a new red/green bug fix.
- Residual limits: SQLite only, injected repository exceptions for error mapping, six pre-existing deprecation warnings. No real PostgreSQL/provider checks or full application lint cleanup in this slice.

## Next Action

Stop at this completed task boundary to conserve usage; no limit failure occurred. Neither slice is merged into `master` or the wider integration branch. The entire Task 2 is not complete. A future separately authorized slice can cover metric partial updates/null. If this temporary worktree disappears, recover this file from `test/company-website-updates` with Git. The developer Ohm and reviewer Dalton are closed at delivery.
