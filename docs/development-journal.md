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
