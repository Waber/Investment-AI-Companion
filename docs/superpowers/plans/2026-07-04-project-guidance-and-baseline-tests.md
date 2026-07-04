# Project Guidance And Baseline Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the project guidance contract, a real development journal, baseline tests, and the first schema refactor that makes financial metrics creation reliable.

**Architecture:** Keep the current FastAPI + SQLAlchemy repository structure. Add a small app factory to make tests independent from PostgreSQL startup, use SQLite in-memory for API tests, and align Pydantic/ORM/repository financial metrics fields around the existing database schema.

**Tech Stack:** Python 3.12 local `.venv`, FastAPI, Pydantic v2, SQLAlchemy, pytest, httpx/TestClient, black, isort, flake8.

---

## File Structure

- Create `AGENTS.md` — root agent/developer working agreements adapted from FlightAssistant.
- Create `docs/development-journal.md` — forward-looking journal; `CONVERSATION.md` stays legacy.
- Create `.env.example` — safe environment template.
- Modify `README.md` — align setup, routes, docs, tests, implemented vs planned components.
- Modify `main.py` — add `create_app(init_database_on_startup: bool = True)` while preserving module-level `app`.
- Modify `app/models/financial_metrics.py` — align API model fields to stored DB fields.
- Modify `app/api/financial_metrics.py` — remove manual field mismatch and return aligned model values.
- Modify `app/repositories/financial_metrics_repository.py` — use aligned fields only.
- Modify `app/repositories/company_repository.py` — normalize `HttpUrl` to string before persistence.
- Modify `app/api/data_collection.py` — add collector dependency seam.
- Create `tests/conftest.py` — SQLite test DB and FastAPI dependency overrides.
- Create `tests/test_root_api.py` — root endpoint smoke test.
- Create `tests/test_companies_api.py` — company create/list behavior and website persistence.
- Create `tests/test_financial_metrics_api.py` — financial metrics create behavior.
- Create `tests/test_data_collection_api.py` — fake Yahoo collector endpoint behavior.

## Task 0: Preflight And Branch Safety

**Files:**
- Inspect only: git state

- [ ] **Step 1: Verify branch**

Run:

```bash
git status --short --branch
```

Expected:

```text
## feature/project-guidance-and-baseline-tests
?? .python-version
?? docs/superpowers/plans/
```

If the branch is not `feature/project-guidance-and-baseline-tests`, stop and switch/create the branch before editing.

- [ ] **Step 2: Record unrelated local files**

Confirm `.python-version` is untracked and unrelated to this plan unless the implementation intentionally decides to include it. Do not delete it.

- [ ] **Step 3: Run baseline lint signal before edits**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m black --check app main.py setup_database.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m isort --check-only app main.py setup_database.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m flake8 app main.py setup_database.py
```

Expected: record current results before edits. If there are pre-existing failures, do not broaden the first implementation slice just to fix unrelated style issues; document them and keep final checks at least no worse.

## Commit Safety Checklist

Run this checklist immediately before every commit step in this plan.

Before staging:

```bash
git status --short --branch
git diff -- <files intended for this commit>
```

Requirements:

- Confirm the branch is `feature/project-guidance-and-baseline-tests`.
- Confirm `.python-version` remains untracked unless deliberately included in a documented Python-version decision.
- Stage only the files listed in that task's commit command.
- Do not stage unrelated user changes.

After staging and immediately before `git commit`, run:

```bash
git status --short --branch
git diff --staged
```

Final requirement:

- If `git diff --staged` shows unexpected files or hunks, unstage them before committing.
- Do not commit until the staged diff matches only the intended files and hunks for the current task.

## Task 1: Project Guidance And Documentation

**Files:**
- Create: `AGENTS.md`
- Create: `docs/development-journal.md`
- Create: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Create `AGENTS.md`**

Add root-level rules:

```markdown
# AGENTS.md

## Working Agreements

- Answer in the language used by the user. Keep code, identifiers, and technical documentation in English.
- Explain non-obvious implementation choices clearly enough for a developer still learning this codebase.
- Work on a dedicated branch for non-trivial changes.
- Keep changes focused, testable, and close to existing project patterns.
- Prefer small domain/service boundaries over broad rewrites.
- Do not remove user changes or untracked files unless explicitly requested.

## Journal And Delivery

- Update `docs/development-journal.md` for each delivered iteration.
- Record scope, decisions, verification commands, AI model used, and time tracking.
- For deeper tasks, use PM/Analyst, Engineer, and QA/Reviewer roles or subagents.
- If priorities change, record what is implemented and what remains in the backlog.

## Investment Domain Rules

