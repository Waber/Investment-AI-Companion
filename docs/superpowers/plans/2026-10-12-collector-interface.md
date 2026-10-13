# Collector interface and offline fake collector (#24, part 1) Implementation Plan

**Spec:** GitHub issue #24 (`gh issue view 24 --comments`), requirements
`docs/product-requirements.md` section 7, US4.2 and section 11 (phase P1).

**Goal:** provider-neutral collector contracts split by capability, a
deterministic offline `FakeCollector`, the Yahoo collector adapted to the
contracts, and a `DATA_COLLECTOR` setting behind the fetch-company
dependency. "No data" (HTTP 404) is separated from "provider error"
(HTTP 502).

**Split of #24 (controller ruling):** this branch is part 1 and its pull
request says "Refs #24", not "Closes". Part 2 is a separate branch: the
TTL cache, rate limit and retry/backoff wrapper tested with a fake clock,
plus uppercase ISO 4217 currency normalization (keep `GBp`). Handed to R1
(#54): `debt_to_assets` from `balance_sheet` (`Total Debt` /
`Total Assets`, latest period) for equities. #18 and #21 are already
closed by PR #49.

## Global Constraints

- Branch `feature/collector-interface-24`. Never commit to `master`, never
  push, never open or merge a pull request.
- Every commit leaves the full suite green.
- TDD: write the failing test first, run it, record RED, then implement
  and record GREEN.
- No automated test reaches the network. No live provider calls.
  Deterministic fakes and stubs only.
- Missing data is `None`, never `0`.
- **Provenance** on every capability result: source name, `as_of` (the
  date the data describes, or `None` when the provider does not say),
  `retrieved_at` (timezone-aware UTC), and a `synthetic` flag.
- **Error contract** for every capability method: return `None` when the
  provider has no data for that ticker; raise `ProviderError` when the
  provider fails (network, rate limit, parse error). Never turn an
  exception into `None`. `ProviderError` must **not** subclass
  `ValueError`, because the fetch-company handler maps `ValueError` to
  HTTP 400.
- **HTTP mapping on fetch-company:** no data → 404 with detail
  `Company with ticker {ticker} not found at the data provider`;
  `ProviderError` → 502 with the fixed detail `Data provider error`,
  logged server-side with the ticker as `%r` and no provider text in the
  body. The existing 502 `Provider returned invalid company data`
  (pydantic `ValidationError`), the 400 for uniqueness, and the generic
  500 stay as they are.
- The Yahoo collector keeps its current yfinance field mapping (same
  output keys, same yfinance fields).
- Shared field-name constants, defined once in
  `app/data_collectors/base.py`:
  - `COMPANY_INFO_FIELDS = ("name", "ticker", "sector", "industry",
    "description", "website", "country", "exchange", "currency",
    "market_cap", "employees", "founded", "logo_url")`
  - `KEY_METRIC_FIELDS = ("pe_ratio", "forward_pe", "pb_ratio",
    "ps_ratio", "ev_ebitda", "ev_revenue", "roe", "roa", "profit_margin",
    "operating_margin", "gross_margin", "revenue_growth",
    "earnings_growth", "earnings_quarterly_growth", "current_ratio",
    "quick_ratio", "debt_to_equity", "debt_to_assets", "dividend_yield",
    "payout_ratio", "dividend_rate", "beta", "52_week_high",
    "52_week_low", "avg_volume", "market_cap")`
  - `FUND_ATTRIBUTE_FIELDS = ("fund_type", "ter", "aum", "aum_currency",
    "issuer", "underlying", "domicile", "distribution_policy")`
- Code and docs are read by a Java developer who is learning Python.
  Docstrings explain the non-obvious Python idioms where they are used:
  `typing.Protocol` (structural typing, compared with a Java interface
  that a class must name in `implements`), `@runtime_checkable` (an
  `isinstance` check only verifies that the method names exist, not their
  signatures), `@dataclass(frozen=True)` (compared with a Java record),
  and `Generic[T]` (compared with Java generics). Match the comment
  density and style of the surrounding modules; no essays.
