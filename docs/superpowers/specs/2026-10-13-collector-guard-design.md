# Collector guard and currency normalization (#24 part 2) - design

Date: 2026-10-13. Issue: [#24](https://github.com/Waber/Investment-AI-Companion/issues/24),
part 2. Part 1 is PR #68. Real Yahoo error mapping is R1 (#54).

## Goal

The two open items of #24:

1. A cache with a TTL per capability, a rate limit, and retry with
   exponential backoff and jitter, in a wrapper around any real
   collector. Configurable, and tested offline with the fake collector
   and a fake clock. After the last retry the caller sees a provider
   error (HTTP 502).
2. Currency stored as uppercase ISO 4217 (`usd` and `USD` are one
   code), without folding Yahoo's `GBp` into `GBP`.

Owner decision (2026-10-13): the wrapper is put in front of the Yahoo
collector now, not only built as a hook.

## Out of scope

- Mapping yfinance errors (`YFRateLimitError`, HTTP 429, timeouts) to
  the retryable error. R1 (#54) does that. Until then the retry path is
  exercised only by tests.
- Request coalescing (two simultaneous misses for one key both call
  the provider).
- A shared or persistent cache (Redis, disk). The cache is per process.
- Rewriting currency values already stored. There are no Alembic
  migration files; the schema is built with `create_all`.
- HTTP 503 or `Retry-After` for a full rate limit. It stays 502, like
  every other provider failure.

## Design

### Errors (`app/data_collectors/base.py`)

`TransientProviderError(ProviderError)` is the only error the guard
retries. It means "the same call may succeed later" (rate limited by
the provider, a timeout). A plain `ProviderError` (a parse error, a
bad response) is not retried. Both still become 502 `Data provider
error` in fetch-company, because the handler catches `ProviderError`.

### The guard (`app/data_collectors/guard.py`)

`guard_collector(inner, policy, *, clock=time.monotonic,
sleep=time.sleep, rand=random.random)` returns a guarded collector.

- **Only the capabilities the inner collector has.** One small mixin
  class per capability protocol (`InstrumentLookup`, `PriceHistory`,
  `Fundamentals`, `FundAttributes`), each with one explicit method that
  calls the shared guarded path. `guard_collector` picks the mixins
  whose protocol `isinstance(inner, ...)` passes and builds the class
  with `type(...)`, cached per inner class. Java analogy:
  `Proxy.newProxyInstance` given only the interfaces the target
  implements. A wrapped Yahoo collector therefore is not a
  `FundAttributes`; a wrapped fake is.
- **Why not `__getattr__`:** since Python 3.12, `isinstance` against a
  `runtime_checkable` protocol uses `inspect.getattr_static`, which
  does not see attributes served by `__getattr__`. A probe on the
  project's Python 3.12.15 confirmed it: a `__getattr__` proxy is not
  an instance of the protocol; a class built from mixins is.
- **Clock:** `clock` is monotonic seconds, used for TTLs and the rate
  limit window. It is not wall time and does not touch provenance:
  `retrieved_at` still comes from the inner collector's own clock.

### One guarded call

1. **Key:** the method name and its arguments, bound to the inner
   method's signature with defaults applied
   (`inspect.signature(...).bind(...).apply_defaults()`). So
   `fetch_price_history("X", period="1y")` and
   `fetch_price_history("X", "1y")` share one entry. If a key is not
   hashable, the call skips the cache (capability arguments are
   strings, so this is defensive).
2. **Cache hit** (entry not expired): return a deep copy of the stored
   result. The original `retrieved_at` is kept, so the data age shown
   to the user stays honest.
3. **Cache miss:** loop over attempts `1 .. max_retries + 1`:
   1. Take a rate-limit slot (below).
   2. Call the inner method.
   3. Success, including `None` ("no data"): store a deep copy with
      the capability's TTL, return the result.
   4. `TransientProviderError`: if attempts remain, sleep the backoff
      delay and try again; otherwise re-raise it.
   5. Any other exception: propagate unchanged. Nothing is cached.

Deep copies on store and on hit mean a caller that mutates a returned
dict cannot change what the next caller gets (`Sourced` is frozen, but
only shallowly).

### Cache

- `OrderedDict` of key to `(expires_at, value)`, least recently used
  first. A hit moves the entry to the end.
- An expired entry found on lookup is removed.
- After an insert, if the size is over `COLLECTOR_CACHE_MAX_ENTRIES`,
  the least recently used entry is dropped.
- TTL `0` for a capability means that capability is never cached.

### Rate limit

A sliding window: at most `COLLECTOR_RATE_LIMIT_CALLS` provider calls
in any `COLLECTOR_RATE_LIMIT_PERIOD_SECONDS`. Only real provider calls
take a slot; cache hits do not. Each retry takes its own slot.

- Keep a deque of call times. Drop the ones older than `now - period`.
- If there is room, record `now` and go.
- If not, the wait is `oldest + period - now`.
  - Wait `<= COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS`: sleep, then check
    again.
  - Longer: raise a plain `ProviderError` without calling the
    provider. It is not transient, because retrying would only wait
    again.

### Backoff

Full jitter. Retry `n` (1-based) sleeps
`rand() * min(BACKOFF_MAX, BACKOFF_BASE * 2 ** (n - 1))` seconds, with
`rand()` in `[0, 1)`. With the defaults (base 1, max 8, two retries)
retry 1 sleeps at most 1 s and retry 2 at most 2 s.

Worst-case latency of one call with the defaults: three attempts with
up to 5 s of rate-limit wait each, plus up to 3 s of backoff, about
18 s.

### Threads

FastAPI runs sync endpoints in a thread pool. One `threading.Lock`
guards the cache and the rate-limit deque. It is never held while the
provider is called or while sleeping. After a rate-limit sleep the
slot check runs again under the lock.

### Logging

The inner collector already logged the provider's own error text, so
the guard never logs it. Tickers use `%r`.

- WARNING on each retry: method, ticker, attempt `n` of `m`, delay.
- WARNING when the rate limit is full and the call fails.
- DEBUG on a cache hit.

### Wiring (`app/api/data_collection.py`)

- `DATA_COLLECTOR=fake`: `get_collector()` returns a bare
  `FakeCollector()`, as today. Tests and the demo stay unguarded and
  deterministic.
- `DATA_COLLECTOR=yahoo`: `get_collector()` returns one process-wide
  guarded `YahooFinanceCollector`, built on first use from the
  settings, so the cache and the rate limit are shared by all
  requests. A `reset_collector()` function clears it for tests.

### Settings (`app/core/config.py`)

Flat names, like the existing settings. Each one is checked at startup
with `Field(ge=..., le=...)`, and a model validator checks
`BACKOFF_MAX >= BACKOFF_BASE`. A bad value stops startup.

| Setting | Type | Default | Bounds | Meaning |
|---|---|---|---|---|
| `COLLECTOR_CACHE_TTL_COMPANY_INFO_SECONDS` | int | 86400 | 0..604800 | Profile data. `0` = no cache. |
| `COLLECTOR_CACHE_TTL_KEY_METRICS_SECONDS` | int | 3600 | 0..604800 | Ratios move with the price. |
| `COLLECTOR_CACHE_TTL_PRICE_HISTORY_SECONDS` | int | 900 | 0..604800 | Price bars. |
| `COLLECTOR_CACHE_TTL_FUND_ATTRIBUTES_SECONDS` | int | 86400 | 0..604800 | Fund data. |
| `COLLECTOR_CACHE_MAX_ENTRIES` | int | 256 | 1..10000 | LRU bound; a 5-year history is about 1260 bars. |
| `COLLECTOR_RATE_LIMIT_CALLS` | int | 30 | 1..10000 | Provider calls per window. |
| `COLLECTOR_RATE_LIMIT_PERIOD_SECONDS` | float | 60 | > 0, <= 3600 | Window length. |
| `COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS` | float | 5 | 0..60 | `0` = fail at once when full. |
| `COLLECTOR_RETRY_MAX_RETRIES` | int | 2 | 0..5 | Retries after the first attempt. |
| `COLLECTOR_BACKOFF_BASE_SECONDS` | float | 1 | > 0, <= 60 | First backoff ceiling. |
| `COLLECTOR_BACKOFF_MAX_SECONDS` | float | 8 | > 0, <= 300 | Backoff cap. |

A frozen `GuardPolicy` dataclass holds these values;
`GuardPolicy.from_settings(settings)` builds it, so the guard itself
does not import the settings module.

### Currency (`app/models/company.py`)

`_normalize_currency` in `_CompanyWriteChecks`, used by company
create, company update and fetch-company:

- The existing check stays: exactly three ASCII letters, no stripping.
- The exact Yahoo minor-unit spellings `GBp` (London pence) and `ZAc`
  (South African cents) are kept as sent.
- Everything else is uppercased: `usd`, `Usd` -> `USD`; `gbp` -> `GBP`
  (only the exact spelling `GBp` means pence). `ILA` (Israeli agorot)
  is already uppercase.
- The read model (`Company`) and stored rows do not change.
- The comments and the error text that say "case is unchanged" are
  updated.

## Testing

All offline. The network guard stays on. A `FakeClock` provides
`clock()` and a `sleep()` that moves time forward and records each
delay. `rand` is a scripted sequence.

- Cache: hit and miss per capability; expiry at the TTL; TTL `0`;
  `None` is cached; `ProviderError` and `TransientProviderError` are
  not; mutating a returned dict does not change the next hit; LRU
  eviction at the bound; keyword and positional arguments share an
  entry; a cache hit keeps the original `retrieved_at`.
- Rate limit: N calls in a window pass without sleeping; call N+1
  sleeps exactly until the oldest slot frees; a wait longer than the
  max raises `ProviderError` without calling the provider; cache hits
  take no slot.
- Retry: a transient error then success makes two provider calls and
  sleeps the jitter delay; exhausted retries re-raise after
  `max_retries + 1` calls; a plain `ProviderError` is not retried;
  each retry takes a slot.
- Capabilities: `guard_collector(FakeCollector())` passes all four
  protocol checks; `guard_collector(YahooFinanceCollector())` passes
  three and not `FundAttributes`; the built class is reused per inner
  class.
- Threads: concurrent calls from several threads never exceed the
  rate limit, and the lock is not held during the provider call.
- Wiring: `yahoo` returns the same guarded instance on every call
  until `reset_collector()`; `fake` returns a bare `FakeCollector`;
  fetch-company still answers 404 for no data and 502 for a
  `ProviderError` through the guard.
- Settings: each bound, and `BACKOFF_MAX < BACKOFF_BASE` is rejected.
- Currency: `usd` -> `USD`, `Usd` -> `USD`, `gbp` -> `GBP`; `GBp` and
  `ZAc` kept; a bad shape still 422; on create, update and
  fetch-company. `test_provider_data_hygiene.py`'s test that keeps
  `usd` lowercase changes to the new rule.

## Docs

`.env.example` and `README.md` list the new settings and their
defaults. Journal and work-state entries for the iteration.

## Acceptance

- [ ] Cache TTL per capability, rate limit and backoff are
  configurable and covered by offline tests with a fake clock.
- [ ] The guard wraps the Yahoo collector in `yahoo` mode; `fake` mode
  is unchanged.
- [ ] After the last retry the error reaches the caller as 502.
- [ ] Currency is uppercase except `GBp` and `ZAc`; tested on create,
  update and fetch-company.
- [ ] No automated test reaches the network.
- [ ] Full SQLite suite and CI green; scoped black, isort and flake8
  pass.
- [ ] Journal and work-state updated; the Code Reviewer approved.