- This app supports investment research and decision hygiene; it must not present outputs as financial advice.
- Show source, data freshness, assumptions, risks, and uncertainty for market data and AI analysis.
- Prefer scenarios over imperative buy/sell language: base case, upside case, downside case, and thesis-breakers.
- Never infer a private portfolio, risk tolerance, or investment style from unavailable chat history. Use explicit project data or user-provided inputs.
- Keep investor preferences explicit and editable when that feature is implemented.

## Quality Gates

- Add or update tests for behavior changes.
- Do not call live market-data providers in automated tests.
- Use deterministic fakes for external providers.
- Run the relevant pytest suite before claiming completion.
```

- [ ] **Step 2: Create `docs/development-journal.md`**

Seed it with:

```markdown
# Development Journal

`CONVERSATION.md` contains legacy project history. This journal is the forward-looking delivery log for new agentic development.

## 2026-07-04 - Iteration 1 (project guidance and baseline tests)

### Scope
- Add repository-level agent/developer guidance.
- Add baseline automated tests.
- Fix financial metrics schema alignment.
- Add test seams for local API work without live providers.

### Status
- Planned.

### Verification
- Pending implementation.

### AI model
- ChatGPT Codex (GPT-5).

### Time tracking
- Pending final implementation summary; replace this before delivery with the real task window, coordinator effort, and reviewer/developer effort.
```

- [ ] **Step 3: Create `.env.example`**

Use safe placeholders:

```dotenv
DATABASE_URL=postgresql://username:password@localhost:5432/investment_ai
REDIS_URL=redis://localhost:6379/0
ELASTICSEARCH_URL=

OPENAI_API_KEY=
NEWS_API_KEY=
TWITTER_API_KEY=
TWITTER_API_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_TOKEN_SECRET=

DEBUG=True
SECRET_KEY=replace-this-in-local-env
LOG_LEVEL=INFO
BACKEND_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

- [ ] **Step 4: Update `README.md`**

Make it clear:
- API prefix is `/api/v1`.
- `tests/` exists after this iteration.
- Redis, Elasticsearch, OpenAI, news, and social-media integrations are planned/configured unless code exists.
- Run command is `python -m uvicorn main:app --reload`.
- Test command is `.venv/bin/python -m pytest -q`.

- [ ] **Step 5: Commit docs**

First run the Commit Safety Checklist for these files, then commit:

```bash
git add AGENTS.md docs/development-journal.md .env.example README.md
git commit -m "docs: add project guidance and setup notes"
```

## Task 2: Test Harness And App Factory

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_root_api.py`
- Modify: `main.py`

- [ ] **Step 1: Write failing root/app-factory test**

Create `tests/test_root_api.py`:

```python
from fastapi.testclient import TestClient

from main import create_app


def test_root_returns_project_metadata():
    app = create_app(init_database_on_startup=False)
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Welcome to Investment AI Companion API",
        "version": "1.0.0",
        "docs_url": "/docs",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_root_api.py -q -p no:cacheprovider
```

Expected: failure because `main.create_app` does not exist.

- [ ] **Step 3: Implement `create_app` in `main.py`**

Refactor without changing external behavior:

```python
def create_app(init_database_on_startup: bool = True) -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
    )

    if settings.BACKEND_CORS_ORIGINS:
        application.add_middleware(...)

    if init_database_on_startup:
        @application.on_event("startup")
        async def startup_event():
            ...

    @application.get("/")
    async def root():
        return {...}

    @application.get("/api/v1/test-config")
    async def test_config() -> Dict:
        ...

    application.include_router(companies_router, prefix=settings.API_V1_STR)
    application.include_router(financial_metrics_router, prefix=settings.API_V1_STR)
    application.include_router(data_collection_router, prefix=settings.API_V1_STR)
    return application


app = create_app()
```

- [ ] **Step 4: Create SQLite test fixture**

Create `tests/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from main import create_app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app(init_database_on_startup=False)
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_root_api.py -q -p no:cacheprovider
```

Expected: pass.

- [ ] **Step 6: Commit app factory and test harness**

First run the Commit Safety Checklist for these files, then commit:

```bash
git add main.py tests/conftest.py tests/test_root_api.py
git commit -m "test: add app factory and root API baseline"
```

## Task 3: Company API Baseline And Website Persistence

**Files:**
- Create: `tests/test_companies_api.py`
- Modify: `app/repositories/company_repository.py`

- [ ] **Step 1: Write failing company API test**

Create `tests/test_companies_api.py`:

```python
def test_create_and_list_company_persists_website_as_string(client):
    payload = {
        "name": "Acme Corp",
        "ticker": "ACME",
        "sector": "Technology",
        "industry": "Software",
        "website": "https://example.com",
        "country": "USA",
        "exchange": "NASDAQ",
        "currency": "USD",
    }

    create_response = client.post("/api/v1/companies/", json=payload)

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["ticker"] == "ACME"
    assert created["website"] == "https://example.com/"

    list_response = client.get("/api/v1/companies/")

    assert list_response.status_code == 200
    companies = list_response.json()
    assert len(companies) == 1
    assert companies[0]["website"] == "https://example.com/"