- Match the typing style of the module you edit (`Optional`, `Dict`,
  `List` from `typing` are used in this code base).
- Commit messages use the repository's prefixes (`feat:`, `fix:`,
  `test:`, `docs:`), are imperative, and end with the trailer line
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Task 1: Collector contracts

**Files:**
- Create: `app/data_collectors/__init__.py` only if the package needs it
  (check how `app/data_collectors` is imported today; do not change
  import behavior for the existing module)
- Create: `app/data_collectors/base.py`
- Create: `tests/test_collector_contracts.py`

**Contents of `base.py`:**
- `ProviderError(Exception)`: raised when a provider fails. Docstring
  states the error contract and why it is not a `ValueError`.
- `Provenance`, `@dataclass(frozen=True)`: `source: str`,
  `retrieved_at: datetime`, `as_of: Optional[date] = None`,
  `synthetic: bool = False`. `__post_init__` rejects a naive
  `retrieved_at` with `ValueError` and stores an aware value converted to
  UTC (use `app/core/utc_datetime.py` helpers if they fit). A blank
  `source` is rejected with `ValueError`.
- `Sourced(Generic[T])`, `@dataclass(frozen=True)`: `value: T`,
  `provenance: Provenance`.
- `PriceBar`, `@dataclass(frozen=True)`: `day: date`,
  `open: Optional[float]`, `high: Optional[float]`, `low: Optional[float]`,
  `close: Optional[float]`, `volume: Optional[int]`.
- The three field-name constants from Global Constraints.
- Capability protocols, each `@runtime_checkable` `typing.Protocol`:
  - `InstrumentLookup.fetch_company_info(self, ticker: str) ->
    Optional[Sourced[Dict[str, Any]]]` (keys: `COMPANY_INFO_FIELDS`)
  - `PriceHistory.fetch_price_history(self, ticker: str,
    period: str = "1y", interval: str = "1d") ->
    Optional[Sourced[List[PriceBar]]]` (bars oldest first)
  - `Fundamentals.fetch_key_metrics(self, ticker: str) ->
    Optional[Sourced[Dict[str, Any]]]` (keys: `KEY_METRIC_FIELDS`)
  - `FundAttributes.fetch_fund_attributes(self, ticker: str) ->
    Optional[Sourced[Dict[str, Any]]]` (keys: `FUND_ATTRIBUTE_FIELDS`)
  A module docstring says a provider may implement only some
  capabilities, and states the error contract.

**Tests (`tests/test_collector_contracts.py`):**
- A naive `retrieved_at` raises `ValueError`; an aware non-UTC value is
  stored as the same instant in UTC; a blank source raises `ValueError`.
- `Provenance`, `Sourced` and `PriceBar` are immutable
  (`dataclasses.FrozenInstanceError`).
- A small stub class with only `fetch_company_info` passes
  `isinstance(stub, InstrumentLookup)` and fails
  `isinstance(stub, PriceHistory)`.
- `ProviderError` is an `Exception` and is not a `ValueError`.
- The three constants contain no duplicates.

## Task 2: Deterministic offline FakeCollector

**Files:**
- Create: `app/data_collectors/fake.py`
- Create: `tests/test_fake_collector.py`

**Behavior:**
- `FakeCollector` implements all four protocols. It never imports
  `yfinance` and never opens a socket.
- **Stocks** are the six companies in `fixtures/demo-v1.json`, read once
  when the collector is built (resolve the path from the module file, not
  from the working directory). Profile values (`name`, `sector`,
  `industry`, `description`, `website`, `country`, `exchange`,
  `currency`) come from the fixture unchanged, so the description keeps
  the `[IAC-DEMO-V1]` marker. Reason: a fake fetch-company refresh of a
  seeded demo row then writes the same values, the `/ui` synthetic badge
  stays (`app/ui/view_models.py` `DEMO_MARKER`), and
  `scripts/seed_demo.py` (line ~307) still recognizes the row. The other
  `COMPANY_INFO_FIELDS` are `None`; `ticker` is the ticker.
