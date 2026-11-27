# Yahoo TTM Metrics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `POST /api/v1/data-collection/fetch-financial-metrics` stores a real stock's latest Yahoo ratios as one TTM row, so the stock score covers its four components.

**Architecture:** The collector dates the `info` snapshot with `mostRecentQuarter`. A small mapping module turns `KEY_METRIC_FIELDS` into `financial_metrics` columns. The repository gains one upsert for collected rows that refuses to touch a row from another source. The route ties them together with the same error handling as `fetch-company`.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest (async client fixture), yfinance 1.7 (never called in tests).

**Spec:** `docs/superpowers/specs/2026-11-27-yahoo-ttm-metrics-design.md`

## Global Constraints

- No automated test reaches the network; Yahoo is replaced by `FakeTicker` or a stub collector.
- A missing or non-finite value is stored as `None`, never 0.
- Provider text never appears in a response body or a log line; logs keep the class name only.
- `period_type` is exactly `"ttm"`; `period_end` is `as_of` at 00:00 UTC.
- Units stay Yahoo's: fractions, debt-to-equity in percent.
- Run tests with `env -u DATABASE_URL PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider`.

## Review Focus

- `mostRecentQuarter` as a string, a float, 0, negative, or out of range: `as_of` is `None`, no crash. (Task 1 test.)
- A boolean in a ratio field (`True` is an `int` in Python): stored as `None`. (Task 3 test.)
- Two fetches in the same quarter: still one row, values replaced, `id` unchanged. (Task 2 test.)
- Lowercase ticker in the request (`"aapl"`): finds the stored `AAPL`. (Task 3 test.)
- A collector whose provenance source is not an allowed record source: 502, no row. (Task 3 test.)

---

### Task 1: Date the key-metrics snapshot

**Files:**
- Modify: `app/data_collectors/yahoo_finance.py` (`_load_key_metrics`, new helper)
- Test: `tests/test_yahoo_finance_collector.py`

**Interfaces:**
- Produces: `fetch_key_metrics(ticker).provenance.as_of` is a `date` from `info["mostRecentQuarter"]` or `None`.

- [ ] **Step 1: Write the failing tests**

```python
def test_key_metrics_are_dated_by_the_most_recent_quarter(install_ticker, collector):
    install_ticker(info={"trailingPE": 20.0, "mostRecentQuarter": 1790726400})
    assert collector.fetch_key_metrics("AAPL").provenance.as_of == date(2026, 9, 30)

@pytest.mark.parametrize("raw", [None, "1790726400", 0, -5, True, float("nan"), 10**20])
def test_an_unreadable_most_recent_quarter_leaves_as_of_empty(install_ticker, collector, raw):
    install_ticker(info={"trailingPE": 20.0, "mostRecentQuarter": raw})
    assert collector.fetch_key_metrics("AAPL").provenance.as_of is None
```

(1790726400 is 2026-09-30 00:00 UTC, checked.)

- [ ] **Step 2: Run them, expect FAIL** (`as_of` is `None` for the first test).
- [ ] **Step 3: Implement `_quarter_date(value: Any) -> Optional[date]`** in `yahoo_finance.py`: only a real positive finite number (not `bool`) converts, through `datetime.fromtimestamp(value, timezone.utc).date()`; `OverflowError`, `OSError`, `ValueError` give `None`. Pass it as `self._provenance(as_of=...)` in `_load_key_metrics`.
- [ ] **Step 4: Run the Yahoo collector tests, expect PASS.**
- [ ] **Step 5: Commit** `Date Yahoo key metrics by the most recent quarter (Refs #54)`.

### Task 2: Allowed sources and the collected-row upsert

**Files:**
- Modify: `app/models/database_models.py` (`RECORD_SOURCES`, message), `app/repositories/financial_metrics_repository.py`
- Test: `tests/test_financial_metrics_collected.py` (new), the four tests that match `"manual, demo, or fixture"`

**Interfaces:**
- Produces: `RECORD_SOURCE_YAHOO = "yahoo_finance"`, `RECORD_SOURCE_FAKE = "fake"`.
- Produces: `class CollectedRowConflict(Exception)` and `FinancialMetricsRepository.upsert_collected(company_id: int, period_end: datetime, period_type: str, values: dict, *, record_source: str) -> tuple[FinancialMetricsDB, bool]` (row, created). `values` has keys from `COLLECTED_METRIC_COLUMNS` (Task 3) only; every listed column is set, missing keys to `None`.

