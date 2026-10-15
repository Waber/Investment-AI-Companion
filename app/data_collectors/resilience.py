"""Cache, rate limit and retry in front of a live market-data collector.

This is a wrapper, the same idea as a Java class that implements an
interface and forwards to another object. Python's ``Protocol`` is
structural: the wrapper does not declare ``implements``. After
``__init__`` it only has the capability methods the wrapped collector
has, because ``isinstance`` looks for those method names. A wrapper
around Yahoo therefore does not claim ``FundAttributes``.

Three protections, all in this process (not on disk):

- A TTL cache. Only a successful result is stored. ``None`` ("no data")
  and ``ProviderError`` are not, so a missing ticker or a failure is
  not pinned for the whole TTL. A cache hit returns the provenance of
  the fetch that filled the cache: ``retrieved_at`` stays the original
  time and is not rewritten to "now". The cached value is copied on the
  way in and on the way out. ``Sourced`` is frozen, but that freeze is
  shallow, and a caller that mutates the dict would otherwise change
  what the next caller sees.
- A sliding-window rate limit. At most N upstream calls in any window
  of 60 seconds. A token bucket with room for a burst of N can still
  allow nearly 2N calls in one minute (one burst, then a refilled
  burst). The setting says "per minute", so the wrapper remembers the
  time of each upstream call and waits until the oldest one is 60
  seconds old. Cache hits are not upstream calls and do not count.
  Waiting uses the injected ``sleep``, so tests move a fake clock
  instead of pausing.
- Retry with exponential backoff and full jitter. A transient failure
  (rate limit, HTTP 429, timeout, connection error) is tried again.
  The wait is a random number from 0 up to ``min(max, base * 2^attempt)``
  — full jitter, so many processes do not retry on the same instant.
  ``attempt`` starts at 0 for the first retry. After the bounded number
  of extra attempts the wrapper raises ``ProviderError`` with a fixed
  message and no chained cause, so a URL or response body from the
  provider cannot ride out on the exception text. The log line names
  the exception class, not that text.

``COLLECTOR_MAX_RETRIES`` is the number of extra attempts. 2 means
three calls.

The lock is the same job as a Java ``synchronized`` block. Uvicorn runs
sync endpoints on a thread pool, so two requests can enter the wrapper
at once. The lock covers the cache and the list of call times. Sleep
happens outside the lock, so a cache hit is not stuck behind a
60-second wait. Do not take the lock and then call a method that takes
it again: ``threading.Lock`` is not re-entrant and that would deadlock.

The clock, sleep and random source are arguments. Production uses
``time.monotonic``, ``time.sleep`` and ``random.uniform``. Tests pass
fakes. ``time.monotonic`` does not jump when the wall clock is
corrected, which is what a TTL and a rate limit need. Provenance still
comes from the inner collector's own clock.

yfinance is not imported here. ``YFRateLimitError`` is recognised by
class name, including when the Yahoo collector has already wrapped it
as the ``__cause__`` of a ``ProviderError`` (Java's "cause").
"""

import copy
import inspect
import logging
import math
import random
import threading
import time
from collections import OrderedDict, deque
from typing import Any, Callable, Deque, Optional, Tuple

from app.core.config import (
    COLLECTOR_BACKOFF_BASE_MAX_SECONDS,
    COLLECTOR_BACKOFF_CAP_MAX_SECONDS,
    COLLECTOR_CACHE_TTL_MAX_SECONDS,
    COLLECTOR_CACHE_TTL_MIN_SECONDS,
    COLLECTOR_MAX_RETRIES_MAX,
    COLLECTOR_MAX_RETRIES_MIN,
    COLLECTOR_RATE_LIMIT_MAX_PER_MINUTE,
    COLLECTOR_RATE_LIMIT_MIN_PER_MINUTE,
)
from app.data_collectors.base import (
    Fundamentals,
    FundAttributes,
    InstrumentLookup,
    PriceHistory,
    ProviderError,
)

logger = logging.getLogger(__name__)

TEMPORARY_FAILURE_MESSAGE = "Data provider is temporarily unavailable"
RATE_LIMIT_WINDOW_SECONDS = 60.0
DEFAULT_MAX_CACHE_ENTRIES = 256
_MAX_CACHE_ENTRIES_LIMIT = 10_000

