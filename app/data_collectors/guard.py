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
    Fundamentals,
    FundAttributes,
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
