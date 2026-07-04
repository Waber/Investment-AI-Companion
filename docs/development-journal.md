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
- Reviewer effort: one spec review and three plan review passes before implementation; final code review pending after this journal update.

### Notes
- `.python-version` existed before this iteration as an untracked local file and was left unmodified/uncommitted.
- Local `.venv` has `httpx 0.28.1` while `requirements.txt` pins `httpx==0.25.2`; tests use `httpx.ASGITransport` to avoid the incompatible legacy `TestClient` path in this environment.
- Full application lint/format cleanup should be handled as a separate technical-debt iteration to avoid mixing broad style churn with this baseline test/refactor slice.
