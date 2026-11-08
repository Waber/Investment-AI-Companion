# Provenance slice A implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development while implementing. This session executes the plan inline. Subagent-per-task was not used: account usage was already 68.4% at dispatch (coordinator reading, under the 80% stop), and this session cannot read a usage meter of its own.

**Goal:** Store `companies.is_synthetic`, `companies.source`, and `financial_metrics.source`, backfill today's `[IAC-DEMO-` rows, and stop the runtime badge from parsing that prefix.

**Architecture:** Alembic `0009` revises `0008` and is the only head. The database columns are plain strings and a boolean with server defaults. Allowed source values live next to the SQLAlchemy models and are checked in Python, not with a CHECK constraint. UI and API writes always store `source='manual'` and never assign `is_synthetic`. The sqlite seeder passes `demo` and `is_synthetic=True` explicitly. Templates stay as they are. The view-model label for a synthetic row is the single word `demo`.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0.23, Alembic 1.12.1, pytest, SQLite 3.45, PostgreSQL 16 in CI (and locally when the service is installed).

## Global Constraints

- Live issue #105 (verified 2026-11-08, no comments): `companies.is_synthetic` Boolean NOT NULL server default false; `companies.source` and `financial_metrics.source` String(64) NOT NULL server default `'manual'`. Allowed sources now: `manual`, `demo`, `fixture`. Validated in the model layer, not a CHECK, so a later `yahoo` value needs no migration.
- Revision `0009`, `down_revision` `0008`. No newer revision exists on `origin/master` `e71c098`. #28's `0010` is not this task. Price bars already have `source` and stay out of scope.
- Backfill: a company description that starts with `[IAC-DEMO-` is `is_synthetic` true and `source` `demo`. Every other company is false and `manual`. A metric is `demo` only when its company is synthetic, otherwise `manual`.
- UI and API create/update set `source` to `manual` and do not change an existing `is_synthetic`. A description edit must keep the flag.
- Seeders and demo fixtures set `is_synthetic` true and `source` `demo` on the in-process sqlite writer. The public HTTP API does not accept a caller-chosen source, so `seed_demo --base-url` stays on that API rule.
- Owner decision, PM transcript 2026-11-08 17:56 (not in the GitHub issue body): one shared label `demo` replaces `demo-v1` and `demo-v2`. Do not add a version field. Do not keep prefix parsing for the runtime label. Document and test this acceptance change. Templates are not edited. If a template edit were required, stop and report the blocker.
- No edit-time column, no visible `manual` badge, no ETF/ETC work, no #34 close, no #28 / `0010`.
- No live market data. No secrets. Do not edit PR #126 or its branch. `Refs #105`. Do not use a closing keyword.
- Invalid and missing `source` values fail in the model helper. The check is exact: `None`, `""`, `"   "`, `"Manual"`, `"demo-v1"`, `"yahoo"`, and non-strings raise `ValueError`. `manual`, `demo`, and `fixture` pass. An omitted attribute uses the server and Python default `manual`. A raw SQL value outside the set is still stored, because there is no CHECK.

## Owner acceptance change

Issue #105 says the current badges still render the same, and the helper stops reading the description prefix. The templates print `instrument.is_synthetic` (catalog badge "synthetic data" / "dane syntetyczne") and `instrument.source` (today `demo-v1`, `demo-v2`, or `demo`). The owner later decided one label, `demo`, replaces the versioned labels. Template files stay unchanged. The view-model value they print changes from a parsed token to `demo` whenever `is_synthetic` is true, and stays empty when it is false, so the word `manual` is not shown. That is the acceptance change this plan tests.

## File structure

- Create: `alembic/versions/0009_company_provenance.py` — add columns, backfill, drop on downgrade.
- Modify: `app/models/database_models.py` — constants, `require_record_source`, columns, `@validates` on `source`.
- Modify: `app/repositories/company_repository.py` and `app/repositories/financial_metrics_repository.py` — write-path provenance.
- Modify: `scripts/seed_demo.py` — sqlite seeder passes demo provenance.
- Modify: `app/ui/view_models.py` and `app/ui/watchlist_view.py` — flag and one label, no prefix parse.
- Create: `tests/test_provenance_migration.py`, `tests/integration/test_postgres_provenance_migration.py`, `tests/test_record_source.py`, `tests/test_provenance_writes.py`.
- Modify tests that pin Alembic head `0008`, the badge tests, and the view-model tests.
- Do not modify: `app/ui/templates/`, `static/`, price-bar code, PR #126 files.

## Decisions locked before code

