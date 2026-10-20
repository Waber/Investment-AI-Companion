"""The collector guard in fake time.

Tests the capabilities, the cache, the rate limit, retries and threads.
"""

import logging
import threading
import time
from collections import deque

import pytest

from app.data_collectors.base import (
    Fundamentals,
    FundAttributes,
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


def test_no_data_expires_at_the_no_data_ttl():
    inner = SpyCollector()
    clock = FakeClock()
    guarded = make(inner, clock, ttl_company_info=100, ttl_no_data=10)
    guarded.fetch_company_info("UNKNOWN")
    guarded.fetch_company_info("DEMO_PL_TECH")

    clock.advance(10)
    guarded.fetch_company_info("UNKNOWN")
    guarded.fetch_company_info("DEMO_PL_TECH")

    # "No data" was fetched again; the real value is still cached.
    assert inner.calls == [
        ("fetch_company_info", "UNKNOWN"),
        ("fetch_company_info", "DEMO_PL_TECH"),
        ("fetch_company_info", "UNKNOWN"),
    ]


def test_no_data_ttl_zero_never_caches_no_data():
    inner = SpyCollector()
    guarded = make(inner, FakeClock(), ttl_no_data=0)

    guarded.fetch_company_info("UNKNOWN")
    guarded.fetch_company_info("UNKNOWN")
    guarded.fetch_company_info("DEMO_PL_TECH")
    guarded.fetch_company_info("DEMO_PL_TECH")

    assert inner.calls == [
        ("fetch_company_info", "UNKNOWN"),
        ("fetch_company_info", "UNKNOWN"),
        ("fetch_company_info", "DEMO_PL_TECH"),
    ]


def test_no_data_ttl_is_capped_by_the_capability_ttl():
    inner = SpyCollector()
    clock = FakeClock()
    guarded = make(inner, clock, ttl_company_info=5, ttl_no_data=300)
    guarded.fetch_company_info("UNKNOWN")

    clock.advance(5)
    guarded.fetch_company_info("UNKNOWN")

    assert len(inner.calls) == 2


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


def test_unexpected_exception_becomes_a_provider_error_and_is_not_cached(
    caplog,
):
    """A KeyError is not a 400 and its text is not kept."""
    value = sourced({"name": "Acme"})
    inner = ScriptedLookup(KeyError("provider secret text"), value)
    guarded = make(inner, FakeClock())

    with caplog.at_level(logging.WARNING, logger="app.data_collectors.guard"):
        with pytest.raises(
            ProviderError, match="Data provider error"
        ) as caught:
            guarded.fetch_company_info("ACME")

    assert caught.value.__cause__ is None
    assert "provider secret text" not in caplog.text
    assert "KeyError" in caplog.text
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
        # The 50 s wait is the rate-limit window. The deadline would
        # refuse it at the default of 15 s, which is a different test.
        total_deadline=120,
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
        # The third attempt waits out the 60 s window. That is longer
        # than the default deadline, which is tested on its own.
        total_deadline=120,
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
    assert "fetch_company_info" in caplog.text
    guard_records = [
        record
        for record in caplog.records
        if record.name == "app.data_collectors.guard"
        and (
            "retry 1 of 2" in record.getMessage()
            or "Rate limit reached" in record.getMessage()
        )
    ]
    assert len(guard_records) == 2
    assert {r.levelno for r in guard_records} == {logging.WARNING}


def test_threads_never_exceed_the_rate_limit():
    clock = FakeClock()
    inner = CountingLookup()
    guarded = make(inner, clock, rate_limit_calls=3, rate_limit_max_wait=0)
    barrier = threading.Barrier(10)
    outcomes = []

    class SlowLenDeque(deque):
        """A deque whose len() pauses after it counts.

        In CPython the GIL makes the guard's check-then-append almost
        atomic, so a missing lock would go unnoticed. The pause opens
        the window between "is there room?" and "take the slot", so
        without the lock more than 3 threads get through. With the
        lock, the other threads wait and the test passes.
        """

        def __len__(self):
            size = super().__len__()
            time.sleep(0.001)
            return size

    guarded._calls = SlowLenDeque()

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

    assert not any(thread.is_alive() for thread in threads)
    assert outcomes.count("ok") == 3
    assert outcomes.count("limited") == 7
    assert inner.calls == 3


def test_total_rate_limit_wait_is_bounded_and_lock_is_free_while_sleeping():
    clock = FakeClock()
    inner = CountingLookup()
    lock_states = []
    stolen = []

    def sleep(seconds):
        lock_states.append(guarded._lock.locked())
        clock.sleep(seconds)
        if not stolen:
            # Another "thread" takes the slot that just freed up, as a
            # real second request could while this one was sleeping.
            with guarded._lock:
                guarded._calls.append(clock())
            stolen.append(True)

    guarded = guard_collector(
        inner,
        GuardPolicy(
            rate_limit_calls=1,
            rate_limit_period=10,
            rate_limit_max_wait=15,
        ),
        clock=clock,
        sleep=sleep,
    )
    # The window is full: the one slot was taken just now.
    guarded._calls.append(clock())

    with pytest.raises(ProviderError) as excinfo:
        guarded.fetch_company_info("ACME")

    # First wait: 10 s (within 15). Second wait would be 10 s more: the
    # total 20 s is over the max, although each wait alone is not.
    assert type(excinfo.value) is ProviderError
    assert clock.sleeps == [10]
    assert inner.calls == 0
    assert lock_states == [False]


def test_lock_is_not_held_during_the_provider_call():
    seen = []

    class LockProbe:
        def fetch_company_info(self, ticker):
            seen.append(guarded._lock.locked())
            return sourced({"name": ticker})

    guarded = make(LockProbe(), FakeClock())

    guarded.fetch_company_info("ACME")

    assert seen == [False]


def test_a_sleep_past_the_deadline_is_refused():
    """A 10 s rate-limit wait does not run when the deadline is 6 s."""
    clock = FakeClock()
    inner = CountingLookup()
    guarded = make(
        inner,
        clock,
        rate_limit_calls=1,
        rate_limit_period=10,
        rate_limit_max_wait=30,
        total_deadline=6,
    )
    guarded._calls.append(clock())

    with pytest.raises(ProviderError, match="deadline") as caught:
        guarded.fetch_company_info("ACME")

    assert type(caught.value) is ProviderError
    assert clock.sleeps == []
    assert inner.calls == 0


def test_retry_backoff_past_the_deadline_is_refused():
    clock = FakeClock()
    inner = ScriptedLookup(
        TransientProviderError("busy"), sourced({"name": "Acme"})
    )
    guarded = make(
        inner,
        clock,
        rand=lambda: 1.0,
        backoff_base=10,
        backoff_max=10,
        total_deadline=5,
    )

    with pytest.raises(ProviderError, match="deadline"):
        guarded.fetch_company_info("ACME")

    assert inner.calls == 1
    assert clock.sleeps == []


def test_transient_error_on_context_is_retried():
    """``raise ProviderError from ValueError`` keeps the transient error.

    Inside ``except TransientProviderError``, that ``raise ... from``
    puts the transient error on ``__context__`` and the ValueError on
    ``__cause__``. The wrapper still retries. The secret stays out of
    the log and out of the final message.
    """

    class Buried:
        def __init__(self):
            self.calls = 0

        def fetch_company_info(self, ticker):
            self.calls += 1
            if self.calls == 1:
                try:
                    raise TransientProviderError("provider secret text")
                except TransientProviderError:
                    raise ProviderError("fixed") from ValueError("other")
            return sourced({"name": "Acme"})

    inner = Buried()
    guarded = make(inner, FakeClock(), rand=lambda: 0.0)
    assert guarded.fetch_company_info("ACME").value["name"] == "Acme"
    assert inner.calls == 2


def test_cache_key_normalizes_ticker_and_upstream_gets_the_raw_one():
    inner = ScriptedLookup(sourced({"name": "Acme"}))
    guarded = make(inner, FakeClock())

    first = guarded.fetch_company_info(" aapl ")
    second = guarded.fetch_company_info("AAPL")

    assert second == first
    assert inner.calls == 1
    assert inner.tickers == [" aapl "]


def test_in_flight_limit_fails_immediately_and_releases():
    entered = threading.Event()
    release = threading.Event()

    class Blocking:
        def __init__(self):
            self.calls = 0

        def fetch_company_info(self, ticker):
            self.calls += 1
            entered.set()
            assert release.wait(timeout=5)
            return sourced({"name": ticker})

    inner = Blocking()
    guarded = make(inner, FakeClock(), max_inflight=1)
    holder = threading.Thread(target=lambda: guarded.fetch_company_info("ONE"))
    holder.start()
    assert entered.wait(timeout=5)

    with pytest.raises(ProviderError, match="in flight"):
        guarded.fetch_company_info("TWO")

    release.set()
    holder.join(timeout=5)

    assert not holder.is_alive()
    assert inner.calls == 1
    assert guarded.fetch_company_info("THREE").value["name"] == "THREE"
    assert inner.calls == 2


def test_cache_hit_does_not_need_an_in_flight_permit():
    entered = threading.Event()
    release = threading.Event()

    class Blocking:
        def fetch_company_info(self, ticker):
            if ticker == "HOLD":
                entered.set()
                assert release.wait(timeout=5)
            return sourced({"name": ticker})

    guarded = make(Blocking(), FakeClock(), max_inflight=1)
    assert guarded.fetch_company_info("CACHED").value["name"] == "CACHED"
    holder = threading.Thread(
        target=lambda: guarded.fetch_company_info("HOLD")
    )
    holder.start()
    assert entered.wait(timeout=5)

    assert guarded.fetch_company_info("CACHED").value["name"] == "CACHED"

    release.set()
    holder.join(timeout=5)
    assert not holder.is_alive()


def test_simultaneous_misses_for_one_key_share_one_call():
    entered = threading.Event()
    release = threading.Event()

    class Once:
        def __init__(self):
            self.calls = 0
            self.tickers = []
            self._lock = threading.Lock()

        def fetch_company_info(self, ticker):
            with self._lock:
                self.calls += 1
                self.tickers.append(ticker)
            entered.set()
            assert release.wait(timeout=5)
            return sourced({"name": "Acme"})

    inner = Once()
    guarded = make(inner, FakeClock(), max_inflight=4)
    waited = []
    real_wait = guarded._wait_for_flight

    def spy_wait(flight, started, method_name, bound):
        waited.append(bound.arguments.get("ticker"))
        return real_wait(flight, started, method_name, bound)

    guarded._wait_for_flight = spy_wait
    results = []
    errors = []

    def worker(ticker):
        try:
            results.append(guarded.fetch_company_info(ticker))
        except Exception as exc:  # pragma: no cover - the assertions below
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=("aapl",)),
        threading.Thread(target=worker, args=("AAPL",)),
    ]
    for thread in threads:
        thread.start()
    assert entered.wait(timeout=5)
    deadline = time.monotonic() + 2
    while not waited and time.monotonic() < deadline:
        time.sleep(0.01)
    assert waited, "the second caller did not wait for the first"
    assert inner.calls == 1
    release.set()
    for thread in threads:
        thread.join(timeout=5)

    assert not any(thread.is_alive() for thread in threads)
    assert errors == []
    assert inner.calls == 1
    assert inner.tickers == ["aapl"] or inner.tickers == ["AAPL"]
    assert len(results) == 2
    assert results[0] == results[1]
    assert results[0].value["name"] == "Acme"
    # The waiter saw the raw ticker it was given, not the cache key.
    assert waited[0] in ("aapl", "AAPL")
    assert waited[0] != inner.tickers[0]