- **Funds**, built into `fake.py`, both on exchange `DEMO-XETRA`, currency
  `EUR`, descriptions starting with `[IAC-DEMO-V1]` and saying they are
  synthetic and not market data:
  - `DEMO_ETF_WORLD`: `fund_type="ETF"`, `ter=0.0022`,
    `aum=1250000000`, `aum_currency="EUR"`, `issuer="Demo Issuer"`,
    `underlying="Synthetic World Equity Index"`, `domicile="Ireland"`,
    `distribution_policy="accumulating"`.
  - `DEMO_ETC_GOLD`: `fund_type="ETC"`, `ter=0.0015`, `aum=450000000`,
    `aum_currency="EUR"`, `issuer="Demo Issuer"`,
    `underlying="Physical gold (synthetic)"`, `domicile="Jersey"`,
    `distribution_policy=None` (it does not apply to an ETC).
- Coverage required by the issue: a GPW stock (`DEMO_PL_TECH`,
  `DEMO-WSE`), a US stock (`DEMO_US_GROWTH`), an EU stock
  (`DEMO_DE_INDUSTRY`), one ETF and one ETC, all with price history.
- **Key metrics:** a small hard-coded table for the five stocks that
  have fixture metrics, with plausible values for at least `pe_ratio`,
  `pb_ratio`, `roe`, `profit_margin`, `current_ratio`, `debt_to_equity`,
  `revenue_growth` and `debt_to_assets` (strictly between 0 and 1); every
  other key is `None`. `DEMO_PL_EMPTY` returns `None` (no data). Funds
  return a dict with every key `None`: balance-sheet ratios do not apply
  to funds, so `debt_to_assets` is `None` for the ETF and the ETC.
- **Fund attributes:** the values above for the two funds; `None` for
  stocks.
- **Price history:** daily bars on weekdays (Monday to Friday) ending on
  `FAKE_AS_OF = date(2026, 9, 30)`, oldest first. Supported periods and
  bar counts: `"1mo"`=21, `"3mo"`=63, `"6mo"`=126, `"1y"`=252, `"2y"`=504,
  `"5y"`=1260. Only `interval="1d"` is supported. Any other period or
  interval raises `ValueError` naming the supported values (a caller bug,
  not a provider failure). Prices come from a closed-form formula per
  ticker (a base price, a small drift and a sine wave; no `random`),
  rounded to 4 decimals, with `low <= min(open, close)` and
  `max(open, close) <= high`, all positive. Volume is a positive `int`.
  `DEMO_PL_EMPTY` returns `None`.
