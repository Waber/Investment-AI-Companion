# Collector guard and currency normalization (#24 part 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** put a TTL cache, a sliding-window rate limit and retries with
full-jitter backoff in front of the Yahoo collector, configurable through
`COLLECTOR_*` settings, and store currency codes in uppercase except
Yahoo's `GBp` and `ZAc`.

**Architecture:** a new module `app/data_collectors/guard.py` holds
`GuardPolicy` (the limits) and `guard_collector(inner, policy, ...)`,
which builds, once per inner class, a class from one mixin per
capability the inner collector has, plus a shared base with the
cache, the rate limit and the retry loop. `get_collector()` returns
one shared guarded Yahoo collector in `yahoo` mode and a bare
`FakeCollector` in `fake` mode. Currency normalization lives in the
existing write-model validator.

**Tech Stack:** Python 3.12, FastAPI, pydantic 2 / pydantic-settings,
pytest with pytest-asyncio, standard library only (`inspect`,
`threading`, `collections`, `copy`, `random`, `time`).

**Spec:** `docs/superpowers/specs/2026-10-13-collector-guard-design.md`

## Global Constraints

- Branch `feature/collector-guard-24`. Never commit to `master`, never
  push, never open or merge a pull request.
- Every commit leaves the full suite green. TDD: write the failing test,
  run it and record RED, implement, run and record GREEN.
- `python` below means the project's Python 3.12 virtualenv; the
  controller gives its path. Full suite (the CI command):
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-fail-under=80`
- No new dependencies. The locks are installed with `--require-hashes`.
- No automated test reaches the network. The autouse `block_network`
  fixture stays on. The root `conftest.py` forces `DATA_COLLECTOR=fake`;
  do not change that.
- Do not change `YahooFinanceCollector`'s provider behavior. Mapping
  yfinance errors to `TransientProviderError` is R1 (#54).
- Error contract (from part 1): a capability returns `None` for no data
  and raises `ProviderError` for a provider failure. fetch-company maps
  `ProviderError` (any subclass) to HTTP 502 `Data provider error`.
  `ProviderError` and `TransientProviderError` are not `ValueError`s.
- The guard never logs the provider's own error text (the inner
  collector already logged it). Tickers in log lines use `%r`.
- Formatting: black and isort at line length 79 (`pyproject.toml`),
  flake8 max-line-length 79 (`setup.cfg`). Scoped check on the files a
  task touches: `python -m black --check <files>`,
  `python -m isort --check-only <files>`, `python -m flake8 <files>`.
- Code comments explain non-obvious Python to a Java developer (AGENTS.md),
  with a Java analogy where one helps. Code, comments and docs in English.
- Commit messages: conventional prefix (`feat:`, `test:`, `docs:`), and
  a `Co-Authored-By:` trailer naming the model that wrote the commit.
  Never put a closing keyword (close, fix, resolve and their forms)
  directly before an issue number; write "Refs #24" or "part 2 of #24".
- The controller writes the journal and work-state entries after the
  final review. Implementers do not edit `docs/development-journal.md`
  or `docs/work-state.md`.

## Review Focus

1. A non-finite float setting (`nan`, `inf`, `-inf` in `.env`) must stop
   startup with a "finite number" error, not build a limiter whose window
   never frees. Test in Task 1.
2. A provider bug that raises something other than `ProviderError` (for
   example `KeyError`) must reach the caller unchanged, not be cached and
   not be retried; the next call reaches the provider again. Test in
   Task 2.
3. When the rate limit is full during a retry, the caller must get a plain
   `ProviderError` (HTTP 502) and the provider must not be called again.
   Test in Task 3.
4. The guard's log lines must name the method and the ticker but never
   contain the provider's error text. Test in Task 3.
5. "No data" cached for one capability must not answer another
   capability for the same ticker (the key includes the method name).
   Test in Task 2.

## File Structure

- `app/data_collectors/base.py` (modify): add `TransientProviderError`.
- `app/core/config.py` (modify): eleven `COLLECTOR_*` settings and one
  cross-field check.
- `app/data_collectors/guard.py` (create): `GuardPolicy`, the guarded
  base class, the capability mixins, `guard_collector`.
- `app/api/data_collection.py` (modify): the shared guarded Yahoo
  collector behind `get_collector()`, and `reset_collector()`.
- `app/models/company.py` (modify): `normalize_currency` and
  `MINOR_UNIT_CURRENCIES`.
- `tests/collector_stubs.py` (modify): shared `FakeClock`,
  `ScriptedLookup`, `SpyCollector`.
- `tests/test_collector_guard_settings.py` (create): settings, policy,
  docs check.
- `tests/test_collector_guard.py` (create): the guard in fake time.
- `tests/test_collector_guard_api.py` (create): fetch-company through
  the guard.
- `tests/conftest.py`, `tests/test_collector_selection.py`,
  `tests/test_provider_data_hygiene.py` (modify).
- `.env.example`, `README.md`, `docs/api-demo.md` (modify).

---

### Task 1: Guard settings, `GuardPolicy` and `TransientProviderError`

**Files:**
- Modify: `app/data_collectors/base.py` (after `class ProviderError`)
- Modify: `app/core/config.py` (imports; after the `DATA_COLLECTOR`
  validator, before `# Logging`)
- Create: `app/data_collectors/guard.py`
- Test: `tests/test_collector_guard_settings.py`

**Interfaces:**
- Consumes: `ProviderError` from `app/data_collectors/base.py`.
- Produces:
  - `class TransientProviderError(ProviderError)` in `base.py`.
  - Settings fields (names, types and defaults exactly as below) on
    `app.core.config.Settings`.
  - `app/data_collectors/guard.py`: `_SETTING_NAMES: Dict[str, str]`
    (GuardPolicy field -> setting name) and
    `@dataclass(frozen=True) class GuardPolicy` with fields
    `ttl_company_info: int = 86400`, `ttl_key_metrics: int = 3600`,
    `ttl_price_history: int = 900`, `ttl_fund_attributes: int = 86400`,
    `cache_max_entries: int = 256`, `rate_limit_calls: int = 30`,
    `rate_limit_period: float = 60.0`,
    `rate_limit_max_wait: float = 5.0`, `max_retries: int = 2`,
    `backoff_base: float = 1.0`, `backoff_max: float = 8.0`, and
    `@classmethod from_settings(cls, settings) -> GuardPolicy`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_collector_guard_settings.py`:

```python
"""COLLECTOR_* settings and the GuardPolicy built from them."""

from dataclasses import fields

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.data_collectors.base import ProviderError, TransientProviderError
from app.data_collectors.guard import _SETTING_NAMES, GuardPolicy

# Every guard setting with its default, as in the spec's table. Float
# settings use float literals: a boundary test converts with this type.
DEFAULTS = {
    "COLLECTOR_CACHE_TTL_COMPANY_INFO_SECONDS": 86400,
    "COLLECTOR_CACHE_TTL_KEY_METRICS_SECONDS": 3600,
    "COLLECTOR_CACHE_TTL_PRICE_HISTORY_SECONDS": 900,
    "COLLECTOR_CACHE_TTL_FUND_ATTRIBUTES_SECONDS": 86400,
    "COLLECTOR_CACHE_MAX_ENTRIES": 256,
    "COLLECTOR_RATE_LIMIT_CALLS": 30,
    "COLLECTOR_RATE_LIMIT_PERIOD_SECONDS": 60.0,
    "COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS": 5.0,
    "COLLECTOR_RETRY_MAX_RETRIES": 2,
    "COLLECTOR_BACKOFF_BASE_SECONDS": 1.0,
    "COLLECTOR_BACKOFF_MAX_SECONDS": 8.0,
}
FLOAT_SETTINGS = [
    "COLLECTOR_RATE_LIMIT_PERIOD_SECONDS",
    "COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS",
    "COLLECTOR_BACKOFF_BASE_SECONDS",
    "COLLECTOR_BACKOFF_MAX_SECONDS",
]


def build_settings(monkeypatch, **env):
    """Settings from the environment only, never from a developer .env.

    A developer shell may export a COLLECTOR_* value, so each one is
    removed first.
    """
    for name in DEFAULTS:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return Settings(_env_file=None)


def test_transient_provider_error_is_a_provider_error():
    assert issubclass(TransientProviderError, ProviderError)
    # Not a ValueError: fetch-company maps ValueError to HTTP 400.
    assert not issubclass(TransientProviderError, ValueError)


def test_guard_settings_have_the_documented_defaults(monkeypatch):
    built = build_settings(monkeypatch)

    for name, default in DEFAULTS.items():
        assert getattr(built, name) == default, name


def test_every_collector_setting_is_listed():
    declared = {
        name for name in Settings.model_fields if name.startswith("COLLECTOR_")
    }

    assert declared == set(DEFAULTS)


def test_every_policy_field_reads_one_setting():
    policy_fields = {field.name for field in fields(GuardPolicy)}

    assert set(_SETTING_NAMES) == policy_fields
    assert set(_SETTING_NAMES.values()) == set(DEFAULTS)


def test_policy_defaults_match_the_setting_defaults(monkeypatch):
    built = build_settings(monkeypatch)

    assert GuardPolicy.from_settings(built) == GuardPolicy()


