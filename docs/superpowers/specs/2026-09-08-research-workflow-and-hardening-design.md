# Research Workflow And Backend Hardening

## Authorization and scope

The user authorized continuing the full remaining-work list from the baseline review, requested separate implementation and review agents, and supplied the demo-investor preferences below. Work proceeds in independently testable slices on dedicated branches. This design makes that authorized work concrete; it does not reopen approval for already requested bug fixes.

## Outcomes

1. The API returns JSON-safe validation errors, starts through FastAPI lifespan, and preserves documented CRUD status codes.
2. Tests cover real PostgreSQL behavior as well as the fast SQLite suite, with migrations and a disposable local database.
3. Investor profiles are stored, editable, and selected explicitly for analysis.
4. A real AI-provider adapter produces structured, source-referenced research from supplied evidence. Missing credentials never produce a fabricated analysis.
5. Repository-wide formatting/import checks, a continuation snapshot, and documentation support later contributors.

## Existing architecture and boundaries

Keep FastAPI, Pydantic, synchronous SQLAlchemy repositories, and the existing company/financial-metrics endpoints. Add focused profile and analysis modules following the existing schema/repository/router layers. Retain the existing API prefix. The usable surface for this backend iteration is the documented API and Swagger UI; a custom frontend is a separate product surface.

No trading execution, brokerage accounts, automatic web research, or inference of private holdings is part of this iteration. Profiles represent research preferences, not authenticated user accounts; the existing local application has no multi-tenant authentication boundary.

## Backend hardening

- Replace `on_event` startup with an async lifespan context. Preserve the startup-disabled test mode. Database initialization failures must be logged and propagated rather than reporting a healthy startup with a missing critical dependency.
- Provide narrow optional application settings/engine injection where needed to test lifespan and CORS without touching the developer's database.
- Register a RequestValidationError handler that keeps the usual error locations/types/messages but sanitizes non-JSON-safe inputs and context. Overflowing raw JSON numbers must yield HTTP 422 without persistence or exposing internal exceptions.
- Normalize configured CORS origins to actual browser origins, without Pydantic's artificial root-path slash. Test preflight/actual allowed and disallowed origins with credentials.
- Replace class-based Pydantic Config and the deprecated SQLAlchemy declarative import while preserving existing API schemas and finite-number validation.
- Cover partial updates, explicit nulls, URL serialization, uniqueness conflicts, missing records, collector updates, and transaction recovery. Fix defects exposed by those tests, including swallowed HTTPException(404).

## Database and migrations

- PostgreSQL binaries are locally available (Homebrew PostgreSQL 14). Test only a new temporary cluster or a purpose-created CI database, never the user's configured database.
- A local runner creates a temporary cluster and Unix-socket directory, disables TCP listening, creates a test database, runs integration tests, and stops the server in a finally block.
- PostgreSQL tests verify timestamps, unique constraints, foreign keys, cascade behavior, transactions, and migration upgrades. Explicit opt-in is required for externally supplied test DSNs.
- Add a baseline Alembic revision for the two existing tables, then additive revisions for new profile/analysis tables. Document adoption for an existing create_all-managed database; do not automatically stamp or migrate the user's database.
- Keep SQLite tests deterministic and fast. PostgreSQL tests are separately marked and skipped only when their explicit test configuration is absent; the local runner must actually execute them during delivery verification.

## Editable investor profiles

New API: `/api/v1/investor-profiles/` with create/list/get/update/delete, plus an explicit idempotent demo-creation endpoint. An edited demo profile must never be reset by another demo request.

Schema/module contracts:

- `app/models/investor_profile.py`: `InstrumentType`, `InvestmentHorizon`, `RiskTolerance`, `InvestorProfileCreate`, `InvestorProfileUpdate`, `InvestorProfile`.
- `app/models/investor_profile_db.py`: `InvestorProfileDB`, sharing the existing Base.
- `app/repositories/investor_profile_repository.py`: CRUD and `get_or_create_demo()`.
- `app/api/investor_profiles.py`: router; parent integrates its registration in `main.py`.

Profile fields: name, investment horizon, risk tolerance, markets, allowed instruments, excluded instruments, optional research notes, id and timestamps. Use bounded strings/lists and explicit enum values; reject overlapping allowed/excluded instruments. Validate updates against the resulting full profile so partial requests cannot bypass invariants.

Demo preferences come only from the user's explicit statements:

- Horizon: `over_10_years`.
- Risk: `moderate_high`.
- Markets: global scope including Poland, the United States, Europe, and Asia.
- Allowed instruments: stock, bond, etf, etc.
- Excluded direct derivatives: future, cfd, option.

Other profiles can select different horizons, risks, markets, and instruments. Demo preferences must not appear as global restrictions in the analysis logic. No holdings, allocations, or exact return targets are inferred.

## Source-aware AI analysis

New `/api/v1/analyses/` create/list/get surface. Creation selects a stored profile, names the instrument and its type, and supplies bounded evidence items with stable IDs, source names/URLs, observation dates, and excerpts. Evidence is supplied data, not automatically verified by a scraper. No provider call occurs for a missing profile or excluded instrument.

The service snapshots the chosen profile and supplied evidence so later profile edits cannot rewrite historical analysis. It builds provider input from that snapshot, validates the structured result and all referenced source IDs, attaches source metadata/freshness warnings itself, and persists only a successfully validated analysis. Unsupported source references or malformed output fail visibly without a success record.

The report contains a summary, evidence-linked observations and risks, base/upside/downside scenarios, assumptions, thesis-breakers, open questions, and uncertainty. It supports research rather than imperative buy/sell instructions. Evidence text and profile notes are untrusted data and cannot override application rules.

Use a small injectable provider interface and the official OpenAI Python SDK Responses API with structured output. Configure API key/model/timeout/output limit through settings; keep provider calls lazy and bounded. Model configuration remains editable. The documented small-model example is GPT-5.4 Mini, whose official documentation confirms Responses and Structured Outputs support.

Tests inject deterministic fakes and mock provider HTTP behavior. Missing configuration, refusal, timeout, rate limiting, malformed responses, and unknown citations have explicit failure paths. There is no production fake provider or silent fallback. A live paid call is not required to validate the backend contract and must not be claimed without evidence.

## Quality and delivery

- Use TDD for behavioral changes and add focused PostgreSQL/integration checks according to blast radius.
- Align Black and isort through project configuration, with a documented matching line-length policy for flake8; fix real lint findings rather than globally suppressing them.
- Dependency changes are limited to capabilities actually implemented, notably the Responses-capable OpenAI SDK. Record any unresolved installed-versus-pinned mismatch.
- Independent review checks each slice and the integrated result, including profile isolation, migration compatibility, and source validation.
- Update the plan checkboxes, development journal, and `docs/work-state.md` with verified state before any interruption.

## References

- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [GPT-5.4 Mini capabilities](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