- **Provenance:** `source="fake"`, `synthetic=True`, `as_of=FAKE_AS_OF`
  (for history, the last bar's day), and `retrieved_at` from an
  injectable `clock` (`FakeCollector(clock=...)`, default returns
  `FAKE_RETRIEVED_AT = datetime(2026, 9, 30, 18, 0, tzinfo=timezone.utc)`),
  so output is identical across runs.
- Unknown ticker → `None` from every capability. Look up `ticker.upper()`.
- Each call returns fresh dicts and lists, so a caller that mutates a
  result cannot change later results.

**Tests (`tests/test_fake_collector.py`):**
- The collector passes `isinstance` for all four protocols.
- Two separate instances return equal results for every capability and
  every fake ticker (determinism).
- A test-local socket guard (monkeypatch `socket.socket.connect` and
  `socket.create_connection` to fail) proves no connection is attempted
  during a full sweep of every capability and ticker.
- Provenance values, the synthetic flag, and the `[IAC-DEMO-V1]` prefix
  on every description.
- Stock profiles equal the fixture values.
- `debt_to_assets` is in (0, 1) for the five stocks with metrics, `None`
  for the ETF and the ETC; `DEMO_PL_EMPTY` key metrics and history are
  `None`.
- Bar counts per period, weekday-only days, last day `FAKE_AS_OF`, OHLC
  ordering, positivity; unsupported period/interval raises `ValueError`.
- Mutating a returned dict does not change the next result.
- Unknown ticker returns `None` from all four methods.

## Task 3: Yahoo collector on the contracts, and fetch-company on the error contract

**Files:**
- Modify: `app/data_collectors/yahoo_finance.py`
- Modify: `app/api/data_collection.py`
- Modify: `tests/test_yahoo_finance_collector.py` and every test whose
  collector stub returns a plain dict (`tests/test_collection_updates.py`,
  `tests/test_data_collection_api.py`, `tests/test_known_defects.py`,
  `tests/test_provider_data_hygiene.py`, and any other the full suite
  reveals)
- Create, if it removes duplication: a small test helper module (for
  example `tests/collector_stubs.py`) that wraps a dict in `Sourced`

**Yahoo collector:**
- `YahooFinanceCollector(clock=...)` with a default that returns the
  current UTC time. Provenance: `source="yahoo_finance"`, `as_of=None`
  for `info`-based results (Yahoo does not say), `synthetic=False`.
- `fetch_company_info` returns `Sourced[dict]` with the same keys and
  mapping as today.
- `fetch_key_metrics` returns `Sourced[dict]` with the same keys and
  mapping as today, except: `debt_to_assets` is `None` when
  `info.get("quoteType")` is `"ETF"` or `"MUTUALFUND"`, because there
  `totalAssets` is assets under management. Docstring notes that Yahoo
  types ETCs as `EQUITY`, so ETCs stay on the `info` path until the
  app-owned instrument type (#26), and that the `balance_sheet` ratio is
  R1 (#54). Keep the existing NaN/inf/overflow guard.
- New `fetch_price_history(ticker, period, interval)` built on
  `fetch_historical_data`: one `PriceBar` per row (index → `day` as a
  `date`; `Open`/`High`/`Low`/`Close` → floats; `Volume` → int; NaN →
  `None`), oldest first, `as_of` = last bar day. `None` when there is no
  history.
- `fetch_historical_data`, `fetch_financial_statements`, `fetch_news` and
  `fetch_recommendations` keep their current return types (they are
  Yahoo-specific helpers, not protocol methods). In every method, each
  `except Exception: ... return None` becomes: log (ticker as `%r`), then
  `raise ProviderError(...) from exc`. The existing "no data" paths that
  return `None` (empty history, no recommendations) stay `None`.
- Yahoo does not implement `FundAttributes` (that comes with I3 #28 /
  R1 #54); the class docstring lists the capabilities it implements.

**fetch-company (`app/api/data_collection.py`):**
- Reads `result.value` from the collector's `Sourced` result.
- `None` → 404 with the provider-neutral detail from Global Constraints.
- `ProviderError` → 502 `Data provider error`, logged with the ticker as
  `%r`. Catch it before the generic `Exception` handler.
- Keep the dependency function name `get_yahoo_finance_collector` in this
  task (Task 4 replaces it).

**Tests:**
- Stub `yf.Ticker` with monkeypatch as the existing tests do; no network.
- Each Yahoo method raises `ProviderError` when yfinance raises, with the
  original exception as `__cause__`.
- `YahooFinanceCollector` passes `isinstance` for `InstrumentLookup`,
  `PriceHistory` and `Fundamentals`, and fails it for `FundAttributes`.
- Provenance on company info and key metrics; the output key sets equal
  `COMPANY_INFO_FIELDS` and `KEY_METRIC_FIELDS`.
- `quoteType` `"ETF"` and `"MUTUALFUND"` give `debt_to_assets is None`
  even when `totalDebt` and `totalAssets` are present; `"EQUITY"` keeps
  the current ratio.
- Price-bar conversion, including NaN → `None` and an empty frame →
  `None`.
- fetch-company: a stub raising `ProviderError` returns 502 with exactly
  `{"detail": "Data provider error"}`, no row is written, and the log has
  the ticker but not the provider's exception text. A stub returning
  `None` returns 404 with the new detail.
- Existing tests that asserted `None` on an exception, or the old
  "not found on Yahoo Finance" text, are updated deliberately; list each
  one in the report.

## Task 4: DATA_COLLECTOR setting, collector dependency, test network guard, docs

**Files:**
- Modify: `app/core/config.py`
- Modify: `app/api/data_collection.py`
- Modify: `tests/conftest.py`, `tests/test_data_collection_wiring.py`,
  every test that overrides `get_yahoo_finance_collector`
- Create: `tests/test_collector_selection.py`
- Modify: `.env.example`, `docs/demo-data.md` (short usage note), and
  any doc that says fetch-company always calls Yahoo (`grep -rn "Yahoo"
  docs README.md`); `docs/development-journal.md`, `docs/work-state.md`

**Setting:** `DATA_COLLECTOR: Literal["fake", "yahoo"] = "yahoo"` with a
`mode="before"` validator that strips and lowercases a string, so
`" Fake "` works and `"other"` fails settings construction. The default
stays `"yahoo"` so a normal run keeps today's behavior; the one-command
demo (#25) and the tests select `"fake"`. A comment says so.

**Dependency:** replace `get_yahoo_finance_collector` with
`get_collector()`, which reads `settings.DATA_COLLECTOR` at call time and
returns a `FakeCollector` or a `YahooFinanceCollector`. Update every
`dependency_overrides` key in the tests to `get_collector`. No alias for
the old name.

**Test safety net (`tests/conftest.py`):**
- Force `os.environ["DATA_COLLECTOR"] = "fake"` before the app is
  imported (assignment, not `setdefault`, so a developer's shell cannot
  turn tests online), next to the existing `SECRET_KEY` line, with a
  comment.
- An autouse fixture that makes any socket connection to a non-loopback
  address fail the test (cover `socket.socket.connect`,
  `socket.socket.connect_ex` and `socket.create_connection`). Loopback
  addresses and Unix sockets stay allowed. Tests marked `integration`
  are not guarded (they connect to PostgreSQL). Explain this in a
  comment.

**Tests (`tests/test_collector_selection.py`, and the wiring test):**
- `Settings` default is `"yahoo"` (with `DATA_COLLECTOR` removed from the
  environment via monkeypatch); `" Fake "` → `"fake"`; `"other"` fails.
- `get_collector()` returns `FakeCollector` for `"fake"` and
  `YahooFinanceCollector` for `"yahoo"` (monkeypatch
  `settings.DATA_COLLECTOR`).
- End to end with no dependency override: fetch-company for
  `DEMO_PL_TECH` creates the company with the fixture name and the marker
  description; a second call updates the same row (no duplicate); an
  unknown ticker returns 404; a fund ticker creates a row too.
- The network guard blocks a non-loopback connect and allows a loopback
  one (a test that tries `socket.create_connection(("192.0.2.1", 80))`
  expects the guard's failure, not a timeout).

**Docs:** journal entry at the top of `docs/development-journal.md` and a
section at the top of `docs/work-state.md`, in the existing short style.
Record: scope (part 1 of #24), the rulings in this plan (the split, the
`yahoo` default, the demo-v1 fixture as the fake's stock source, funds
with the demo marker, `debt_to_assets` handed to R1 with the fund guard
added now, cache/backoff and currency normalization in part 2), the exact
verification results, AI model (Claude Opus 5.5 via Claude Code, as
controller and implementer; reviewers named by the controller in the
report), time tracking (started 2026-10-12 about 14:40 +0200), and that
account usage was not available in this session. Work-state next action:
"Code Reviewer review of the branch, then open the pull request
(Refs #24); then part 2 of #24, then #25".
