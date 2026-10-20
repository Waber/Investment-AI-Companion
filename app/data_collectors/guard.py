"""
Cache, rate limit and retry in front of a real market-data collector.

``guard_collector(inner, policy)`` returns an object that has the same
capability methods as ``inner``, and only those. A call first looks in
a TTL cache, so a repeat call within the TTL does not reach the
provider. A cache miss takes an in-flight permit first. Only then does
it take a slot in the sliding-window rate limit and call the provider.
A second caller for a key that is already being fetched fails at once
instead of waiting. A ``TransientProviderError`` is retried after an
exponential backoff with full jitter; after the last retry it reaches
the caller. Rate-limit waits and retry sleeps share one deadline
(``total_deadline``), so they cannot stack into minutes. The deadline
does not kill the provider call itself; the Yahoo collector reads the
same budget and caps each HTTP request.

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
from collections import OrderedDict, deque
from dataclasses import dataclass
from functools import lru_cache
from typing import (
    Any,
    Callable,
    Deque,
    Dict,
    Hashable,
    List,
    Optional,
    Set,
    Tuple,
)

from app.data_collectors.base import (
    Fundamentals,
    FundAttributes,
    InstrumentLookup,
    PriceBar,
    PriceHistory,
    ProviderError,
    Sourced,
    TransientProviderError,
)
from app.data_collectors.call_budget import pop_budget, push_budget

logger = logging.getLogger(__name__)

# GuardPolicy field -> Settings attribute. One table, so a new limit is
# added in one place and cannot be read from the wrong setting.
_SETTING_NAMES = {
    "ttl_company_info": "COLLECTOR_CACHE_TTL_COMPANY_INFO_SECONDS",
    "ttl_key_metrics": "COLLECTOR_CACHE_TTL_KEY_METRICS_SECONDS",
    "ttl_price_history": "COLLECTOR_CACHE_TTL_PRICE_HISTORY_SECONDS",
    "ttl_fund_attributes": "COLLECTOR_CACHE_TTL_FUND_ATTRIBUTES_SECONDS",
    "ttl_no_data": "COLLECTOR_CACHE_TTL_NO_DATA_SECONDS",
    "cache_max_entries": "COLLECTOR_CACHE_MAX_ENTRIES",
    "rate_limit_calls": "COLLECTOR_RATE_LIMIT_CALLS",
    "rate_limit_period": "COLLECTOR_RATE_LIMIT_PERIOD_SECONDS",
    "rate_limit_max_wait": "COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS",
    "max_retries": "COLLECTOR_RETRY_MAX_RETRIES",
    "backoff_base": "COLLECTOR_BACKOFF_BASE_SECONDS",
    "backoff_max": "COLLECTOR_BACKOFF_MAX_SECONDS",
    "total_deadline": "COLLECTOR_TOTAL_DEADLINE_SECONDS",
    "max_inflight": "COLLECTOR_MAX_INFLIGHT",
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

    A TTL of 0 skips the cache for that capability. An argument that
    cannot be hashed skips it too. Either one also disables the
    one-leader de-dup, because there is no cache key to share.
    """

    ttl_company_info: int = 86400
    ttl_key_metrics: int = 3600
    ttl_price_history: int = 900
    ttl_fund_attributes: int = 86400
    ttl_no_data: int = 300
    cache_max_entries: int = 256
    rate_limit_calls: int = 30
    rate_limit_period: float = 60.0
    rate_limit_max_wait: float = 5.0
    max_retries: int = 2
    backoff_base: float = 1.0
    backoff_max: float = 8.0
    # One budget for the sleeps of a single call (rate-limit wait and
    # retry backoff together). The provider call is not interrupted.
    total_deadline: float = 15.0
    # Provider calls allowed to run at the same time. A further call
    # fails immediately. Cache hits do not take a permit.
    max_inflight: int = 4

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
    """``(method, ((name, value), ...))``, or None when not hashable.

    A ``ticker`` string is stripped and uppercased in the key only, so
    ``aapl`` and ``AAPL`` share one entry. The arguments forwarded to
    the inner collector stay exactly as the caller sent them. Yahoo
    normalizes again before it builds a ``yf.Ticker``.
    """
    normalized = {}
    for name, value in arguments.items():
        if name == "ticker" and isinstance(value, str):
            normalized[name] = value.strip().upper()
        else:
            normalized[name] = value
    key = (method_name, tuple(normalized.items()))
    try:
        hash(key)
    except TypeError:
        # A list or dict argument. Capability arguments are strings, so
        # this is defensive: the call still works, it skips the cache.
        return None
    return key


