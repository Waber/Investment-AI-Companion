# Project Guidance And Baseline Tests Design

## Context

Investment AI Companion is an existing FastAPI application on branch `master`, with SQLAlchemy repositories, PostgreSQL configuration, Alembic scaffolding, and a Yahoo Finance collector. The project has useful historical notes in `CONVERSATION.md`, but it does not yet have an `AGENTS.md` contract, a structured `docs/development-journal.md`, or automated tests.

The current working tree has one unrelated untracked file, `.python-version`, set to `3.12.2`. This iteration will not remove or rewrite it unless it is deliberately included as part of the Python-version decision.

This work is intentionally a foundation iteration. It should make future feature work safer before adding a real AI analysis layer, live scheduler, or broader market-data ingestion.

## Goals

- Add root-level `AGENTS.md` modeled after the FlightAssistant working agreements, adapted to this investment domain.
- Add `docs/development-journal.md` as the forward-looking work journal while keeping `CONVERSATION.md` as legacy history.
- Add a minimal automated test baseline for the existing FastAPI/domain behavior without requiring a local PostgreSQL server.
- Fix the highest-risk schema mismatch around financial metrics.
- Add project documentation needed for reproducible local setup, including `.env.example`.
- Introduce investor-profile guidance that supports the user without pretending to know private ChatGPT history.

## Non-Goals

- Do not implement full OpenAI analysis in this iteration.
- Do not add live trading, portfolio execution, brokerage integrations, or investment recommendations.
- Do not replace Yahoo Finance or build a multi-vendor data platform yet.
- Do not Dockerize the project in this iteration; `DOCKER_INVESTIGATION.md` remains future work.
- Do not rewrite the whole app into a new architecture.

## Approach

Use a small, protective first slice:

1. Establish the project rules and documentation contract.
2. Add tests that reproduce important current behavior and expose the financial metrics mismatch.
3. Align the financial metrics API model, ORM model, and repository mapping.
4. Add small seams where they unlock testing, especially around Yahoo Finance collection.
5. Record verification and team/review notes in the development journal.

This should happen on branch `feature/project-guidance-and-baseline-tests`.

## Project Guidance

Create `AGENTS.md` at the repository root. It should include:

- Answer in the language used by the user; keep code identifiers and code comments in English.
- Explain implementation decisions clearly enough for a developer still learning this codebase.
- Work on dedicated branches for non-trivial tasks.
- Prefer small, testable changes over broad rewrites.
- For deeper tasks, use at least PM/Analyst, Engineer, and QA/Reviewer roles or subagents.
- Update `docs/development-journal.md` for each delivered iteration with scope, decisions, verification, AI model, and time tracking.
- Treat financial outputs as analysis support, not financial advice.
- Always expose data source, data date/freshness, assumptions, risks, and uncertainty.
- Never infer the user's portfolio or risk profile from unavailable private chat history; use explicit project data or user-provided inputs.

## Documentation

Create `docs/development-journal.md` for new work from this iteration onward. Keep `CONVERSATION.md` as historical context, not the primary process log.

Update README where it is inaccurate:

- Keep current stack description aligned with existing files.
- Clarify API prefix `/api/v1`.
- Mention that tests now exist.
- Mention `.env.example`.
- Clarify that Redis, Elasticsearch, OpenAI, news, and Twitter/X are planned/configured assumptions unless implemented by code.

Add `.env.example` with safe placeholders:

- `DATABASE_URL`
- `DEBUG`
- `SECRET_KEY`
- `OPENAI_API_KEY`
- optional service URLs/API keys already supported by settings.

## Test Baseline

Add a `tests/` package using pytest and FastAPI/httpx tooling already listed in `requirements.txt`.

The first tests should avoid requiring a running PostgreSQL instance. Prefer one of these patterns:

- Isolated SQLAlchemy test database using SQLite in-memory with dependency override for `get_db`.
- Pure model/repository tests where the database setup is local to the test.

Required coverage for this iteration:

- Root endpoint returns project metadata.
- Company create/list behavior can be exercised against a test database.
- Financial metrics creation works with fields documented in the API examples.
- Financial metrics schema does not reference fields missing from `FinancialMetricsCreate`.
- Data collection endpoint can be tested with a fake collector rather than live Yahoo Finance.

## Financial Metrics Refactor

The current highest-risk bug is that `FinancialMetricsRepository.create()` reads fields such as `revenue`, `net_income`, `total_assets`, and `gross_margin`, while `FinancialMetricsCreate` does not define them. The model also defines fields not persisted by the ORM, such as `operating_margin`, `cash_ratio`, and `dividend_yield`.

Fix by aligning the first supported schema around fields already present in `FinancialMetricsDB`:

- `company_id`
- `period_end`
- `period_type`
- `revenue`
- `net_income`
- `total_assets`
- `total_liabilities`
- `total_equity`
- `roe`
- `roa`
- `gross_margin`
- `net_margin`
- `current_ratio`
- `quick_ratio`
- `debt_to_equity`
- `debt_to_assets`
- `asset_turnover`
- `inventory_turnover`
- `revenue_growth`
- `net_income_growth`
- `pe_ratio`
- `pb_ratio`
- `ev_ebitda`

Do not add new database columns in this iteration unless required by a failing test and supported by migration planning.

## Testability Seams

Introduce a dependency provider for the Yahoo Finance collector:

- Keep `YahooFinanceCollector` as the production implementation.
- Add a small `get_yahoo_finance_collector()` dependency.
- In tests, override it with a fake collector returning deterministic company data.

Normalize `CompanyCreate.website` at the persistence boundary. Pydantic may hold it as an `HttpUrl`; SQLAlchemy stores it as a string.

## Investor Profile Direction

This app should support an investor who wants structured, risk-aware analysis rather than hype or opaque recommendations.

Initial domain rules:

- Store investor preferences explicitly, not implicitly.
- Make risk tolerance, time horizon, preferred markets, excluded instruments, and thesis style editable later.
- In generated analysis, prefer scenario framing: base case, upside case, downside case, key assumptions, and what would change the thesis.
- Surface valuation, quality, balance sheet, growth, dilution, cyclicality, currency, and data-quality risks.
- Avoid imperative buy/sell language.
- Cite source and freshness for market data when available.

Implementation of a persistent investor profile can wait until the baseline tests and schema refactor are complete.

## Error Handling

For this iteration:

- Preserve existing HTTP status behavior unless a test reveals a clear bug.
- Avoid swallowing unexpected exceptions in ways that hide diagnostics during tests.
- Use stable messages for known validation conflicts.
- Do not call live Yahoo Finance in automated tests.

## Verification

Expected verification after implementation:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m black --check app main.py setup_database.py tests
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m isort --check-only app main.py setup_database.py tests
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m flake8 app main.py setup_database.py tests
```

`mypy` may be run as an additional signal, but existing SQLAlchemy/Pydantic typing may require a separate cleanup pass if it produces broad legacy noise.

## Risks

- The local environment may not have dependencies installed. If `.venv` is absent or stale, dependency installation may require network access and explicit approval.
- SQLite tests can differ from PostgreSQL behavior around constraints and date/time handling. Repository tests should focus on behavior that is portable.
- Tightening config defaults could break local startup if done too aggressively, so config hardening should be limited to documentation and safe defaults in this iteration.
- The untracked `.python-version` should be handled deliberately, not accidentally swept into unrelated commits.
