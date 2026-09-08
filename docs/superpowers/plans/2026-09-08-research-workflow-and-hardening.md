# Research Workflow And Backend Hardening Implementation Plan

> Use subagent-driven development with separate developer worktrees and an independent reviewer. The user already selected this workflow and authorized the remaining-work scope.

**Goal:** Close the technical remaining-work items and deliver editable investor profiles plus an evidence-based AI research API.

**Architecture:** Retain FastAPI, Pydantic, and SQLAlchemy repositories. Add small profile/analysis modules, explicit provider injection, Alembic revisions, and isolated PostgreSQL verification.

**Tech stack:** Python 3.12, existing FastAPI/Pydantic/SQLAlchemy stack, PostgreSQL, pytest/httpx, OpenAI Responses SDK, Black/isort/flake8.

Design: [research workflow and hardening](../specs/2026-09-08-research-workflow-and-hardening-design.md).

## Task 1 - Runtime, validation errors, and CORS

Owner: backend developer. Files: `main.py`, `app/core/validation.py` (new), `app/core/database.py`, `app/models/company.py`, `app/models/financial_metrics.py`, `app/models/historical_data.py`, Pydantic configuration in `app/api/data_collection.py`, and new `tests/test_lifespan.py`, `tests/test_validation_errors.py`, `tests/test_cors.py`.

- [ ] Write failures for overflowing raw JSON payloads, lifecycle execution/disabled mode/failure propagation, and real browser-origin matching.
- [ ] Introduce JSON-safe request validation errors and lifespan with injectable test settings/engine as needed.
- [ ] Migrate deprecated configuration/import usage without changing existing response schemas.
- [ ] Run focused tests, full SQLite suite, and inspect warnings.
- [ ] Independent review, then commit and integrate.

## Task 2 - CRUD and collector regression coverage

Owner: second backend developer. Files: `app/api/companies.py`, `app/api/financial_metrics.py`, both existing repositories, and new `tests/test_updates_api.py`, `tests/test_collection_updates.py`. Do not modify Task 1 files or `tests/conftest.py`.

- [ ] Add failures for missing-update records returning 404, uniqueness conflicts, URL omission/change/null, metrics partial updates, and rollback/recovery after errors.
- [ ] Cover fake-collector refresh of an existing company and not-found behavior.
- [ ] Make only the minimal production fixes exposed by these tests, preserving documented status codes and database invariants.
- [ ] Run focused/full tests and independent review; commit and integrate.

## Task 3 - PostgreSQL tests and migration baseline

Owner: database/QA developer. Files: `scripts/test_postgres.py` (new), `tests/integration/conftest.py`, `tests/integration/test_postgres.py`, `alembic/versions/0001_baseline.py`, `alembic/env.py`, and dedicated pytest marker/config if necessary. Avoid changing shared SQLite fixtures.

- [ ] Add baseline migration matching existing companies/financial_metrics tables and constraints.
- [ ] Add opt-in integration fixtures that reject accidental use of the application's default DSN.
- [ ] Add a disposable local cluster runner with guaranteed shutdown and no TCP listener.
- [ ] Exercise constraints, timezone timestamps, cascade deletion, rollback recovery, upgrade/downgrade on the disposable database, and later new table revisions.
- [ ] Actually run PostgreSQL tests locally and report the server version; independently review before integration.

## Task 4 - Persistent investor profiles

Owner: profile developer. Files: new `app/models/investor_profile.py`, `app/models/investor_profile_db.py`, `app/repositories/investor_profile_repository.py`, `app/api/investor_profiles.py`, `alembic/versions/0002_investor_profiles.py`, `tests/test_investor_profiles.py`. Parent owns registration in main/Alembic after integration.

- [ ] Define the exported schema/model/repository contracts from the design.
- [ ] Add failing CRUD/validation tests and explicit demo-profile tests using the user's preferences.
- [ ] Implement additive persistence, bounded validation, full-profile validation on partial updates, and idempotent demo creation that preserves user edits.
- [ ] Test multiple independent profiles and mutation/persistence of every preference category.
- [ ] Review, commit, integrate, and register the router/model for startup/migrations.

## Task 5 - AI research workflow

Owner: AI developer after Task 4 contracts are available. New files: `app/models/analysis.py`, `app/models/analysis_db.py`, `app/repositories/analysis_repository.py`, `app/services/analysis_service.py`, `app/providers/openai_analysis.py`, `app/api/analyses.py`, `alembic/versions/0003_analyses.py`, and focused model/service/provider/API tests. Parent integrates settings/router imports and requirements.

- [ ] Write deterministic failures for profile selection, excluded instruments, evidence metadata, citation validation, and profile/evidence snapshots.
- [ ] Add a bounded, injectable provider interface and structured report schemas with three named scenarios.
- [ ] Implement lazy Responses API calls with configurable model, timeout, output budget, and no production fake fallback.
- [ ] Test missing credentials, provider refusal/timeouts/rate limits, malformed outputs, and unknown evidence IDs without live calls.
- [ ] Persist validated results and expose list/get without allowing later profile edits to rewrite historical inputs.
- [ ] Run unit/API tests and independent review; integrate and verify migrations on PostgreSQL.

## Task 6 - Repository quality and delivery

Owner: coordinator, after overlapping code edits are integrated.

- [ ] Align formatter/import settings; apply mechanical formatting to the application, entrypoints, migration code, and tests.
- [ ] Resolve remaining actual flake8 findings, avoiding blanket suppression.
- [ ] Install/verify the needed SDK version in an isolated development environment and update reproducible requirements.
- [ ] Run the full SQLite suite, PostgreSQL runner, migration checks, Black, isort, flake8, and a documented API smoke test.
- [ ] Update README/setup docs, example configuration, latest review, journal, and work-state snapshot with real outcomes and limitations.
- [ ] Complete final independent review and preserve scoped commits for publication.

## Coordination and checkpoints

Tasks 1, 2, 3, and 4 can run in parallel with disjoint file ownership. Main/Alembic registration is integrated by the coordinator after their respective owners finish. Task 5 follows the profile interface; Task 6 follows all behavioral edits. Each commit is reviewed with staged scope and whitespace checks. If context or usage capacity approaches a boundary, checkpoint work and update `docs/work-state.md` before stopping.

## Verification commands

Use the primary checkout's virtual environment until an isolated upgraded runtime is prepared; invoke it from the appropriate worktree with a clean environment and `PYTHONDONTWRITEBYTECODE=1`.

```bash
python -m pytest -q -p no:cacheprovider
python scripts/test_postgres.py
python -m black --check app main.py setup_database.py alembic scripts tests
python -m isort --check-only app main.py setup_database.py alembic scripts tests
python -m flake8 app main.py setup_database.py alembic scripts tests
```

The PostgreSQL runner must distinguish successful executed integration tests from a suite that only skipped them. No live AI-provider success may be claimed from a fake-provider test.