```

- [ ] **Step 2: Run test to verify failure if website persistence is broken**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_companies_api.py -q -p no:cacheprovider
```

Expected: fail if SQLAlchemy cannot bind Pydantic `HttpUrl`, or pass if the current environment coerces it. If it passes immediately, add repository-level assertion using SQLite session to prove stored `CompanyDB.website` is a `str`.

- [ ] **Step 3: Normalize website in repository**

In `app/repositories/company_repository.py`, add:

```python
def _serialize_optional_url(value):
    return str(value) if value is not None else None
```

Use it for `website` in `create()` and when `website` appears in `update_data`.

- [ ] **Step 4: Run company tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_companies_api.py -q -p no:cacheprovider
```

Expected: pass.

- [ ] **Step 5: Commit company API baseline**

First run the Commit Safety Checklist for these files, then commit:

```bash
git add app/repositories/company_repository.py tests/test_companies_api.py
git commit -m "test: cover company API persistence"
```

## Task 4: Financial Metrics Schema Alignment

**Files:**
- Create: `tests/test_financial_metrics_api.py`
- Modify: `app/models/financial_metrics.py`
- Modify: `app/api/financial_metrics.py`
- Modify: `app/repositories/financial_metrics_repository.py`

- [ ] **Step 1: Write failing financial metrics API test**

Create `tests/test_financial_metrics_api.py`:

```python
def test_create_financial_metrics_accepts_documented_fields(client):
    company_response = client.post(
        "/api/v1/companies/",
        json={
            "name": "Acme Corp",
            "ticker": "ACME",
            "sector": "Technology",
            "industry": "Software",
            "country": "USA",
            "exchange": "NASDAQ",
            "currency": "USD",
        },
    )
    company_id = company_response.json()["id"]

    metrics_response = client.post(
        "/api/v1/financial-metrics/",
        json={
            "company_id": company_id,
            "period_end": "2024-12-31T00:00:00Z",
            "period_type": "annual",
            "revenue": 1_000_000.0,
            "net_income": 200_000.0,
            "total_assets": 2_000_000.0,
            "total_liabilities": 800_000.0,
            "total_equity": 1_200_000.0,
            "roe": 0.16,
            "roa": 0.10,
            "gross_margin": 0.42,
            "net_margin": 0.20,
            "current_ratio": 2.1,
            "quick_ratio": 1.4,
            "debt_to_equity": 0.67,
            "debt_to_assets": 0.40,
            "asset_turnover": 0.50,
            "inventory_turnover": 5.0,
            "revenue_growth": 0.12,
            "net_income_growth": 0.08,
            "pe_ratio": 25.0,
            "pb_ratio": 6.0,
            "ev_ebitda": 18.0,
        },
    )

    assert metrics_response.status_code == 201
    created = metrics_response.json()
    assert created["company_id"] == company_id
    assert created["revenue"] == 1_000_000.0
    assert created["net_margin"] == 0.20
    assert created["ev_ebitda"] == 18.0
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_financial_metrics_api.py -q -p no:cacheprovider
```

Expected: failure because the Pydantic model/repository/API schema is inconsistent.

- [ ] **Step 3: Align `FinancialMetricsBase`**

In `app/models/financial_metrics.py`, define only stored fields:

```python
class FinancialMetricsBase(BaseModel):
    revenue: Optional[float] = Field(None, description="Revenue")
    net_income: Optional[float] = Field(None, description="Net income")
    total_assets: Optional[float] = Field(None, description="Total assets")
    total_liabilities: Optional[float] = Field(None, description="Total liabilities")
    total_equity: Optional[float] = Field(None, description="Total equity")
    roe: Optional[float] = Field(None, description="Return on Equity")
    roa: Optional[float] = Field(None, description="Return on Assets")
    gross_margin: Optional[float] = Field(None, description="Gross margin")
    net_margin: Optional[float] = Field(None, description="Net margin")
    current_ratio: Optional[float] = Field(None, description="Current ratio")
    quick_ratio: Optional[float] = Field(None, description="Quick ratio")
    debt_to_equity: Optional[float] = Field(None, description="Debt to equity ratio")
    debt_to_assets: Optional[float] = Field(None, description="Debt to assets ratio")
    asset_turnover: Optional[float] = Field(None, description="Asset turnover")
    inventory_turnover: Optional[float] = Field(None, description="Inventory turnover")
    revenue_growth: Optional[float] = Field(None, description="Revenue growth")
    net_income_growth: Optional[float] = Field(None, description="Net income growth")
    pe_ratio: Optional[float] = Field(None, description="Price to Earnings ratio")
    pb_ratio: Optional[float] = Field(None, description="Price to Book ratio")
    ev_ebitda: Optional[float] = Field(None, description="Enterprise Value to EBITDA")