def test_policy_reads_each_setting(monkeypatch):
    built = build_settings(
        monkeypatch,
        COLLECTOR_CACHE_TTL_COMPANY_INFO_SECONDS="11",
        COLLECTOR_CACHE_TTL_KEY_METRICS_SECONDS="12",
        COLLECTOR_CACHE_TTL_PRICE_HISTORY_SECONDS="13",
        COLLECTOR_CACHE_TTL_FUND_ATTRIBUTES_SECONDS="14",
        COLLECTOR_CACHE_MAX_ENTRIES="15",
        COLLECTOR_RATE_LIMIT_CALLS="16",
        COLLECTOR_RATE_LIMIT_PERIOD_SECONDS="17.5",
        COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS="1.5",
        COLLECTOR_RETRY_MAX_RETRIES="4",
        COLLECTOR_BACKOFF_BASE_SECONDS="0.25",
        COLLECTOR_BACKOFF_MAX_SECONDS="2.5",
    )

    assert GuardPolicy.from_settings(built) == GuardPolicy(
        ttl_company_info=11,
        ttl_key_metrics=12,
        ttl_price_history=13,
        ttl_fund_attributes=14,
        cache_max_entries=15,
        rate_limit_calls=16,
        rate_limit_period=17.5,
        rate_limit_max_wait=1.5,
        max_retries=4,
        backoff_base=0.25,
        backoff_max=2.5,
    )


@pytest.mark.parametrize(
    "name, value",
    [
        ("COLLECTOR_CACHE_TTL_COMPANY_INFO_SECONDS", "-1"),
        ("COLLECTOR_CACHE_TTL_KEY_METRICS_SECONDS", "604801"),
        ("COLLECTOR_CACHE_TTL_PRICE_HISTORY_SECONDS", "-1"),
        ("COLLECTOR_CACHE_TTL_FUND_ATTRIBUTES_SECONDS", "604801"),
        ("COLLECTOR_CACHE_MAX_ENTRIES", "0"),
        ("COLLECTOR_CACHE_MAX_ENTRIES", "10001"),
        ("COLLECTOR_CACHE_MAX_ENTRIES", "1.5"),
        ("COLLECTOR_RATE_LIMIT_CALLS", "0"),
        ("COLLECTOR_RATE_LIMIT_CALLS", "10001"),
        ("COLLECTOR_RATE_LIMIT_PERIOD_SECONDS", "0"),
        ("COLLECTOR_RATE_LIMIT_PERIOD_SECONDS", "3601"),
        ("COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS", "-0.1"),
        ("COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS", "61"),
        ("COLLECTOR_RETRY_MAX_RETRIES", "-1"),
        ("COLLECTOR_RETRY_MAX_RETRIES", "6"),
        ("COLLECTOR_BACKOFF_BASE_SECONDS", "0"),
        ("COLLECTOR_BACKOFF_BASE_SECONDS", "61"),
        ("COLLECTOR_BACKOFF_MAX_SECONDS", "0"),
        ("COLLECTOR_BACKOFF_MAX_SECONDS", "301"),
    ],
)
def test_out_of_range_guard_setting_fails_startup(monkeypatch, name, value):
    with pytest.raises(ValidationError) as excinfo:
        build_settings(monkeypatch, **{name: value})

    assert name in str(excinfo.value)


@pytest.mark.parametrize(
    "name, value",
    [
        ("COLLECTOR_CACHE_TTL_COMPANY_INFO_SECONDS", "0"),
        ("COLLECTOR_CACHE_TTL_COMPANY_INFO_SECONDS", "604800"),
        ("COLLECTOR_CACHE_MAX_ENTRIES", "1"),
        ("COLLECTOR_RATE_LIMIT_CALLS", "1"),
        ("COLLECTOR_RATE_LIMIT_PERIOD_SECONDS", "3600"),
        ("COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS", "0"),
        ("COLLECTOR_RETRY_MAX_RETRIES", "0"),
        ("COLLECTOR_RETRY_MAX_RETRIES", "5"),
        ("COLLECTOR_BACKOFF_MAX_SECONDS", "300"),
    ],
)
def test_boundary_guard_setting_is_accepted(monkeypatch, name, value):
    built = build_settings(monkeypatch, **{name: value})

    assert getattr(built, name) == type(DEFAULTS[name])(value)


@pytest.mark.parametrize("name", FLOAT_SETTINGS)
@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_non_finite_float_setting_fails_startup(monkeypatch, name, value):
    with pytest.raises(ValidationError) as excinfo:
        build_settings(monkeypatch, **{name: value})

    assert "finite" in str(excinfo.value)


def test_backoff_max_below_base_fails_startup(monkeypatch):
    with pytest.raises(ValidationError) as excinfo:
        build_settings(
            monkeypatch,
            COLLECTOR_BACKOFF_BASE_SECONDS="4",
            COLLECTOR_BACKOFF_MAX_SECONDS="3",
        )

    assert "COLLECTOR_BACKOFF_MAX_SECONDS must not be below" in str(
        excinfo.value
    )


def test_backoff_max_equal_to_base_is_accepted(monkeypatch):
    built = build_settings(
        monkeypatch,
        COLLECTOR_BACKOFF_BASE_SECONDS="4",
        COLLECTOR_BACKOFF_MAX_SECONDS="4",
    )

    assert built.COLLECTOR_BACKOFF_MAX_SECONDS == 4.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest -q -p no:cacheprovider tests/test_collector_guard_settings.py`
Expected: collection error, `ImportError: cannot import name 'TransientProviderError'`.

- [ ] **Step 3: Add `TransientProviderError`**

In `app/data_collectors/base.py`, directly after the `ProviderError`
class:

```python
class TransientProviderError(ProviderError):
    """A provider failure that may pass if the same call is repeated.

    Examples: the provider rate-limited us (HTTP 429), or a request
    timed out. The collector guard retries only this error, after a
    backoff delay. A plain ``ProviderError`` (a parse error, a bad
    response) is not retried. Both become HTTP 502 in fetch-company.
    """