def _context_counts(exc: BaseException) -> bool:
    """Whether ``exc.__context__`` may still be a reason to retry.

    ``__context__`` is the error being handled when ``raise`` ran inside
    ``except``. Follow it only for a ``ProviderError`` wrapper.

    ``raise New() from Old()`` sets ``__suppress_context__`` even when
    ``Old`` is not ``None``. The traceback then prints ``Old`` and hides
    ``__context__``, but the attribute is still there. The wrapper test
    does ``raise ProviderError from ValueError`` inside
    ``except TransientProviderError``, so the transient error is only
    on ``__context__`` and suppress is already true. That wrapper is
    still retried, because it has an explicit cause.

    ``raise KeyError(...) from None`` leaves the same transient error
    on ``__context__``. A ``KeyError`` is not a provider wrapper, so
    the link is ignored. ``raise ProviderError(...) from None`` has no
    cause and suppress is true, so its context is ignored too.
    """
    if not isinstance(exc, ProviderError):
        return False
    if not exc.__suppress_context__:
        return True
    return exc.__cause__ is not None


def _has_transient(exc: BaseException) -> bool:
    """True when ``exc`` or an allowed linked error is transient.

    ``__cause__`` (``raise New() from Old()``) is always followed.
    ``__context__`` is followed only when :func:`_context_counts` says
    so. The walk does not read the exception text, which can contain a
    URL or a response body.
    """
    seen = set()
    stack = [exc]
    while stack:
        current = stack.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, TransientProviderError):
            return True
        stack.append(current.__cause__)
        if _context_counts(current):
            stack.append(current.__context__)
    return False