- Columns are appended, matching `op.add_column` and `create_all`.
- `server_default` is `sa.false()` and `'manual'`. Both engines accept those constants. The migration adds a column only when it is missing, so a `create_all` database stamped before `0009` can still upgrade (this repository's legacy tests do that). The backfill still runs.
- Downgrade uses SQLite `ALTER TABLE ... DROP COLUMN` (3.35+, this tree is 3.45.1) and PostgreSQL `DROP COLUMN`. A batch copy of `companies` would `DROP TABLE companies` while metrics, prices, notes, theses, and the watchlist point at it. With foreign keys on, that drop fails or deletes the child rows. Batch mode is the wrong tool for this drop. The downgrade test keeps a metric row.
- The page label is `demo` when `is_synthetic` is true, including after a UI edit that stored `source='manual'`. Non-synthetic rows keep a missing source cell. `demo_source_label` is removed.
- `fetch-company` uses the repository, so an update of a seeded company records `manual` and leaves `is_synthetic` as it was.

---

### Task 1: Migration 0009

**Files:**
- Create: `alembic/versions/0009_company_provenance.py`
- Test: `tests/test_provenance_migration.py`
- Test: `tests/integration/test_postgres_provenance_migration.py`
- Modify: head pins in `tests/test_alembic_env.py`, `tests/test_watchlist_migration.py`, `tests/test_research_notes.py`, `tests/test_theses_closed_at_migration.py`, `tests/integration/test_postgres_theses_closed_at_migration.py`

**Interfaces:**
- Produces: revision id `0009`, `down_revision` `0008`.
- Consumes: nothing.

- [x] Write the SQLite upgrade, backfill, default, no-CHECK, and downgrade test. Run it and confirm it fails because revision `0009` does not exist.
- [x] Add the migration. Run the SQLite test and confirm it passes.
- [x] Point the old "head is 0008" assertions at `0009`, and make the closed-at tests expect head `0009` after `upgrade_head`.
- [x] Run the PostgreSQL copy when `TEST_POSTGRES_DSN` is available.

### Task 2: Model constants and source validation

**Files:**
- Modify: `app/models/database_models.py`
- Test: `tests/test_record_source.py`

**Interfaces:**
- Produces: `RECORD_SOURCE_MANUAL`, `RECORD_SOURCE_DEMO`, `RECORD_SOURCE_FIXTURE`, `RECORD_SOURCES`, `require_record_source(value) -> str`.
- `CompanyDB.is_synthetic`, `CompanyDB.source`, `FinancialMetricsDB.source`.

- [x] Parameterize missing and invalid sources and expect `ValueError` with `manual, demo, or fixture`. Expect the three allowed strings to pass. Run and confirm `require_record_source` is missing.
- [x] Add the helper, the columns (Python default plus server default), and `@validates("source")` on both models. A raw SQL value outside the set still loads only if the validator does not run on load; if it does, the test records that and the write path still rejects it before flush.
- [x] An omitted ORM source flushes as `manual`. An explicit `None` raises.

### Task 3: Repository and seeder writes

**Files:**
- Modify: `app/repositories/company_repository.py`
- Modify: `app/repositories/financial_metrics_repository.py`
- Modify: `scripts/seed_demo.py`
- Test: `tests/test_provenance_writes.py`

**Interfaces:**
- `CompanyRepository.create(company, *, record_source="manual", is_synthetic=False)`
- `CompanyRepository.update` sets `source` to `manual` and does not assign `is_synthetic`.
- `FinancialMetricsRepository.create(metrics, *, record_source="manual")`
- `FinancialMetricsRepository.update` sets `source` to `manual`.
- `SqliteSeedClient` passes `record_source="demo"` and `is_synthetic=True` for companies, and `record_source="demo"` for metrics.

- [x] Tests first: API-shaped create with a `[IAC-DEMO-` description stores manual/false. Update keeps a true flag and sets source manual. Metric create/update stores manual unless the keyword is `demo`. Seeder rows are true/demo and metric source demo. Invalid keyword raises. Run, confirm failure.
- [x] Minimal repository and seeder changes. Run, confirm pass.

### Task 4: One runtime demo label

**Files:**
- Modify: `app/ui/view_models.py`
- Modify: `app/ui/watchlist_view.py`
- Modify: `tests/test_ui_view_models.py`, `tests/test_ui_pages.py`, `tests/test_ui_forms.py`, `tests/test_ui_watchlist_view.py`

**Interfaces:**
- `to_instrument` sets `is_synthetic` from the attribute, not the description. `source` is `demo` when that flag is true, else `None`.
- `to_entry` uses `company.is_synthetic`.
- No template diff.

- [x] Rewrite the view and page tests to the new contract. Run and confirm they fail on the old prefix parser.
- [x] Remove `demo_source_label` and the prefix read. Run and confirm pass. `git diff -- app/ui/templates` is empty.

### Task 5: Docs and full verification

- [x] Journal entry and a new work-state section. Historical entries stay. PR #124 is merged on GitHub; say so where this snapshot would otherwise repeat "open". PR #126 stays open and is not this branch.
- [x] SQLite CI command. PostgreSQL integration command when the server is up. `black`, `isort`, `flake8` on the changed Python files. `alembic heads` is `0009`.

## Spec coverage

| Requirement | Task |
| --- | --- |
| Columns, defaults, no CHECK | 1, 2 |
| Backfill rule | 1 |
| Upgrade and downgrade, both engines, child rows kept | 1 |
| Single head `0009` on `0008` | 1 |
| Model constants and invalid/missing source | 2 |
| UI/API manual, flag preserved | 3 |
| Seeder explicit demo | 3 |
| One `demo` label, no prefix parse, templates unchanged | 4 |
| No manual badge, no price-bar edit, no #28 | out of scope, not implemented |
| Journal and work-state | 5 |