```

- [ ] **Step 4: Add the settings**

In `app/core/config.py`, change the pydantic import to:

```python
from pydantic import (
    AnyHttpUrl,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
```

Then insert after the `normalize_data_collector` validator and before
the `# Logging` comment:

```python
    # Limits for the guard in front of the real collector
    # (app/data_collectors/guard.py): a cache, a rate limit and retries.
    # Field(ge=..., le=...) works like Bean Validation @Min/@Max in
    # Java: a value out of range stops startup. Times are in seconds.
    # A cache TTL of 0 turns the cache off for that capability.
    COLLECTOR_CACHE_TTL_COMPANY_INFO_SECONDS: int = Field(
        86400, ge=0, le=604800
    )
    COLLECTOR_CACHE_TTL_KEY_METRICS_SECONDS: int = Field(
        3600, ge=0, le=604800
    )
    COLLECTOR_CACHE_TTL_PRICE_HISTORY_SECONDS: int = Field(
        900, ge=0, le=604800
    )
    COLLECTOR_CACHE_TTL_FUND_ATTRIBUTES_SECONDS: int = Field(
        86400, ge=0, le=604800
    )
    COLLECTOR_CACHE_MAX_ENTRIES: int = Field(256, ge=1, le=10000)
    COLLECTOR_RATE_LIMIT_CALLS: int = Field(30, ge=1, le=10000)
    # allow_inf_nan=False: "nan" or "inf" in .env fails with a clear
    # "finite number" error instead of a confusing range error.
    COLLECTOR_RATE_LIMIT_PERIOD_SECONDS: float = Field(
        60.0, gt=0, le=3600, allow_inf_nan=False
    )
    COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS: float = Field(
        5.0, ge=0, le=60, allow_inf_nan=False
    )
    COLLECTOR_RETRY_MAX_RETRIES: int = Field(2, ge=0, le=5)
    COLLECTOR_BACKOFF_BASE_SECONDS: float = Field(
        1.0, gt=0, le=60, allow_inf_nan=False
    )
    COLLECTOR_BACKOFF_MAX_SECONDS: float = Field(
        8.0, gt=0, le=300, allow_inf_nan=False
    )

    @model_validator(mode="after")
    def backoff_max_is_not_below_base(self) -> "Settings":
        # A model validator sees every field at once, so it can compare
        # two of them. mode="after" runs it on the built object.
        if (
            self.COLLECTOR_BACKOFF_MAX_SECONDS
            < self.COLLECTOR_BACKOFF_BASE_SECONDS
        ):
            raise ValueError(
                "COLLECTOR_BACKOFF_MAX_SECONDS must not be below "
                "COLLECTOR_BACKOFF_BASE_SECONDS"
            )
        return self
```

- [ ] **Step 5: Create `app/data_collectors/guard.py` with the policy**

```python
"""
Cache, rate limit and retry in front of a real market-data collector.

``GuardPolicy`` holds the limits. ``GuardPolicy.from_settings`` builds
it from the ``COLLECTOR_*`` settings, so this module does not import
the settings and a test can pass any policy directly.
"""

from dataclasses import dataclass
from typing import Any

# GuardPolicy field -> Settings attribute. One table, so a new limit is
# added in one place and cannot be read from the wrong setting.
_SETTING_NAMES = {
    "ttl_company_info": "COLLECTOR_CACHE_TTL_COMPANY_INFO_SECONDS",
    "ttl_key_metrics": "COLLECTOR_CACHE_TTL_KEY_METRICS_SECONDS",
    "ttl_price_history": "COLLECTOR_CACHE_TTL_PRICE_HISTORY_SECONDS",
    "ttl_fund_attributes": "COLLECTOR_CACHE_TTL_FUND_ATTRIBUTES_SECONDS",
    "cache_max_entries": "COLLECTOR_CACHE_MAX_ENTRIES",
    "rate_limit_calls": "COLLECTOR_RATE_LIMIT_CALLS",
    "rate_limit_period": "COLLECTOR_RATE_LIMIT_PERIOD_SECONDS",
    "rate_limit_max_wait": "COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS",
    "max_retries": "COLLECTOR_RETRY_MAX_RETRIES",
    "backoff_base": "COLLECTOR_BACKOFF_BASE_SECONDS",
    "backoff_max": "COLLECTOR_BACKOFF_MAX_SECONDS",
}


@dataclass(frozen=True)
class GuardPolicy:
    """Limits for one guarded collector. Times are in seconds.

    The defaults equal the ``COLLECTOR_*`` setting defaults (a test
    checks it), so a test can write ``GuardPolicy(rate_limit_calls=1)``
    and keep every other value realistic. The settings validate the
    ranges; this class trusts what it is given.
    """

    ttl_company_info: int = 86400
    ttl_key_metrics: int = 3600
    ttl_price_history: int = 900
    ttl_fund_attributes: int = 86400
    cache_max_entries: int = 256
    rate_limit_calls: int = 30
    rate_limit_period: float = 60.0
    rate_limit_max_wait: float = 5.0
    max_retries: int = 2
    backoff_base: float = 1.0
    backoff_max: float = 8.0

    @classmethod
    def from_settings(cls, settings: Any) -> "GuardPolicy":
        """Read every limit from the ``COLLECTOR_*`` settings."""
        values = {
            field: getattr(settings, name)
            for field, name in _SETTING_NAMES.items()
        }
        return cls(**values)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest -q -p no:cacheprovider tests/test_collector_guard_settings.py`
Expected: all pass.

- [ ] **Step 7: Run the full suite and the scoped lint**

Run the CI command from Global Constraints. Expected: all pass,
coverage at least 80%. Then black, isort and flake8 on
`app/data_collectors/base.py app/core/config.py app/data_collectors/guard.py tests/test_collector_guard_settings.py`.
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add app/data_collectors/base.py app/core/config.py \
  app/data_collectors/guard.py tests/test_collector_guard_settings.py
git commit -m "feat: add the collector guard settings and policy (#24 part 2)"
```

---

### Task 2: `guard_collector` with capabilities and the TTL cache

**Files:**
- Modify: `app/data_collectors/guard.py`
- Modify: `tests/collector_stubs.py`
- Test: `tests/test_collector_guard.py`

**Interfaces:**
- Consumes: `GuardPolicy` (Task 1); `InstrumentLookup`, `PriceHistory`,
  `Fundamentals`, `FundAttributes`, `PriceBar`, `Sourced` from
  `app/data_collectors/base.py`; `FakeCollector` from
  `app/data_collectors/fake.py`.
- Produces:
  - `GuardPolicy.ttl_for(method_name: str) -> int`.
  - `guard_collector(inner, policy, *, clock=time.monotonic,
    sleep=time.sleep, rand=random.random) -> _GuardedBase`. The result
    has exactly the capability methods of `inner`, plus the read-only
    properties `inner` and `policy`.
  - `_GuardedBase._call_provider(self, method_name, method, bound)`,
    which Task 3 replaces.
  - In `tests/collector_stubs.py`: `FakeClock` (callable; `.now`,
    `.sleeps`, `.sleep(seconds)`, `.advance(seconds)`), `ScriptedLookup(*outcomes)`
    (`.calls: int`, `.tickers: list`), and `SpyCollector()` (a
    `FakeCollector` with `.calls: list[tuple]`).

- [ ] **Step 1: Add the shared test helpers**

Append to `tests/collector_stubs.py` (keep the existing imports and
`sourced`; add `from app.data_collectors.fake import FakeCollector` to
the imports):

```python
class FakeClock:
    """Monotonic time that moves only when a test or ``sleep`` moves it.

    Pass the instance as ``clock`` and its ``sleep`` method as ``sleep``
    to the guard: a "sleep" then records the delay and moves time
    forward instantly, so tests never wait.
    """

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start
        self.sleeps: list = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def advance(self, seconds: float) -> None:
        self.now += seconds


class ScriptedLookup:
    """An ``InstrumentLookup`` only. Each call takes the next outcome.

    An outcome that is an exception instance is raised; anything else
    is returned. A test that runs out of outcomes fails with IndexError.
    """

    def __init__(self, *outcomes: Any) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0
        self.tickers: list = []

    def fetch_company_info(self, ticker):
        self.calls += 1
        self.tickers.append(ticker)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class SpyCollector(FakeCollector):
    """The offline fake, recording every call that reaches it."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list = []

    def fetch_company_info(self, ticker):
        self.calls.append(("fetch_company_info", ticker))
        return super().fetch_company_info(ticker)

    def fetch_key_metrics(self, ticker):
        self.calls.append(("fetch_key_metrics", ticker))
        return super().fetch_key_metrics(ticker)

    def fetch_fund_attributes(self, ticker):
        self.calls.append(("fetch_fund_attributes", ticker))
        return super().fetch_fund_attributes(ticker)

    def fetch_price_history(self, ticker, period="1y", interval="1d"):
        self.calls.append(("fetch_price_history", ticker, period, interval))
        return super().fetch_price_history(ticker, period, interval)
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_collector_guard.py`:

```python
"""The collector guard in fake time: capabilities and the cache."""

import pytest

from app.data_collectors.base import (
    FundAttributes,
    Fundamentals,
    InstrumentLookup,
    PriceHistory,
    ProviderError,
    TransientProviderError,
)
from app.data_collectors.guard import GuardPolicy, guard_collector
from app.data_collectors.yahoo_finance import YahooFinanceCollector
from tests.collector_stubs import (
    STUB_RETRIEVED_AT,
    FakeClock,
    ScriptedLookup,
    SpyCollector,
    sourced,
)

PROTOCOLS = (InstrumentLookup, PriceHistory, Fundamentals, FundAttributes)


def make(inner, clock, rand=lambda: 0.5, **policy):
    """Guard ``inner`` in fake time with ``GuardPolicy(**policy)``."""
    return guard_collector(
        inner,
        GuardPolicy(**policy),
        clock=clock,
        sleep=clock.sleep,
        rand=rand,
    )


def test_guarded_fake_has_every_capability():
    guarded = make(SpyCollector(), FakeClock())

    assert all(isinstance(guarded, protocol) for protocol in PROTOCOLS)


def test_guarded_yahoo_has_no_fund_attributes():
    # Building the Yahoo collector makes no network call.
    guarded = make(YahooFinanceCollector(), FakeClock())

    assert isinstance(guarded, InstrumentLookup)
    assert isinstance(guarded, PriceHistory)
    assert isinstance(guarded, Fundamentals)
    assert not isinstance(guarded, FundAttributes)
    assert not hasattr(guarded, "fetch_fund_attributes")


def test_guarded_lookup_has_only_instrument_lookup():
    guarded = make(ScriptedLookup(), FakeClock())

    assert isinstance(guarded, InstrumentLookup)
    assert not isinstance(guarded, PriceHistory)


def test_guarded_class_is_built_once_per_inner_class():
    first = make(SpyCollector(), FakeClock())
    second = make(SpyCollector(), FakeClock())

    assert type(first) is type(second)
    assert type(first).__name__ == "GuardedSpyCollector"


def test_inner_without_a_capability_is_rejected():
    with pytest.raises(TypeError, match="no collector capability"):
        guard_collector(object(), GuardPolicy())


def test_inner_and_policy_are_exposed():
    inner = SpyCollector()
    policy = GuardPolicy(rate_limit_calls=7)

    guarded = guard_collector(inner, policy)

    assert guarded.inner is inner
    assert guarded.policy is policy


@pytest.mark.parametrize(
    "method, ticker",
    [
        ("fetch_company_info", "DEMO_PL_TECH"),
        ("fetch_key_metrics", "DEMO_PL_TECH"),
        ("fetch_price_history", "DEMO_PL_TECH"),
        ("fetch_fund_attributes", "DEMO_ETF_WORLD"),
    ],
)
def test_repeat_call_is_served_from_the_cache(method, ticker):
    inner = SpyCollector()
    guarded = make(inner, FakeClock())

    first = getattr(guarded, method)(ticker)
    second = getattr(guarded, method)(ticker)

    assert first == second
    assert len(inner.calls) == 1


def test_entry_expires_at_its_ttl():
    inner = SpyCollector()
    clock = FakeClock()
    guarded = make(inner, clock, ttl_company_info=100)

    guarded.fetch_company_info("DEMO_PL_TECH")
    clock.advance(99)
    guarded.fetch_company_info("DEMO_PL_TECH")
    assert len(inner.calls) == 1

    clock.advance(1)
    guarded.fetch_company_info("DEMO_PL_TECH")
    assert len(inner.calls) == 2


def test_each_capability_uses_its_own_ttl():
    inner = SpyCollector()
    clock = FakeClock()
    guarded = make(inner, clock, ttl_company_info=100, ttl_key_metrics=10)
    guarded.fetch_company_info("DEMO_PL_TECH")
    guarded.fetch_key_metrics("DEMO_PL_TECH")

    clock.advance(10)
    guarded.fetch_company_info("DEMO_PL_TECH")
    guarded.fetch_key_metrics("DEMO_PL_TECH")

    assert inner.calls == [
        ("fetch_company_info", "DEMO_PL_TECH"),
        ("fetch_key_metrics", "DEMO_PL_TECH"),
        ("fetch_key_metrics", "DEMO_PL_TECH"),
    ]


def test_ttl_zero_turns_the_cache_off():
    inner = SpyCollector()
    guarded = make(inner, FakeClock(), ttl_company_info=0)

    guarded.fetch_company_info("DEMO_PL_TECH")
    guarded.fetch_company_info("DEMO_PL_TECH")

    assert len(inner.calls) == 2


def test_no_data_is_cached():
    inner = SpyCollector()
    guarded = make(inner, FakeClock())

    assert guarded.fetch_company_info("UNKNOWN") is None
    assert guarded.fetch_company_info("UNKNOWN") is None
    assert len(inner.calls) == 1


def test_no_data_for_one_capability_does_not_answer_another():
    inner = SpyCollector()
    guarded = make(inner, FakeClock())

    guarded.fetch_company_info("UNKNOWN")
    guarded.fetch_key_metrics("UNKNOWN")

    assert inner.calls == [
        ("fetch_company_info", "UNKNOWN"),
        ("fetch_key_metrics", "UNKNOWN"),
    ]


@pytest.mark.parametrize(
    "error", [ProviderError("down"), TransientProviderError("busy")]
)
def test_provider_errors_are_not_cached(error):
    value = sourced({"name": "Acme"})
    inner = ScriptedLookup(error, value)
    # max_retries=0: this test is about the cache, not the retry loop.
    guarded = make(inner, FakeClock(), max_retries=0)

    with pytest.raises(type(error)):
        guarded.fetch_company_info("ACME")
    assert guarded.fetch_company_info("ACME") == value
    assert inner.calls == 2


def test_unexpected_exception_reaches_the_caller_and_is_not_cached():
    value = sourced({"name": "Acme"})
    inner = ScriptedLookup(KeyError("bug"), value)
    guarded = make(inner, FakeClock())

    with pytest.raises(KeyError):
        guarded.fetch_company_info("ACME")
    assert inner.calls == 1
    assert guarded.fetch_company_info("ACME") == value
    assert inner.calls == 2


def test_a_caller_cannot_change_what_the_cache_returns():
    inner = SpyCollector()
    guarded = make(inner, FakeClock())

    first = guarded.fetch_company_info("DEMO_PL_TECH")
    original = first.value["name"]
    first.value["name"] = "changed by the first caller"
    second = guarded.fetch_company_info("DEMO_PL_TECH")
    second.value["name"] = "changed by the second caller"
    third = guarded.fetch_company_info("DEMO_PL_TECH")

    assert third.value["name"] == original
    assert len(inner.calls) == 1


def test_cache_hit_keeps_the_original_retrieval_time():
    clock = FakeClock()
    inner = ScriptedLookup(sourced({"name": "Acme"}))
    guarded = make(inner, clock)
    guarded.fetch_company_info("ACME")

    clock.advance(3600)
    hit = guarded.fetch_company_info("ACME")

    assert hit.provenance.retrieved_at == STUB_RETRIEVED_AT


def test_least_recently_used_entry_is_evicted():
    inner = SpyCollector()
    guarded = make(inner, FakeClock(), cache_max_entries=2)
    guarded.fetch_company_info("DEMO_PL_TECH")
    guarded.fetch_company_info("DEMO_US_GROWTH")
    # A hit makes DEMO_PL_TECH the most recently used entry.
    guarded.fetch_company_info("DEMO_PL_TECH")
    guarded.fetch_company_info("DEMO_DE_INDUSTRY")  # evicts DEMO_US_GROWTH
    inner.calls.clear()

    guarded.fetch_company_info("DEMO_PL_TECH")
    guarded.fetch_company_info("DEMO_US_GROWTH")

    assert inner.calls == [("fetch_company_info", "DEMO_US_GROWTH")]


def test_keyword_positional_and_default_arguments_share_an_entry():
    inner = SpyCollector()
    guarded = make(inner, FakeClock())

    guarded.fetch_price_history("DEMO_PL_TECH")
    guarded.fetch_price_history("DEMO_PL_TECH", "1y")
    guarded.fetch_price_history("DEMO_PL_TECH", period="1y", interval="1d")
    guarded.fetch_price_history("DEMO_PL_TECH", period="1mo")

    assert inner.calls == [
        ("fetch_price_history", "DEMO_PL_TECH", "1y", "1d"),
        ("fetch_price_history", "DEMO_PL_TECH", "1mo", "1d"),
    ]


def test_unhashable_argument_skips_the_cache():
    value = sourced({"name": "Acme"})
    inner = ScriptedLookup(value, value)
    guarded = make(inner, FakeClock())

    guarded.fetch_company_info(["ACME"])
    guarded.fetch_company_info(["ACME"])

    assert inner.calls == 2
```

The demo tickers come from `fixtures/demo-v1.json` (`DEMO_PL_TECH`,
`DEMO_US_GROWTH`, `DEMO_DE_INDUSTRY`) and the fake's funds
(`DEMO_ETF_WORLD`). `UNKNOWN` is in neither.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest -q -p no:cacheprovider tests/test_collector_guard.py`
Expected: collection error, `ImportError: cannot import name 'guard_collector'`.

- [ ] **Step 4: Write the guard**

Replace the whole of `app/data_collectors/guard.py` with:

```python
"""
Cache, rate limit and retry in front of a real market-data collector.

``guard_collector(inner, policy)`` returns an object that has the same
capability methods as ``inner``, and only those. A call first looks in
a TTL cache, so a repeat call within the TTL does not reach the
provider. A cache miss calls the provider through ``_call_provider``.

Java analogy: the returned object is like
``java.lang.reflect.Proxy.newProxyInstance`` given only the interfaces
the target implements. A collector without ``fetch_fund_attributes``
gives a guarded object that is not a ``FundAttributes`` either.

The clock, ``sleep`` and the random source are parameters, so tests
run in fake time and never sleep. ``GuardPolicy`` holds the limits.
``GuardPolicy.from_settings`` builds it from the ``COLLECTOR_*``
settings, so this module does not import the settings and a test can
pass any policy directly.
"""

import copy
import inspect
import logging
import random
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Dict, Hashable, List, Optional, Tuple

from app.data_collectors.base import (
    FundAttributes,
    Fundamentals,
    InstrumentLookup,
    PriceBar,
    PriceHistory,
    Sourced,
)

logger = logging.getLogger(__name__)

# GuardPolicy field -> Settings attribute. One table, so a new limit is
# added in one place and cannot be read from the wrong setting.
_SETTING_NAMES = {
    "ttl_company_info": "COLLECTOR_CACHE_TTL_COMPANY_INFO_SECONDS",
    "ttl_key_metrics": "COLLECTOR_CACHE_TTL_KEY_METRICS_SECONDS",
    "ttl_price_history": "COLLECTOR_CACHE_TTL_PRICE_HISTORY_SECONDS",
    "ttl_fund_attributes": "COLLECTOR_CACHE_TTL_FUND_ATTRIBUTES_SECONDS",
    "cache_max_entries": "COLLECTOR_CACHE_MAX_ENTRIES",
    "rate_limit_calls": "COLLECTOR_RATE_LIMIT_CALLS",
    "rate_limit_period": "COLLECTOR_RATE_LIMIT_PERIOD_SECONDS",
    "rate_limit_max_wait": "COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS",
    "max_retries": "COLLECTOR_RETRY_MAX_RETRIES",
    "backoff_base": "COLLECTOR_BACKOFF_BASE_SECONDS",
    "backoff_max": "COLLECTOR_BACKOFF_MAX_SECONDS",
}

# Capability method -> the GuardPolicy field with its cache TTL.
_TTL_FIELDS = {
    "fetch_company_info": "ttl_company_info",
    "fetch_key_metrics": "ttl_key_metrics",
    "fetch_price_history": "ttl_price_history",
    "fetch_fund_attributes": "ttl_fund_attributes",
}


@dataclass(frozen=True)
class GuardPolicy:
    """Limits for one guarded collector. Times are in seconds.

    The defaults equal the ``COLLECTOR_*`` setting defaults (a test
    checks it), so a test can write ``GuardPolicy(rate_limit_calls=1)``
    and keep every other value realistic. The settings validate the
    ranges; this class trusts what it is given.
    """

    ttl_company_info: int = 86400
    ttl_key_metrics: int = 3600
    ttl_price_history: int = 900
    ttl_fund_attributes: int = 86400
    cache_max_entries: int = 256
    rate_limit_calls: int = 30
    rate_limit_period: float = 60.0
    rate_limit_max_wait: float = 5.0
    max_retries: int = 2
    backoff_base: float = 1.0
    backoff_max: float = 8.0

    @classmethod
    def from_settings(cls, settings: Any) -> "GuardPolicy":
        """Read every limit from the ``COLLECTOR_*`` settings."""
        values = {
            field: getattr(settings, name)
            for field, name in _SETTING_NAMES.items()
        }
        return cls(**values)

    def ttl_for(self, method_name: str) -> int:
        """Cache TTL in seconds for one capability method."""
        return getattr(self, _TTL_FIELDS[method_name])


def _cache_key(
    method_name: str, arguments: Dict[str, Any]
) -> Optional[Hashable]:
    """``(method, ((name, value), ...))``, or None when not hashable."""
    key = (method_name, tuple(arguments.items()))
    try:
        hash(key)
    except TypeError:
        # A list or dict argument. Capability arguments are strings, so
        # this is defensive: the call still works, it skips the cache.
        return None
    return key


class _GuardedBase:
    """The guarded call path shared by every guarded collector.

    The capability mixins below add the public ``fetch_*`` methods;
    each one calls ``_guarded``. ``guard_collector`` combines this
    class with the mixins the inner collector supports.
    """

    def __init__(
        self,
        inner: Any,
        policy: GuardPolicy,
        clock: Callable[[], float],
        sleep: Callable[[float], None],
        rand: Callable[[], float],
    ) -> None:
        self._inner = inner
        self._policy = policy
        self._clock = clock
        self._sleep = sleep
        self._rand = rand
        # FastAPI runs sync endpoints in a thread pool, so two requests
        # can use this object at once. The lock guards the cache. It is
        # never held while the provider is called, so one slow call does
        # not block cache hits for other requests.
        self._lock = threading.Lock()
        # Key -> (expires_at, value). OrderedDict keeps the least
        # recently used entry first, like Java's LinkedHashMap in
        # access order.
        self._cache: OrderedDict[Hashable, Tuple[float, Any]] = OrderedDict()

    @property
    def inner(self) -> Any:
        """The collector this guard calls on a cache miss."""
        return self._inner

    @property
    def policy(self) -> GuardPolicy:
        """The limits this guard applies."""
        return self._policy

    def _guarded(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        method = getattr(self._inner, method_name)
        # bind() maps the arguments to the inner method's parameters and
        # apply_defaults() fills in the rest, so fetch_price_history("X")
        # and fetch_price_history("X", period="1y") get the same key.
        bound = inspect.signature(method).bind(*args, **kwargs)
        bound.apply_defaults()
        ticker = bound.arguments.get("ticker")
        key = _cache_key(method_name, bound.arguments)
        ttl = self._policy.ttl_for(method_name)
        use_cache = key is not None and ttl > 0
        if use_cache:
            hit, value = self._cache_get(key)
            if hit:
                logger.debug("Cache hit for %s %r", method_name, ticker)
                return value
        result = self._call_provider(method_name, method, bound)
        if use_cache:
            self._cache_put(key, result, ttl)
        return result

    def _call_provider(
        self,
        method_name: str,
        method: Callable[..., Any],
        bound: inspect.BoundArguments,
    ) -> Any:
        """Call the provider once with the bound arguments."""
        return method(*bound.args, **bound.kwargs)

    def _cache_get(self, key: Hashable) -> Tuple[bool, Any]:
        """``(True, copy)`` for a live entry, ``(False, None)`` otherwise.

        A flag is needed because ``None`` ("no data") is a valid cached
        value. Expired entries are removed when found.
        """
        now = self._clock()
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False, None
            expires_at, value = entry
            if now >= expires_at:
                del self._cache[key]
                return False, None
            self._cache.move_to_end(key)
        # Deep copy: Sourced is frozen, but its dict value is not. A
        # caller that edits its result must not change the next hit.
        # The stored value is never mutated, so copying outside the
        # lock is safe.
        return True, copy.deepcopy(value)

    def _cache_put(self, key: Hashable, value: Any, ttl: int) -> None:
        stored = copy.deepcopy(value)
        expires_at = self._clock() + ttl
        with self._lock:
            self._cache[key] = (expires_at, stored)
            self._cache.move_to_end(key)
            while len(self._cache) > self._policy.cache_max_entries:
                self._cache.popitem(last=False)


# One mixin per capability protocol. Each adds one explicit method with
# the protocol's signature. Explicit methods (not __getattr__) matter:
# since Python 3.12, isinstance() against a runtime_checkable protocol
# looks methods up with inspect.getattr_static, which does not see
# attributes served by __getattr__.


class _GuardedInstrumentLookup:
    def fetch_company_info(
        self, ticker: str
    ) -> Optional[Sourced[Dict[str, Any]]]:
        return self._guarded("fetch_company_info", ticker)


class _GuardedPriceHistory:
    def fetch_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> Optional[Sourced[List[PriceBar]]]:
        return self._guarded(
            "fetch_price_history", ticker, period=period, interval=interval
        )


class _GuardedFundamentals:
    def fetch_key_metrics(
        self, ticker: str
    ) -> Optional[Sourced[Dict[str, Any]]]:
        return self._guarded("fetch_key_metrics", ticker)


class _GuardedFundAttributes:
    def fetch_fund_attributes(
        self, ticker: str
    ) -> Optional[Sourced[Dict[str, Any]]]:
        return self._guarded("fetch_fund_attributes", ticker)


# Protocol -> the mixin that adds its guarded method.
_CAPABILITY_MIXINS = (
    (InstrumentLookup, _GuardedInstrumentLookup),
    (PriceHistory, _GuardedPriceHistory),
    (Fundamentals, _GuardedFundamentals),
    (FundAttributes, _GuardedFundAttributes),
)


@lru_cache(maxsize=None)
def _guarded_class(inner_class: type) -> type:
    """Build, once per inner class, a class with the matching mixins.

    ``type(name, bases, namespace)`` creates a class at runtime, the
    same as a ``class`` statement. ``issubclass`` against a
    ``runtime_checkable`` protocol checks that the methods exist.
    ``lru_cache`` keeps one built class per inner class.
    """
    mixins = tuple(
        mixin
        for protocol, mixin in _CAPABILITY_MIXINS
        if issubclass(inner_class, protocol)
    )
    if not mixins:
        raise TypeError(
            f"{inner_class.__name__} implements no collector capability"
        )
    name = f"Guarded{inner_class.__name__}"
    return type(name, (*mixins, _GuardedBase), {})


def guard_collector(
    inner: Any,
    policy: GuardPolicy,
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    rand: Callable[[], float] = random.random,
) -> _GuardedBase:
    """Wrap ``inner`` in the cache, rate limit and retries of ``policy``.

    ``clock`` is monotonic seconds, not wall time: it measures TTLs and
    the rate-limit window, and it does not touch provenance
    (``retrieved_at`` still comes from the inner collector). ``rand``
    returns a float in [0, 1) for the backoff jitter; it is not used
    for anything secret.
    """
    return _guarded_class(type(inner))(inner, policy, clock, sleep, rand)
```

`sleep` and `rand` are stored now and used by Task 3.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest -q -p no:cacheprovider tests/test_collector_guard.py tests/test_collector_guard_settings.py`
Expected: all pass.

- [ ] **Step 6: Run the full suite and the scoped lint**

Run the CI command. Expected: all pass. Lint
`app/data_collectors/guard.py tests/collector_stubs.py tests/test_collector_guard.py`.
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add app/data_collectors/guard.py tests/collector_stubs.py \
  tests/test_collector_guard.py
git commit -m "feat: add the collector guard with capabilities and a TTL cache"
```

---

### Task 3: Rate limit and retry with backoff

**Files:**
- Modify: `app/data_collectors/guard.py`
- Test: `tests/test_collector_guard.py` (append)

**Interfaces:**
- Consumes: `_GuardedBase` and `guard_collector` (Task 2),
  `ProviderError` and `TransientProviderError` (Task 1), `FakeClock`,
  `ScriptedLookup` (Task 2).
- Produces: `_GuardedBase._call_provider` with the rate limit and the
  retry loop; `_GuardedBase._acquire_slot(method_name, ticker)`;
  `_GuardedBase._backoff_delay(retry) -> float`. The public interface
  of `guard_collector` does not change.

- [ ] **Step 1: Write the failing tests**

Add `import logging` and `import threading` to the imports at the top
of `tests/test_collector_guard.py`, then append:

```python
class CountingLookup:
    """A thread-safe ``InstrumentLookup`` that counts its calls."""

    def __init__(self):
        self.calls = 0
        self._lock = threading.Lock()

    def fetch_company_info(self, ticker):
        with self._lock:
            self.calls += 1
        return sourced({"name": ticker})


def test_calls_within_the_limit_do_not_wait():
    clock = FakeClock()
    inner = CountingLookup()
    guarded = make(inner, clock, rate_limit_calls=3)

    for ticker in ("A", "B", "C"):
        guarded.fetch_company_info(ticker)

    assert inner.calls == 3
    assert clock.sleeps == []


def test_call_over_the_limit_waits_for_the_oldest_slot():
    clock = FakeClock()
    inner = CountingLookup()
    guarded = make(
        inner,
        clock,
        rate_limit_calls=2,
        rate_limit_period=60,
        rate_limit_max_wait=60,
    )
    guarded.fetch_company_info("A")
    clock.advance(10)
    guarded.fetch_company_info("B")

    guarded.fetch_company_info("C")

    # The first call leaves the 60 s window 50 s later.
    assert clock.sleeps == [50.0]
    assert inner.calls == 3


def test_slot_frees_after_the_period():
    clock = FakeClock()
    inner = CountingLookup()
    guarded = make(inner, clock, rate_limit_calls=1, rate_limit_period=60)
    guarded.fetch_company_info("A")

    clock.advance(60)
    guarded.fetch_company_info("B")

    assert clock.sleeps == []
    assert inner.calls == 2


def test_wait_longer_than_the_max_fails_without_calling_the_provider():
    clock = FakeClock()
    inner = CountingLookup()
    guarded = make(
        inner,
        clock,
        rate_limit_calls=1,
        rate_limit_period=60,
        rate_limit_max_wait=5,
    )
    guarded.fetch_company_info("A")

    with pytest.raises(ProviderError) as excinfo:
        guarded.fetch_company_info("B")

    assert type(excinfo.value) is ProviderError
    assert inner.calls == 1
    assert clock.sleeps == []


def test_max_wait_zero_fails_at_once():
    clock = FakeClock()
    inner = CountingLookup()
    guarded = make(inner, clock, rate_limit_calls=1, rate_limit_max_wait=0)
    guarded.fetch_company_info("A")

    with pytest.raises(ProviderError):
        guarded.fetch_company_info("B")
    assert clock.sleeps == []


def test_cache_hits_take_no_slot():
    clock = FakeClock()
    inner = CountingLookup()
    guarded = make(inner, clock, rate_limit_calls=1, rate_limit_max_wait=0)

    for _ in range(5):
        guarded.fetch_company_info("A")

    assert inner.calls == 1


def test_transient_error_is_retried_after_a_jittered_delay():
    clock = FakeClock()
    value = sourced({"name": "Acme"})
    inner = ScriptedLookup(TransientProviderError("busy"), value)
    guarded = make(inner, clock, rand=lambda: 0.5, backoff_base=1)

    assert guarded.fetch_company_info("ACME") == value
    assert inner.calls == 2
    # Retry 1: 0.5 * min(8, 1 * 2**0).
    assert clock.sleeps == [0.5]


def test_backoff_grows_and_is_capped():
    clock = FakeClock()
    value = sourced({"name": "Acme"})
    busy = TransientProviderError("busy")
    inner = ScriptedLookup(busy, busy, busy, value)
    guarded = make(
        inner,
        clock,
        rand=lambda: 0.5,
        max_retries=3,
        backoff_base=1,
        backoff_max=3,
    )

    guarded.fetch_company_info("ACME")

    # Ceilings 1, 2, then min(3, 4) = 3, each times 0.5.
    assert clock.sleeps == [0.5, 1.0, 1.5]


def test_exhausted_retries_reraise_the_last_transient_error():
    clock = FakeClock()
    inner = ScriptedLookup(
        TransientProviderError("first"),
        TransientProviderError("second"),
        TransientProviderError("third"),
    )
    guarded = make(inner, clock, max_retries=2)

    with pytest.raises(TransientProviderError, match="third"):
        guarded.fetch_company_info("ACME")
    assert inner.calls == 3
    assert len(clock.sleeps) == 2


def test_plain_provider_error_is_not_retried():
    clock = FakeClock()
    inner = ScriptedLookup(ProviderError("bad response"))
    guarded = make(inner, clock)

    with pytest.raises(ProviderError):
        guarded.fetch_company_info("ACME")
    assert inner.calls == 1
    assert clock.sleeps == []


def test_each_retry_takes_a_rate_limit_slot():
    clock = FakeClock()
    value = sourced({"name": "Acme"})
    busy = TransientProviderError("busy")
    inner = ScriptedLookup(busy, busy, value)
    guarded = make(
        inner,
        clock,
        rand=lambda: 0.0,
        rate_limit_calls=2,
        rate_limit_period=60,
        rate_limit_max_wait=60,
    )

    assert guarded.fetch_company_info("ACME") == value
    # Two zero backoffs, then the third attempt waits for a slot.
    assert clock.sleeps == [0.0, 0.0, 60.0]
    assert inner.calls == 3


def test_full_rate_limit_during_a_retry_is_a_plain_provider_error():
    clock = FakeClock()
    inner = ScriptedLookup(
        TransientProviderError("busy"), sourced({"name": "Acme"})
    )
    guarded = make(
        inner,
        clock,
        rand=lambda: 0.0,
        rate_limit_calls=1,
        rate_limit_max_wait=0,
    )

    with pytest.raises(ProviderError) as excinfo:
        guarded.fetch_company_info("ACME")

    assert type(excinfo.value) is ProviderError
    assert inner.calls == 1


def test_guard_logs_name_the_ticker_but_never_the_provider_text(caplog):
    caplog.set_level(logging.DEBUG, logger="app.data_collectors.guard")
    clock = FakeClock()
    inner = ScriptedLookup(
        TransientProviderError("provider secret text"),
        sourced({"name": "Acme"}),
    )
    guarded = make(
        inner,
        clock,
        rand=lambda: 0.0,
        rate_limit_calls=1,
        rate_limit_max_wait=0,
    )

    with pytest.raises(ProviderError):
        guarded.fetch_company_info("ACME")

    assert "provider secret text" not in caplog.text
    assert "retry 1 of 2" in caplog.text
    assert "Rate limit reached" in caplog.text
    assert "'ACME'" in caplog.text


def test_threads_never_exceed_the_rate_limit():
    clock = FakeClock()
    inner = CountingLookup()
    guarded = make(inner, clock, rate_limit_calls=3, rate_limit_max_wait=0)
    barrier = threading.Barrier(10)
    outcomes = []

    def worker(number):
        barrier.wait()
        try:
            guarded.fetch_company_info(f"T{number}")
            outcomes.append("ok")
        except ProviderError:
            outcomes.append("limited")

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert outcomes.count("ok") == 3
    assert outcomes.count("limited") == 7
    assert inner.calls == 3


def test_lock_is_not_held_during_the_provider_call():
    seen = []

    class LockProbe:
        def fetch_company_info(self, ticker):
            seen.append(guarded._lock.locked())
            return sourced({"name": ticker})

    guarded = make(LockProbe(), FakeClock())

    guarded.fetch_company_info("ACME")

    assert seen == [False]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest -q -p no:cacheprovider tests/test_collector_guard.py`
Expected: most new tests FAIL (no waiting, no retries yet).
`test_cache_hits_take_no_slot` and
`test_lock_is_not_held_during_the_provider_call` may already pass; they
pin behavior Task 3 must keep. The Task 2 tests still pass.

- [ ] **Step 3: Add the rate limit and the retry loop**

In `app/data_collectors/guard.py`:

1. Change `from collections import OrderedDict` to
   `from collections import OrderedDict, deque`, add `Deque` to the
   `typing` import, and add `ProviderError` and
   `TransientProviderError` to the `app.data_collectors.base` import.
2. Replace the last paragraph of the module docstring
   ("A cache miss calls the provider through ``_call_provider``.") so
   the first paragraph ends with:

```
provider. A cache miss takes a slot in a sliding-window rate limit and
calls the provider. A ``TransientProviderError`` is retried after an
exponential backoff with full jitter; after the last retry it reaches
the caller.
```

3. In `_GuardedBase.__init__`, replace the lock comment and add the
   call-time deque, so the end of `__init__` reads:

```python
        # FastAPI runs sync endpoints in a thread pool, so two requests
        # can use this object at once. The lock guards the cache and the
        # rate-limit window. It is never held while the provider is
        # called or while sleeping, so one slow call does not block
        # other requests.
        self._lock = threading.Lock()
        # Key -> (expires_at, value). OrderedDict keeps the least
        # recently used entry first, like Java's LinkedHashMap in
        # access order.
        self._cache: OrderedDict[Hashable, Tuple[float, Any]] = OrderedDict()
        # Start times of the provider calls in the current window,
        # oldest first. A deque is a double-ended queue (ArrayDeque).
        self._calls: Deque[float] = deque()
```

4. Replace `_call_provider` with the three methods below:

```python
    def _call_provider(
        self,
        method_name: str,
        method: Callable[..., Any],
        bound: inspect.BoundArguments,
    ) -> Any:
        """Call the provider under the rate limit, retrying if transient.

        Only ``TransientProviderError`` is retried, after a backoff
        delay. Every attempt takes its own rate-limit slot. Any other
        exception, and the last transient one, reaches the caller.
        """
        ticker = bound.arguments.get("ticker")
        retries = self._policy.max_retries
        attempt = 1
        while True:
            self._acquire_slot(method_name, ticker)
            try:
                return method(*bound.args, **bound.kwargs)
            except TransientProviderError:
                if attempt > retries:
                    raise
                delay = self._backoff_delay(attempt)
                # The inner collector logged the provider's own text.
                # This line names only the method and the ticker.
                logger.warning(
                    "Transient provider error in %s for %r; "
                    "retry %d of %d in %.2f s",
                    method_name,
                    ticker,
                    attempt,
                    retries,
                    delay,
                )
                self._sleep(delay)
                attempt += 1

    def _acquire_slot(self, method_name: str, ticker: Any) -> None:
        """Wait for a free slot in the sliding window, or fail.

        At most ``rate_limit_calls`` provider calls may start within any
        ``rate_limit_period``. When the window is full, wait until the
        oldest call leaves it, as long as the total wait stays within
        ``rate_limit_max_wait``. Otherwise raise a plain
        ``ProviderError`` without calling the provider. It is not
        transient, because a retry would only wait again.
        """
        period = self._policy.rate_limit_period
        waited = 0.0
        while True:
            with self._lock:
                now = self._clock()
                while self._calls and self._calls[0] <= now - period:
                    self._calls.popleft()
                if len(self._calls) < self._policy.rate_limit_calls:
                    self._calls.append(now)
                    return
                wait = self._calls[0] + period - now
            if waited + wait > self._policy.rate_limit_max_wait:
                logger.warning(
                    "Rate limit reached for %s %r: %d calls per %.0f s",
                    method_name,
                    ticker,
                    self._policy.rate_limit_calls,
                    period,
                )
                raise ProviderError("Local rate limit reached")
            # Sleep outside the lock, then check again: another thread
            # may have taken the slot meanwhile.
            self._sleep(wait)
            waited += wait

    def _backoff_delay(self, retry: int) -> float:
        """Full jitter: a random time up to an exponential ceiling.

        Retry 1 waits up to ``backoff_base``, retry 2 up to twice that,
        and so on, never more than ``backoff_max``. Random delays stop
        many clients from retrying at the same moment.
        """
        ceiling = min(
            self._policy.backoff_max,
            self._policy.backoff_base * 2 ** (retry - 1),
        )
        return self._rand() * ceiling
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest -q -p no:cacheprovider tests/test_collector_guard.py`
Expected: all pass.

- [ ] **Step 5: Run the full suite and the scoped lint**

Run the CI command. Expected: all pass. Lint
`app/data_collectors/guard.py tests/test_collector_guard.py`.
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add app/data_collectors/guard.py tests/test_collector_guard.py
git commit -m "feat: add the rate limit and retry with backoff to the collector guard"
```

---

### Task 4: Put the guard in front of Yahoo, and document the settings

**Files:**
- Modify: `app/api/data_collection.py` (imports; `get_collector`)
- Modify: `tests/conftest.py` (new autouse fixture)
- Modify: `tests/test_collector_selection.py`
  (`test_get_collector_returns_yahoo`)
- Create: `tests/test_collector_guard_api.py`
- Modify: `tests/test_collector_guard_settings.py` (append the docs test)
- Modify: `.env.example`, `README.md`

**Interfaces:**
- Consumes: `guard_collector`, `GuardPolicy` (Tasks 1-3); `FakeClock`,
  `ScriptedLookup`, `SpyCollector`, `sourced` from
  `tests/collector_stubs.py`.
- Produces: `app.api.data_collection.get_collector()` (unchanged
  signature) and `app.api.data_collection.reset_collector() -> None`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_collector_selection.py`, change the imports to add
`reset_collector` and the protocols:

```python
from app.api.data_collection import get_collector, reset_collector
from app.data_collectors.base import FundAttributes, InstrumentLookup
```

and replace `test_get_collector_returns_yahoo` with:

```python
def test_get_collector_returns_one_guarded_yahoo(monkeypatch):
    monkeypatch.setattr(settings, "DATA_COLLECTOR", "yahoo")

    first = get_collector()

    assert isinstance(first.inner, YahooFinanceCollector)
    assert get_collector() is first
    assert isinstance(first, InstrumentLookup)
    assert not isinstance(first, FundAttributes)


def test_reset_collector_builds_a_new_guarded_yahoo(monkeypatch):
    monkeypatch.setattr(settings, "DATA_COLLECTOR", "yahoo")
    first = get_collector()

    reset_collector()

    assert get_collector() is not first


def test_shared_yahoo_reads_the_guard_settings(monkeypatch):
    monkeypatch.setattr(settings, "DATA_COLLECTOR", "yahoo")
    monkeypatch.setattr(settings, "COLLECTOR_RATE_LIMIT_CALLS", 7)
    monkeypatch.setattr(
        settings, "COLLECTOR_CACHE_TTL_COMPANY_INFO_SECONDS", 0
    )

    policy = get_collector().policy

    assert policy.rate_limit_calls == 7
    assert policy.ttl_company_info == 0


def test_fake_mode_is_not_guarded(monkeypatch):
    monkeypatch.setattr(settings, "DATA_COLLECTOR", "fake")

    assert type(get_collector()) is FakeCollector
```

Create `tests/test_collector_guard_api.py`:

```python
"""fetch-company through the collector guard, offline and in fake time."""

import pytest

from app.api.data_collection import get_collector
from app.data_collectors.base import ProviderError, TransientProviderError
from app.data_collectors.guard import GuardPolicy, guard_collector
from tests.collector_stubs import (
    FakeClock,
    ScriptedLookup,
    SpyCollector,
    sourced,
)

FETCH = "/api/v1/data-collection/fetch-company"


def serve(client, inner, **policy):
    """Make fetch-company use one guarded ``inner`` for every request."""
    clock = FakeClock()
    guarded = guard_collector(
        inner,
        GuardPolicy(**policy),
        clock=clock,
        sleep=clock.sleep,
        rand=lambda: 0.0,
    )
    client.app.dependency_overrides[get_collector] = lambda: guarded
    return guarded


@pytest.mark.asyncio
async def test_no_data_through_the_guard_is_404(client):
    inner = ScriptedLookup(None)
    serve(client, inner)

    response = await client.post(FETCH, json={"ticker": "NOPE"})

    assert response.status_code == 404
    assert inner.calls == 1


@pytest.mark.asyncio
async def test_provider_error_through_the_guard_is_502(client):
    inner = ScriptedLookup(ProviderError("down"))
    serve(client, inner)

    response = await client.post(FETCH, json={"ticker": "DOWN"})

    assert response.status_code == 502
    assert response.json() == {"detail": "Data provider error"}
    assert inner.calls == 1


@pytest.mark.asyncio
async def test_exhausted_retries_are_502(client):
    busy = TransientProviderError("busy")
    inner = ScriptedLookup(busy, busy)
    serve(client, inner, max_retries=1)

    response = await client.post(FETCH, json={"ticker": "BUSY"})

    assert response.status_code == 502
    assert response.json() == {"detail": "Data provider error"}
    assert inner.calls == 2


@pytest.mark.asyncio
async def test_retry_success_creates_the_company(client):
    inner = ScriptedLookup(
        TransientProviderError("busy"),
        sourced({"name": "Acme", "currency": "USD"}),
    )
    serve(client, inner)

    response = await client.post(FETCH, json={"ticker": "ACME"})

    assert response.status_code == 200
    assert inner.calls == 2


@pytest.mark.asyncio
async def test_full_rate_limit_is_502(client):
    inner = ScriptedLookup(sourced({"name": "Acme", "currency": "USD"}))
    serve(client, inner, rate_limit_calls=1, rate_limit_max_wait=0)
    first = await client.post(FETCH, json={"ticker": "ACME"})

    response = await client.post(FETCH, json={"ticker": "OTHER"})

    assert first.status_code == 200
    assert response.status_code == 502
    assert response.json() == {"detail": "Data provider error"}
    assert inner.calls == 1


@pytest.mark.asyncio
async def test_repeat_fetch_is_served_from_the_cache(client):
    inner = SpyCollector()
    serve(client, inner)

    first = await client.post(FETCH, json={"ticker": "DEMO_PL_TECH"})
    second = await client.post(FETCH, json={"ticker": "DEMO_PL_TECH"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert inner.calls == [("fetch_company_info", "DEMO_PL_TECH")]
```

Append to `tests/test_collector_guard_settings.py` (add
`from pathlib import Path` to its imports):

```python
ROOT = Path(__file__).resolve().parents[1]


def test_every_guard_setting_is_documented():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    example = (ROOT / ".env.example").read_text(encoding="utf-8")

    for name in DEFAULTS:
        assert name in readme, name
        assert f"{name}=" in example, name
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest -q -p no:cacheprovider tests/test_collector_selection.py tests/test_collector_guard_api.py tests/test_collector_guard_settings.py`
Expected: collection error in `test_collector_selection.py`
(`ImportError: cannot import name 'reset_collector'`), and
`test_every_guard_setting_is_documented` fails. The tests in
`test_collector_guard_api.py` may already pass, because they install
their own guarded collector; they pin the HTTP mapping through the
guard. The existing `test_yahoo_near_empty_info_is_a_404_not_a_502`
runs through the guarded Yahoo collector after Step 3 and must still
pass.

- [ ] **Step 3: Share one guarded Yahoo collector**

In `app/api/data_collection.py`, add `import threading` after
`import logging`, add
`from app.data_collectors.guard import GuardPolicy, guard_collector`
after the `app.data_collectors.fake` import, and replace
`get_collector` with:

```python
# fetch-company in "yahoo" mode uses one guarded Yahoo collector for
# every request, so the cache and the rate limit see all of them. It is
# a module-level variable (like a static field in Java), built on first
# use from the settings. The lock stops two first requests from each
# building one.
_shared_collector: Optional[InstrumentLookup] = None
_shared_collector_lock = threading.Lock()


def get_collector() -> InstrumentLookup:
    """Return the collector chosen by ``DATA_COLLECTOR``.

    ``fake`` gives a new offline ``FakeCollector``. It is not guarded:
    it never calls the network. ``yahoo`` gives the shared Yahoo
    collector behind the cache, rate limit and retries of
    ``app.data_collectors.guard``.

    The setting is read on every call (not at import), so a test can
    change it with ``monkeypatch``. Tests that need other behavior
    replace this function through ``app.dependency_overrides``.
    """
    if settings.DATA_COLLECTOR == "fake":
        return FakeCollector()
    return _shared_yahoo_collector()


def _shared_yahoo_collector() -> InstrumentLookup:
    # "global" lets this function assign the module-level variable;
    # without it the assignment would create a local variable.
    global _shared_collector
    with _shared_collector_lock:
        if _shared_collector is None:
            _shared_collector = guard_collector(
                YahooFinanceCollector(), GuardPolicy.from_settings(settings)
            )
        return _shared_collector


def reset_collector() -> None:
    """Forget the shared Yahoo collector, with its cache and rate limit.

    The next ``yahoo`` request builds a new one from the current
    settings. Tests call this around every test.
    """
    global _shared_collector
    with _shared_collector_lock:
        _shared_collector = None
```

- [ ] **Step 4: Reset the shared collector around every test**

In `tests/conftest.py`, add the import (isort keeps it before
`app.core.database`):

```python
from app.api.data_collection import reset_collector  # noqa: E402
```

and add this fixture after `block_network`:

```python
@pytest.fixture(autouse=True)
def fresh_shared_collector():
    """Each test starts and ends without the shared Yahoo collector.

    It lives at module level, so the cache or rate-limit state of one
    test would otherwise leak into the next.
    """
    reset_collector()
    yield
    reset_collector()
```

- [ ] **Step 5: Document the settings**

In `.env.example`, directly after `DATA_COLLECTOR=yahoo`, add:

```
# Cache, rate limit and retries in front of the Yahoo collector
# (DATA_COLLECTOR=yahoo only). Times are in seconds. A cache TTL of 0
# turns the cache off for that kind of data. A value out of range stops
# startup.
COLLECTOR_CACHE_TTL_COMPANY_INFO_SECONDS=86400
COLLECTOR_CACHE_TTL_KEY_METRICS_SECONDS=3600
COLLECTOR_CACHE_TTL_PRICE_HISTORY_SECONDS=900
COLLECTOR_CACHE_TTL_FUND_ATTRIBUTES_SECONDS=86400
COLLECTOR_CACHE_MAX_ENTRIES=256
# At most COLLECTOR_RATE_LIMIT_CALLS provider calls per period. A call
# waits up to the max wait for a free slot, then fails with HTTP 502.
COLLECTOR_RATE_LIMIT_CALLS=30
COLLECTOR_RATE_LIMIT_PERIOD_SECONDS=60
COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS=5
# Retries for temporary provider errors, after a random delay whose
# ceiling doubles from the base up to the max.
COLLECTOR_RETRY_MAX_RETRIES=2
COLLECTOR_BACKOFF_BASE_SECONDS=1
COLLECTOR_BACKOFF_MAX_SECONDS=8
```

In `README.md`, after the two lines that start with
"`DATA_COLLECTOR` picks the market-data collector", add:

```markdown
With `yahoo`, fetch-company calls Yahoo through a guard
(`app/data_collectors/guard.py`): an in-memory cache, a rate limit and
retries. A repeat request within the cache time does not reach Yahoo,
and the data keeps its original retrieval time. The cache belongs to
one process, starts empty, and changed settings apply after a restart.
A full rate limit, or a provider error after the last retry, returns
502 `Data provider error`. The limits, with their defaults:

| Setting | Default | Meaning |
|---|---|---|
| `COLLECTOR_CACHE_TTL_COMPANY_INFO_SECONDS` | 86400 | Cache time for company profiles. `0` turns it off. |
| `COLLECTOR_CACHE_TTL_KEY_METRICS_SECONDS` | 3600 | Cache time for key metrics. |
| `COLLECTOR_CACHE_TTL_PRICE_HISTORY_SECONDS` | 900 | Cache time for price history. |
| `COLLECTOR_CACHE_TTL_FUND_ATTRIBUTES_SECONDS` | 86400 | Cache time for fund data. |
| `COLLECTOR_CACHE_MAX_ENTRIES` | 256 | The least recently used entry is dropped beyond this. |
| `COLLECTOR_RATE_LIMIT_CALLS` | 30 | Provider calls allowed per period. |
| `COLLECTOR_RATE_LIMIT_PERIOD_SECONDS` | 60 | Length of the rate-limit window. |
| `COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS` | 5 | How long a call may wait for a free slot. |
| `COLLECTOR_RETRY_MAX_RETRIES` | 2 | Retries for a temporary provider error. |
| `COLLECTOR_BACKOFF_BASE_SECONDS` | 1 | Ceiling of the first random retry delay. |
| `COLLECTOR_BACKOFF_MAX_SECONDS` | 8 | Largest retry delay ceiling. |
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest -q -p no:cacheprovider tests/test_collector_selection.py tests/test_collector_guard_api.py tests/test_collector_guard_settings.py tests/test_config.py tests/test_secure_config.py`
Expected: all pass (`tests/test_config.py` loads `.env.example`, so the
new lines must be valid values).

- [ ] **Step 7: Run the full suite, the integration selection and the scoped lint**

Run the CI command, then
`python -m pytest -q -p no:cacheprovider -m integration`
(PostgreSQL tests skip without `TEST_POSTGRES_DSN`). Expected: all pass.
Lint `app/api/data_collection.py tests/conftest.py tests/test_collector_selection.py tests/test_collector_guard_api.py tests/test_collector_guard_settings.py`.
Expected: clean (all five files are clean on `master` today).

- [ ] **Step 8: Commit**

```bash
git add app/api/data_collection.py tests/conftest.py \
  tests/test_collector_selection.py tests/test_collector_guard_api.py \
  tests/test_collector_guard_settings.py .env.example README.md
git commit -m "feat: put the collector guard in front of Yahoo and document its settings"
```

---

### Task 5: Uppercase currency codes, keeping `GBp` and `ZAc`

**Files:**
- Modify: `app/models/company.py:14-15` (constants) and the
  `_normalize_currency` validator (around line 65)
- Modify: `tests/test_provider_data_hygiene.py`
  (`test_currency_keeps_case_and_rejects_a_non_letter_code`, around
  line 361; new tests after it)
- Modify: `docs/api-demo.md:70-71`

**Interfaces:**
- Consumes: nothing from Tasks 1-4.
- Produces: `app.models.company.normalize_currency(value: object) -> object`
  and `app.models.company.MINOR_UNIT_CURRENCIES: frozenset`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_provider_data_hygiene.py`, add `normalize_currency` to
the `from app.models.company import ...` line, and replace
`test_currency_keeps_case_and_rejects_a_non_letter_code` with:

```python
@pytest.mark.parametrize(
    "value, expected",
    [
        ("usd", "USD"),
        ("Usd", "USD"),
        ("USD", "USD"),
        ("eur", "EUR"),
        ("gbp", "GBP"),
        ("GBP", "GBP"),
        ("GBp", "GBp"),
        ("ZAc", "ZAc"),
        ("zac", "ZAC"),
        ("ILA", "ILA"),
        (None, None),
    ],
)
def test_normalize_currency(value, expected):
    assert normalize_currency(value) == expected


@pytest.mark.parametrize(
    "value", ["US1", "US", "USDD", " usd", "usd ", "u$d", "", "ŁÓD"]
)
def test_normalize_currency_rejects_a_bad_shape(value):
    with pytest.raises(ValueError, match="exactly three letters"):
        normalize_currency(value)


@pytest.mark.asyncio
async def test_currency_is_uppercased_and_a_non_letter_code_rejected(client):
    created = await client.post(
        COMPANIES,
        json={"name": "Dollar", "ticker": "USDX", "currency": "usd"},
    )
    rejected = await client.post(
        COMPANIES,
        json={"name": "Bad", "ticker": "BADC", "currency": "US1"},
    )

    assert created.status_code == 201
    assert created.json()["currency"] == "USD"
    assert rejected.status_code == 422


@pytest.mark.asyncio
async def test_currency_update_is_uppercased(client):
    created = (
        await client.post(
            COMPANIES,
            json={"name": "Euro", "ticker": "EURX", "currency": "USD"},
        )
    ).json()
    url = f"/api/v1/companies/{created['id']}"

    updated = await client.put(url, json={"currency": "eur"})

    assert updated.status_code == 200
    assert (await client.get(url)).json()["currency"] == "EUR"


@pytest.mark.asyncio
async def test_fetch_company_uppercases_a_lowercase_currency(client):
    client.app.dependency_overrides[get_collector] = lambda: PayloadCollector(
        {"name": "Acme", "currency": "usd"}
    )

    created = await client.post(FETCH, json={"ticker": "ACME"})

    assert created.status_code == 200
    stored = await client.get(
        f"/api/v1/companies/{created.json()['company_id']}"
    )
    assert stored.json()["currency"] == "USD"


@pytest.mark.asyncio
async def test_rand_cents_currency_round_trips_unchanged(client):
    """Yahoo sends ZAc for South African cents. ZAC would lose that."""
    client.app.dependency_overrides[get_collector] = lambda: PayloadCollector(
        {"name": "Naspers", "currency": "ZAc"}
    )

    created = await client.post(FETCH, json={"ticker": "NPN.JO"})

    assert created.status_code == 200
    stored = await client.get(
        f"/api/v1/companies/{created.json()['company_id']}"
    )
    assert stored.json()["currency"] == "ZAc"
```

Keep `test_pence_currency_round_trips_unchanged` as it is.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest -q -p no:cacheprovider tests/test_provider_data_hygiene.py`
Expected: collection error, `ImportError: cannot import name 'normalize_currency'`.

- [ ] **Step 3: Implement the normalization**

In `app/models/company.py`, replace the two lines

```python
# Three letters, either case. GBp is London pence and must not become GBP.
_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")
```

with:

```python
# Three ASCII letters, either case, before normalization.
_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")
# Yahoo's minor-unit codes, where the letter case is the meaning:
# GBp is London pence (GBP / 100) and ZAc is South African cents. They
# are kept exactly as sent. Every other code is uppercased.
MINOR_UNIT_CURRENCIES = frozenset({"GBp", "ZAc"})
```

Add this function after `normalize_ticker`:

```python
def normalize_currency(value: object) -> object:
    """Uppercase a three-letter currency code, except Yahoo minor units.

    ``usd`` and ``Usd`` become ``USD``, so one currency is stored as one
    code. ``GBp`` and ``ZAc`` stay as sent; ``gbp`` becomes ``GBP``,
    because only the exact spelling ``GBp`` means pence. ``None`` and
    non-strings are left for the field type to handle.
    """
    if value is None or not isinstance(value, str):
        return value
    if _CURRENCY_RE.fullmatch(value) is None:
        raise ValueError("currency must be exactly three letters")
    if value in MINOR_UNIT_CURRENCIES:
        return value
    return value.upper()
```

Replace the body of the `_normalize_currency` validator in
`_CompanyWriteChecks` with:

```python
    @field_validator("currency", mode="before", check_fields=False)
    @classmethod
    def _normalize_currency(cls, value: object) -> object:
        return normalize_currency(value)
```

- [ ] **Step 4: Update the API demo note**

In `docs/api-demo.md`, replace the two lines starting "Currency is
stored exactly as sent" with:

```markdown
Currency is stored in uppercase (`usd` becomes `USD`). Yahoo's
minor-unit codes `GBp` (pence) and `ZAc` (South African cents) are kept
exactly as sent: rewriting `GBp` to `GBP` would treat the amount as
pounds.
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest -q -p no:cacheprovider tests/test_provider_data_hygiene.py tests/test_secure_config.py`
Expected: all pass.

- [ ] **Step 6: Run the full suite and the scoped lint**

Run the CI command. Expected: all pass. Lint
`app/models/company.py tests/test_provider_data_hygiene.py`. Expected:
clean except the two E501 lines that already exist on `master` in
`tests/test_provider_data_hygiene.py` (the line numbers move; report
them).

- [ ] **Step 7: Commit**

```bash
git add app/models/company.py tests/test_provider_data_hygiene.py \
  docs/api-demo.md
git commit -m "feat: store currency codes in uppercase except GBp and ZAc (#24 part 2)"
```

---

## After the tasks (controller)

- Final whole-branch review, one fix wave if needed, scoped re-review.
- Controller writes the journal and work-state entries (scope,
  decisions, verification, AI models, time tracking from git times).
- Push and pull request only after the owner's go-ahead. The pull
  request says "Refs #24" and ticks the two remaining #24 items.