# A missing cache entry. ``None`` is a real "no data" result, so it
# cannot be the missing marker.
_MISS = object()


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
        # How many provider calls may run at once. ``acquire(blocking=
        # False)`` is Java's ``Semaphore.tryAcquire``: it fails at once
        # instead of parking another worker. The permit is taken before
        # the rate-limit wait, so a rejected call does not sleep and
        # does not record a token. Cache hits do not take one.
        self._inflight = threading.BoundedSemaphore(policy.max_inflight)
        # Keys whose leader is inside the provider call. A second miss
        # for one of these fails at once. It does not wait: waiting
        # would hold a server worker with no permit.
        self._flights: Set[Hashable] = set()

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
            # A second miss while this key is already being fetched
            # fails at once. It does not wait on the leader.
            return self._coalesced(key, method_name, method, bound, ttl)
        # No cache key: the TTL is 0, or an argument cannot be hashed.
        # There is nothing to share, so this calls the provider directly.
        return self._call_provider(method_name, method, bound)

    def _coalesced(
        self,
        key: Hashable,
        method_name: str,
        method: Callable[..., Any],
        bound: inspect.BoundArguments,
        ttl: int,
    ) -> Any:
        """One leader per key. A second caller does not wait.

        Waiting held a worker for up to the whole deadline and did not
        take an in-flight permit, so a burst of one ticker could fill
        the server's thread pool. The follower raises ``ProviderError``
        at once (HTTP 502). It takes no permit and no rate-limit token.
        The leader still makes one upstream call. Its result is cached,
        so a later request for that key does not call the provider.
        """
        ticker = bound.arguments.get("ticker")
        with self._lock:
            cached = self._lookup_locked(key)
            if cached is not _MISS:
                leader = False
                busy = False
            elif key in self._flights:
                cached = None
                leader = False
                busy = True
            else:
                self._flights.add(key)
                cached = None
                leader = True
                busy = False
        if not leader and not busy:
            return copy.deepcopy(cached)
        if busy:
            logger.warning(
                "Duplicate in-flight fetch for %s %r", method_name, ticker
            )
            raise ProviderError(
                "A collector call for this ticker is already in flight"
            )
        try:
            result = self._call_provider(method_name, method, bound)
            self._remember(key, result, ttl)
            return result
        finally:
            with self._lock:
                self._flights.discard(key)

    def _remember(self, key: Hashable, result: Any, ttl: int) -> None:
        """Store ``result`` for ``ttl`` seconds, or skip a short no-data.

        A "no data" answer (None) is kept for a shorter time: yfinance
        can report a hidden HTTP failure as None, and the full TTL (up
        to 24 h) would make one blip a long false "not found". ``min``
        keeps the capability TTL as the cap.
        """
        stored_ttl = (
            ttl if result is not None else min(ttl, self._policy.ttl_no_data)
        )
        if stored_ttl > 0:
            self._cache_put(key, result, stored_ttl)

    def _call_provider(
        self,
        method_name: str,
        method: Callable[..., Any],
        bound: inspect.BoundArguments,
    ) -> Any:
        """Call the provider under the rate limit, retrying if transient.

        The in-flight permit is taken first, with ``acquire(blocking=
        False)``. A full pool raises before any rate-limit sleep and
        before a token is recorded. The permit stays held through the
        rate-limit wait and the provider call, then ``finally`` releases
        it before a retry sleep. Only ``TransientProviderError`` is
        retried. Every attempt takes its own rate-limit slot.
        """
        ticker = bound.arguments.get("ticker")
        retries = self._policy.max_retries
        attempt = 1
        # One clock for every sleep in this call. The provider call
        # itself is not interrupted; Yahoo reads the same budget.
        started = self._clock()
        token = push_budget(started + self._policy.total_deadline, self._clock)
        try:
            while True:
                if not self._inflight.acquire(blocking=False):
                    logger.warning(
                        "In-flight limit reached for %s %r",
                        method_name,
                        ticker,
                    )
                    raise ProviderError(
                        "Too many collector calls are in flight"
                    )
                try:
                    self._acquire_slot(method_name, ticker, started)
                    try:
                        return method(*bound.args, **bound.kwargs)
                    except Exception as exc:
                        if not self._should_retry(exc, attempt, retries):
                            if isinstance(exc, ProviderError):
                                raise
                            # A raw ValueError used to become HTTP 400
                            # and copy its text into the body. The fixed
                            # message has no provider text, and
                            # ``from None`` drops the chain so the text
                            # is not attached.
                            logger.warning(
                                "Unexpected %s in %s for %r",
                                type(exc).__name__,
                                method_name,
                                ticker,
                            )
                            raise ProviderError(
                                "Data provider error"
                            ) from None
                        delay = self._backoff_delay(attempt)
                        # The inner collector logged the provider text.
                        # This line names the class, the method and the
                        # ticker.
                        logger.warning(
                            "Transient %s in %s for %r; "
                            "retry %d of %d in %.2f s",
                            type(exc).__name__,
                            method_name,
                            ticker,
                            attempt,
                            retries,
                            delay,
                        )
                finally:
                    self._inflight.release()
                self._sleep_within_deadline(
                    started, delay, method_name, ticker
                )
                attempt += 1
        finally:
            pop_budget(token)

    def _should_retry(
        self, exc: BaseException, attempt: int, retries: int
    ) -> bool:
        """True when a transient error is still allowed another try.

        ``TransientProviderError`` counts when it is the error itself
        or its ``__cause__`` (``raise New from Old``). ``__context__``
        counts only for a ``ProviderError`` wrapper; see
        :func:`_context_counts`. The walk does not read the text.
        """
        if attempt > retries:
            return False
        return _has_transient(exc)

    def _acquire_slot(
        self, method_name: str, ticker: Any, started: float
    ) -> None:
        """Wait for a free slot in the sliding window, or fail.

        The caller already holds an in-flight permit. This method
        records a timestamp only when that permit is held and a slot
        is free, so a call rejected for the in-flight limit never
        burns a token. At most ``rate_limit_calls`` provider calls may
        start within any ``rate_limit_period``. When the window is
        full, wait until the oldest call leaves it, as long as the
        total wait stays within ``rate_limit_max_wait``. Otherwise
        raise a plain ``ProviderError`` without calling the provider.
        It is not transient, because a retry would only wait again.
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
                    "Rate limit reached for %s %r: %d calls per %g s",
                    method_name,
                    ticker,
                    self._policy.rate_limit_calls,
                    period,
                )
                raise ProviderError("Local rate limit reached")
            # Sleep outside the lock, then check again: another thread
            # may have taken the slot meanwhile. A sleep that would
            # pass the call's deadline is refused.
            self._sleep_within_deadline(started, wait, method_name, ticker)
            waited += wait

    def _sleep_within_deadline(
        self,
        started: float,
        delay: float,
        method_name: str,
        ticker: Any,
    ) -> None:
        """Sleep, unless this wait would pass the call's deadline.

        The clock does not interrupt a provider call that is already
        running. It only refuses the next sleep.
        """
        remaining = self._policy.total_deadline - (self._clock() - started)
        if delay > remaining:
            logger.warning(
                "Deadline reached for %s %r after %.2f s",
                method_name,
                ticker,
                self._clock() - started,
            )
            raise ProviderError("Collector deadline reached")
        self._sleep(delay)

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

    def _cache_get(self, key: Hashable) -> Tuple[bool, Any]:
        """``(True, copy)`` for a live entry, ``(False, None)`` otherwise.

        A flag is needed because ``None`` ("no data") is a valid cached
        value. Expired entries are removed when found.
        """
        with self._lock:
            value = self._lookup_locked(key)
        if value is _MISS:
            return False, None
        # Deep copy: Sourced is frozen, but its dict value is not. A
        # caller that edits its result must not change the next hit.
        # The stored value is never mutated, so copying outside the
        # lock is safe.
        return True, copy.deepcopy(value)

    def _lookup_locked(self, key: Hashable) -> Any:
        """The stored value, or ``_MISS``. The caller holds ``_lock``.

        Expired entries are removed. ``None`` ("no data") is returned
        as itself, which is why the missing marker is a separate object.
        """
        now = self._clock()
        entry = self._cache.get(key)
        if entry is None:
            return _MISS
        expires_at, value = entry
        if now >= expires_at:
            del self._cache[key]
            return _MISS
        self._cache.move_to_end(key)
        return value

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
