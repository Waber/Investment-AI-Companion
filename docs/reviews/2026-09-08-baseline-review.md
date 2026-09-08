# Baseline Review - 2026-09-08

## Scope and verdict

Independent reviewer: Noether, acting as a senior Python engineer and software architect.

Reviewed baseline: `ce57523b1eb50ecfc102afce177c04c6475fbd51` through `4ee4938cb9aa33514a575633c73c75f9c84545d3`, including the approved design and implementation plan. The coordinator separately reviewed setup documentation and verification claims.

The initial verdict was to hold integration until three findings were fixed. Each fix subsequently received independent approval. All three fixes are now present on the development branch through `719f691`; the combined suite passes. No reported blockers remain for this iteration. This verdict does not certify the entire application for production.

## Findings and resolutions

### P1 - Shipped configuration prevented startup (resolved)

Location: `.env.example:15`.

Following README setup instructions copied comma-separated CORS origins into `.env`. Pydantic Settings decodes list fields as JSON before the field validator executes, so the example raised `SettingsError` before database access.

Resolution: use a JSON array in the template. `tests/test_config.py` copies the real template to a temporary directory, removes ambient environment overrides, executes a fresh configuration module, and verifies both parsed origins. The test failed before the fix and passed afterwards. No parser change was required.

Developer: Descartes. Independent reviewer: Noether. Integrated commit: `5597a00`.

### P2 - Non-finite financial values could break subsequent reads (resolved)

Location: `app/models/financial_metrics.py`, shared numeric fields.

Changing schema types from Decimal to float admitted values such as the JSON string `"Infinity"`. Updating a metric could commit infinity, fail response serialization with HTTP 500, and then break list reads. SQLite could silently store NaN as NULL. This was a validation regression, distinct from the pre-existing database Float columns.

Resolution: `ConfigDict(allow_inf_nan=False)` on the common model rejects non-finite values for all 20 fields. Unit tests cover both create/update models, numeric and string representations, valid finite numbers, nulls, and omitted fields. Representative POST/PUT tests verify HTTP 422, unchanged table contents, and readable list responses. A valid field included alongside the invalid field detects partial writes.

Developer evidence: 246 failing and 283 passing cases before the fix, then all 529 new cases passing. Noether independently confirmed all 533 tests on the isolated validation branch, preserved ORM loading, and unchanged JSON schemas.

Developer: Ohm. Independent reviewer: Noether. Integrated commit: `719f691`.

### P2 - SQLite tests did not enforce relational integrity (resolved)

Location: `tests/conftest.py`, test-engine construction.

The new fixture allowed a metric for a nonexistent company, returning HTTP 201 despite the foreign key declared in the production schema. This was a defect in the test environment, not evidence that PostgreSQL lacked the constraint.

Resolution: a listener scoped to the test engine enables foreign keys on every physical connection before schema creation. Regression tests verify HTTP 400 with no saved row for a missing company, successful persistence for an existing company, and enforcement after replacing the connection. The engine is disposed after teardown.

Developer evidence: two failing cases and one passing case before the fix; all seven tests passed afterwards. Noether independently disabled only the listener in memory and reproduced the two expected failures.

Developer: Linnaeus. Independent reviewer: Noether. Integrated commit: `5f1b2fb`.

## Combined verification

- 537 passing pytest cases, including parameterized unit tests and API tests; six existing deprecation warnings.
- Default Black, isort, and flake8 checks pass for all eight test files.
- Tests use SQLite in memory, deterministic collector fakes, and isolated configuration; no live market provider or private database was used.
- The integrated suite was run in a clean environment from outside the checkout so developer `.env` values were not loaded. See the development journal for the exact command.

## Remaining work

- A pre-existing error-response issue remains for a raw JSON number such as `1e999`: validation prevents persistence, but serializing the error returns HTTP 500. Noether reproduced it in both the original Decimal model and the fixed model. The string form is rejected with HTTP 422. This did not block the reviewed regression fix.
- Legacy FastAPI startup events, Pydantic class-based configuration, and the SQLAlchemy declarative import still produce deprecation warnings. Existing application-wide formatting/import debt remains outside this iteration.
- SQLite checks do not replace PostgreSQL integration tests. The template test checks settings initialization, not database connectivity or browser CORS behavior.
- Startup/lifespan and additional update paths need broader persisted regression coverage; ASGITransport alone does not run lifespan.
- Investor-profile persistence and AI analysis remain future product work, as established by the approved baseline scope.