- [ ] **Step 1: Write the failing tests** (repository on the test session):
  - create returns `created is True`, `source == "yahoo_finance"`, `period_type == "ttm"`;
  - a second call on the same key with new `pe_ratio` returns `created is False`, same `id`, new value, and a column absent from the second `values` is `None`;
  - a `manual` row on the same key raises `CollectedRowConflict` and stays unchanged;
  - `record_source="stub"` raises `ValueError`;
  - `require_record_source("yahoo_finance")` and `("fake")` pass.
- [ ] **Step 2: Run, expect FAIL** (no `upsert_collected`).
- [ ] **Step 3: Implement.** Add the two constants to `RECORD_SOURCES`; the error message lists all five. Update the four `match=` strings in the existing tests to the new message. `upsert_collected` normalizes `period_end` with `as_utc`, validates the source first, looks up the key, raises `CollectedRowConflict` when the row's source differs, commits, and rolls back and raises `ValueError` on `IntegrityError` like `create`.
- [ ] **Step 4: Run the new file and `tests/test_record_source.py tests/test_fund_attributes_edges.py tests/test_provenance_writes.py`, expect PASS.**
- [ ] **Step 5: Commit** `Upsert collected metric rows without touching manual ones (Refs #54)`.

### Task 3: Mapping, route, docs

**Files:**
- Create: `app/collected_metrics.py`
- Modify: `app/api/data_collection.py` (`fetch_financial_metrics`), `docs/api-demo.md`
- Test: `tests/test_fetch_financial_metrics_api.py` (new)

**Interfaces:**
- Consumes: Task 1 `as_of`; Task 2 `upsert_collected`, `CollectedRowConflict`.
- Produces: `COLLECTED_METRIC_COLUMNS: tuple[str, ...]` (the 12 columns), `SCORE_FIGURES: tuple[str, ...]` (`roe`, `net_margin`, `pe_ratio`, `pb_ratio`, `debt_to_equity`, `current_ratio`, `revenue_growth`), `columns_from_key_metrics(values: dict) -> dict`, `TTM_PERIOD = "ttm"`, `ttm_period_end(as_of: date) -> datetime`.

- [ ] **Step 1: Write the failing route tests** with a stub collector through `client.app.dependency_overrides[get_collector]`, returning `Sourced(values, Provenance(source="yahoo_finance", retrieved_at=..., as_of=date(2026, 9, 30)))`. The company is created first with `POST /api/v1/companies/` (`AAPL`, `STOCK`).
  - full snapshot → 200; body `period_type == "ttm"`, `period_end` starts with `2026-09-30T00:00:00`, `net_margin == profit_margin`, `source == "yahoo_finance"`; then `GET /api/v1/instruments/{id}/score` has coverage label `4 of 4`;
  - request `{"ticker": "aapl"}` works;
  - same quarter twice → one row in `GET /api/v1/financial-metrics/company/{id}`, new values;
  - `as_of=date(2026, 12, 31)` after the first → two rows;
  - a manual TTM row on the same key → 409, unchanged;
  - unknown ticker → 404; an `ETF` company → 400;
  - collector returns `None`, `as_of=None`, or all seven score figures `None` → 404, no row;
  - `pe_ratio` NaN, `roe` `True` → stored `None`;
  - collector raises `ProviderError("secret text")` → 502 `{"detail": "Data provider error"}`, `"secret text"` not in the body or in `caplog.text`;
  - provenance source `"stub"` → 502, no row.
- [ ] **Step 2: Run, expect FAIL** (placeholder returns 200 with a message).
- [ ] **Step 3: Implement** `app/collected_metrics.py` (finite real numbers only, `bool` rejected, `profit_margin` → `net_margin`) and the route, `response_model=FinancialMetrics`. Order: company by ticker (404), type `STOCK` (400), collector call, empty checks (404), upsert (409 on conflict). `ProviderError`, a source `ValueError`, and any other exception → 502 with the fixed detail and the class name in the log, as in `fetch_company_data`.
- [ ] **Step 4: Run the new file and the collector/data-collection tests, expect PASS.**
- [ ] **Step 5: Document** the route in `docs/api-demo.md` (request, the 200 body fields, 400/404/409/502).
- [ ] **Step 6: Commit** `Store a Yahoo TTM metrics snapshot on fetch-financial-metrics (Refs #54, Refs #35)`.

### Task 4: Verify and record

- [ ] Full CI command (`-W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-fail-under=80`); only the known local failures may fail.
- [ ] `black --check`, `isort --check-only`, `flake8` on changed Python files.
- [ ] Manual probe against real Yahoo (AAPL, PKN.WA): fetch-company, fetch-financial-metrics, score shows `4 of 4`.
- [ ] Journal entry and work-state section; commit; push; open the pull request; run the code-reviewer.