```

- [ ] **Step 4: Align API mapping**

Ensure `db_to_metrics_model()` returns only fields defined by `FinancialMetrics`, including `revenue`, `net_income`, `gross_margin`, and `net_margin`.

- [ ] **Step 5: Run financial metrics tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_financial_metrics_api.py -q -p no:cacheprovider
```

Expected: pass.

- [ ] **Step 6: Commit financial metrics fix**

First run the Commit Safety Checklist for these files, then commit:

```bash
git add app/models/financial_metrics.py app/api/financial_metrics.py app/repositories/financial_metrics_repository.py tests/test_financial_metrics_api.py
git commit -m "fix: align financial metrics schema"
```

## Task 5: Yahoo Collector Dependency Seam

**Files:**
- Create: `tests/test_data_collection_api.py`
- Modify: `app/api/data_collection.py`

- [ ] **Step 1: Write failing fake-collector test**

Create `tests/test_data_collection_api.py`:

```python
from app.api.data_collection import get_yahoo_finance_collector


class FakeYahooFinanceCollector:
    def fetch_company_info(self, ticker):
        return {
            "name": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "description": "Test fixture company",
            "website": "https://www.apple.com",
            "country": "USA",
            "exchange": "NASDAQ",
            "currency": "USD",
        }


def test_fetch_company_uses_injected_collector(client):
    client.app.dependency_overrides[get_yahoo_finance_collector] = (
        lambda: FakeYahooFinanceCollector()
    )

    response = client.post("/api/v1/data-collection/fetch-company", json={"ticker": "aapl"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["company_id"] is not None

    companies_response = client.get("/api/v1/companies/")
    assert companies_response.status_code == 200
    assert companies_response.json()[0]["ticker"] == "AAPL"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_data_collection_api.py -q -p no:cacheprovider
```

Expected: import failure because `get_yahoo_finance_collector` does not exist, or a live-provider call if the seam is missing.

- [ ] **Step 3: Add dependency seam**

In `app/api/data_collection.py`:

```python
def get_yahoo_finance_collector() -> YahooFinanceCollector:
    return YahooFinanceCollector()
```

Update endpoint signature:

```python
def fetch_company_data(
    request: FetchCompanyRequest,
    db: Session = Depends(get_db),
    collector: YahooFinanceCollector = Depends(get_yahoo_finance_collector),
):
```

Remove the local `collector = YahooFinanceCollector()` line.

- [ ] **Step 4: Run data collection test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_data_collection_api.py -q -p no:cacheprovider
```

Expected: pass without calling live Yahoo Finance.

- [ ] **Step 5: Commit collector seam**

First run the Commit Safety Checklist for these files, then commit:

```bash
git add app/api/data_collection.py tests/test_data_collection_api.py
git commit -m "test: add fakeable Yahoo Finance collector seam"
```

## Task 6: Final Verification And Journal

**Files:**
- Modify: `docs/development-journal.md`

- [ ] **Step 1: Run full pytest suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 2: Run formatting/lint checks**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m black --check app main.py setup_database.py tests
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m isort --check-only app main.py setup_database.py tests
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m flake8 app main.py setup_database.py tests
```

Expected: all pass or produce only pre-existing issues documented in the journal.

- [ ] **Step 3: Update journal status**

Update `docs/development-journal.md`:

- Set `Status` to `Delivered`.
- Under `Verification`, paste each actual command line that was run and its observed result, for example `passed`, `failed with <specific pre-existing issue>`, or `not run because <specific reason>`. Do not write abbreviated commands such as ``... pytest ...``.
- Under `AI model`, name the coordinator model and summarize subagent roles actually used.
- Under `Time tracking`, record the actual Europe/Warsaw task window and approximate coordinator/developer/reviewer durations.
- Do not leave angle-bracket placeholders, ellipsis placeholders, "pending", or generic `result` text in the final journal entry.

- [ ] **Step 4: Commit journal update**

First run the Commit Safety Checklist for this file, then commit:

```bash
git add docs/development-journal.md
git commit -m "docs: record baseline test iteration"
```

- [ ] **Step 5: Final code review**

Dispatch a final reviewer with:

- Spec: `docs/superpowers/specs/2026-07-03-project-guidance-and-baseline-tests-design.md`
- Plan: `docs/superpowers/plans/2026-07-04-project-guidance-and-baseline-tests.md`
- Diff range: from `master` to current branch head.

Fix Critical/Important issues before final response.