# Class names, not imports. requests and yfinance use these names.
# Matching the name keeps yfinance out of this module.
_TRANSIENT_TYPE_NAMES = frozenset(
    {
        "YFRateLimitError",
        "Timeout",
        "TimeoutError",
        "ConnectTimeout",
        "ReadTimeout",
        "ConnectTimeoutError",
        "ReadTimeoutError",
        "ConnectionError",
        "NewConnectionError",
        "MaxRetryError",
        "ChunkedEncodingError",
        "RemoteDisconnected",
        "ProtocolError",
    }
)

_CAPABILITIES = (
    ("fetch_company_info", InstrumentLookup),
    ("fetch_price_history", PriceHistory),
    ("fetch_key_metrics", Fundamentals),
    ("fetch_fund_attributes", FundAttributes),
)

_MISS = object()


def _is_transient(exc: BaseException) -> bool:
    """True when this exception, or its cause, is worth retrying."""
    seen = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if _is_transient_one(current):
            return True
        nxt = current.__cause__
        if nxt is None:
            nxt = current.__context__
        current = nxt
    return False


def _is_transient_one(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    names = {cls.__name__ for cls in type(exc).__mro__}
    if names & _TRANSIENT_TYPE_NAMES:
        return True
    return _status_code(exc) == 429


def _status_code(exc: BaseException) -> Optional[int]:
    code = getattr(exc, "status_code", None)
    if code is None:
        response = getattr(exc, "response", None)
        code = getattr(response, "status_code", None)
    return code


def _public_type(exc: BaseException) -> str:
    """Class names only. The exception text can contain a URL."""
    names = [type(exc).__name__]
    cause = exc.__cause__ or exc.__context__
    if cause is not None and cause is not exc:
        names.append(type(cause).__name__)
    return " from ".join(names)


def _require_int(name: str, value: object, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if not low <= value <= high:
        raise ValueError(f"{name} must be from {low} to {high}")
    return value


def _require_float(name: str, value: object, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number) or not low <= number <= high:
        raise ValueError(f"{name} must be from {low} to {high}")
    return number


class ResilientCollector:
    """Wrap ``inner`` with the cache, the rate limit and the retry."""

    def __init__(
        self,
        inner: Any,
        *,
        clock: Optional[Callable[[], float]] = None,
        sleep: Optional[Callable[[float], None]] = None,
        rng: Optional[Callable[[float, float], float]] = None,
        cache_ttl_seconds: float = 300,
        rate_limit_per_minute: int = 30,
        max_retries: int = 2,
        backoff_base_seconds: float = 0.5,
        backoff_max_seconds: float = 8,
        max_cache_entries: int = DEFAULT_MAX_CACHE_ENTRIES,
    ) -> None:
        self.inner = inner
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep
        self._rng = rng or random.uniform
        self._cache_ttl_seconds = _require_float(
            "cache_ttl_seconds",
            cache_ttl_seconds,
            COLLECTOR_CACHE_TTL_MIN_SECONDS,
            COLLECTOR_CACHE_TTL_MAX_SECONDS,
        )
        self._rate_limit = _require_int(
            "rate_limit_per_minute",
            rate_limit_per_minute,
            COLLECTOR_RATE_LIMIT_MIN_PER_MINUTE,
            COLLECTOR_RATE_LIMIT_MAX_PER_MINUTE,
        )
        self._max_retries = _require_int(
            "max_retries",
            max_retries,
            COLLECTOR_MAX_RETRIES_MIN,
            COLLECTOR_MAX_RETRIES_MAX,
        )
        self._backoff_base = _require_float(
            "backoff_base_seconds",
            backoff_base_seconds,
            0,
            COLLECTOR_BACKOFF_BASE_MAX_SECONDS,
        )
        if self._backoff_base <= 0:
            raise ValueError("backoff_base_seconds must be positive")
        self._backoff_max = _require_float(
            "backoff_max_seconds",
            backoff_max_seconds,
            0,
            COLLECTOR_BACKOFF_CAP_MAX_SECONDS,
        )
        if self._backoff_max <= 0:
            raise ValueError("backoff_max_seconds must be positive")
        if self._backoff_max < self._backoff_base:
            raise ValueError(
                "backoff_max_seconds must be greater than or equal to "
                "backoff_base_seconds"
            )
        self.max_cache_entries = _require_int(
            "max_cache_entries",
            max_cache_entries,
            1,
            _MAX_CACHE_ENTRIES_LIMIT,
        )
        self._lock = threading.Lock()
        self._cache: "OrderedDict[Tuple, Tuple[float, Any]]" = OrderedDict()
        self._attempts: Deque[float] = deque()
        for name, protocol in _CAPABILITIES:
            if isinstance(inner, protocol):
                setattr(self, name, self._bind(name))

    def _bind(self, name: str) -> Callable:
        def method(*args: Any, **kwargs: Any) -> Any:
            return self._invoke(name, args, kwargs)

        method.__name__ = name
        return method

    def _invoke(self, name: str, args: tuple, kwargs: dict) -> Any:
        key = self._cache_key(name, args, kwargs)
        with self._lock:
            hit = self._recall(key)
        if hit is not _MISS:
            return hit
        result = self._call_upstream(name, args, kwargs)
        if result is None or key is None:
            return result
        with self._lock:
            self._remember(key, result)
        return copy.deepcopy(result)

    def _cache_key(self, name: str, args: tuple, kwargs: dict):
        method = getattr(self.inner, name)
        try:
            bound = inspect.signature(method).bind(*args, **kwargs)
        except TypeError:
            return None
        bound.apply_defaults()
        try:
            key = (name, tuple(bound.arguments.items()))
            hash(key)
        except TypeError:
            return None
        return key

    def _recall(self, key):
        if key is None or key not in self._cache:
            return _MISS
        stored_at, value = self._cache[key]
        age = self._clock() - stored_at
        if age >= self._cache_ttl_seconds:
            del self._cache[key]
            return _MISS
        self._cache.move_to_end(key)
        return copy.deepcopy(value)

    def _remember(self, key, result) -> None:
        now = self._clock()
        expired = [
            cached_key
            for cached_key, (stored_at, _value) in self._cache.items()
            if now - stored_at >= self._cache_ttl_seconds
        ]
        for cached_key in expired:
            del self._cache[cached_key]
        self._cache[key] = (now, copy.deepcopy(result))
        self._cache.move_to_end(key)
        while len(self._cache) > self.max_cache_entries:
            self._cache.popitem(last=False)

    def _call_upstream(self, name: str, args: tuple, kwargs: dict) -> Any:
        attempts = self._max_retries + 1
        last: Optional[BaseException] = None
        for attempt in range(attempts):
            self._take_token()
            try:
                return getattr(self.inner, name)(*args, **kwargs)
            except Exception as exc:
                if not _is_transient(exc):
                    raise
                last = exc
                if attempt + 1 == attempts:
                    break
                logger.warning(
                    "Transient data-provider failure on %s (%s); retrying",
                    name,
                    _public_type(exc),
                )
                delay = self._delay(attempt)
                if delay > 0:
                    self._sleep(delay)
        logger.error(
            "Data provider still failing on %s after %s attempts (%s)",
            name,
            attempts,
            _public_type(last) if last is not None else "unknown",
        )
        raise ProviderError(TEMPORARY_FAILURE_MESSAGE) from None

    def _delay(self, retry_index: int) -> float:
        ceiling = self._backoff_base * (2**retry_index)
        if ceiling > self._backoff_max:
            ceiling = self._backoff_max
        try:
            value = float(self._rng(0.0, ceiling))
        except (TypeError, ValueError):
            return ceiling
        if not math.isfinite(value) or value > ceiling:
            return ceiling
        if value < 0.0:
            return 0.0
        return value

    def _take_token(self) -> None:
        """Block until this upstream call fits in the last 60 seconds."""
        while True:
            with self._lock:
                now = self._clock()
                while (
                    self._attempts
                    and now - self._attempts[0] >= RATE_LIMIT_WINDOW_SECONDS
                ):
                    self._attempts.popleft()
                if len(self._attempts) < self._rate_limit:
                    self._attempts.append(now)
                    return
                # Calls a full window old were just removed, so this
                # wait is positive. Sleeping outside the lock lets a
                # cache hit on another thread proceed.
                wait = RATE_LIMIT_WINDOW_SECONDS - (now - self._attempts[0])
            self._sleep(wait)
