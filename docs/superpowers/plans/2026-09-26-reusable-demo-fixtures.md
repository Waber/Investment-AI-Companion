# Reusable Demo Fixtures Implementation Plan

**Goal:** Populate the isolated running demo with reproducible, explicitly synthetic data without overwriting user edits.

**Architecture:** A versioned JSON fixture is the source of truth; a standard-library HTTP client imports it through existing API endpoints. Default dry-run uses GET only; explicit `--apply` adds missing records. No new production endpoints, database connection, dependencies, automatic startup seeding, or real market data.

**Scope:** Six synthetic companies across Poland/US/Germany/Japan/Singapore; four reporting periods for five companies, one company with no metrics. Include profits, losses, zero revenue, sparse fields, and absent URLs. Stable reserved tickers identify records; marker `[IAC-DEMO-V1]` in descriptions distinguishes this fixture. Only companies are modeled today, so do not misrepresent bonds/ETFs as supported instruments.

## Tasks

- [x] Inspect existing schema/legacy seed and preserve the live demo's existing records.
- [x] Coordinator: create `fixtures/demo-v1.json` and schema/scenario tests in `tests/test_demo_fixture.py` (two passed).
- [x] Developer: TDD `scripts/seed_demo.py` and `tests/test_seed_demo.py` for dry run, idempotency, preservation, collision preflight, pagination, UTC-equivalent timestamps, and partial-failure resumption (60 focused cases passed).
- [x] Independent reviewer: inspect scope, transport safety, preservation, fixture validity, and test evidence (Volta approved; 62 focused cases passed).
- [x] Coordinator: run full isolated tests and focused style checks; dry-run/apply against the known demo; repeat apply and confirm zero new records and preservation of unrelated data (611 total passed; first apply6/20, second0/0).
- [x] Document commands/scenarios/limitations and checkpoint; deliver in local commit, leave demo running. No push or merge.

## Contracts And Safety

- Fixture: `{version: 1, marker: "[IAC-DEMO-V1]", companies: [{company: {...}, metrics: [...]}]}`. Use only fields accepted by current schemas and timezone-aware period ends.
- Use an explicit numeric loopback HTTP URL; disable proxy inheritance and redirects, bound request timeouts. Loopback is not proof of database isolation; the operator must select the isolated demo.
- Validate fixture and preflight existing ticker ownership before any POST. Never PUT or DELETE. Existing values remain unchanged. If a fixture ticker lacks the marker, fail rather than attach data to it.
- Paginate company/metric reads; compare metric keys by normalized UTC instant and period type. Preserve edits to existing financial values.
- Each HTTP POST commits separately: failures are not atomic. Report failure and allow sequential rerun to fill missing records. Concurrent seed runs are not supported.
- No reset/delete command. Back up valuable data elsewhere; the running demo database is temporary, while fixtures are committed and reproducible.
- Existing `DEMO` and user-created records must remain untouched.

## Verification

From `/private/tmp`, run the primary `.venv/bin/python -m pytest -q -p no:cacheprovider` with clean environment, `PYTHONDONTWRITEBYTECODE=1`, and this worktree on `PYTHONPATH`. Use deterministic fake clients for seed unit tests and existing isolated SQLite fixtures for schema tests. Live verification is separate against `http://127.0.0.1:8081`; do not use providers or private `.env`.
