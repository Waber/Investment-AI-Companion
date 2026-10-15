"""Cache, rate limit and retry around a collector. Offline, no sleeps.

The clock and ``sleep`` are fakes, so a 60-second rate-limit wait is an
addition on a number, not a real pause. ``FakeCollector`` supplies the
success paths. Stubs supply errors a fake never raises.
"""

import ast
import asyncio
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import anyio
import pytest
import requests

from app.api.data_collection import get_collector, reset_cached_collector
from app.core.config import Settings, settings
from app.data_collectors import yahoo_finance
from app.data_collectors.base import (
    Fundamentals,
    FundAttributes,
    InstrumentLookup,
    PriceHistory,
    Provenance,
    ProviderError,
    Sourced,
)
from app.data_collectors.fake import FakeCollector
from app.data_collectors.resilience import (
    DEFAULT_MAX_CACHE_ENTRIES,
    TEMPORARY_FAILURE_MESSAGE,
    ResilientCollector,
)
from tests.collector_stubs import sourced

FETCH_URL = "/api/v1/data-collection/fetch-company"
RESILIENCE_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "data_collectors"
    / "resilience.py"
)
ENV_EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"

_LIMIT_NAMES = (
    "COLLECTOR_CACHE_TTL_SECONDS",
    "COLLECTOR_RATE_LIMIT_PER_MINUTE",
    "COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS",
    "COLLECTOR_TOTAL_DEADLINE_SECONDS",
    "COLLECTOR_MAX_INFLIGHT",
    "COLLECTOR_MAX_RETRIES",
    "COLLECTOR_BACKOFF_BASE_SECONDS",
    "COLLECTOR_BACKOFF_MAX_SECONDS",
)


class FakeClock:
    """A monotonic clock. ``sleep`` moves it forward and records the wait."""

    def __init__(self):
        self.now = 0.0
        self.slept = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


class YFRateLimitError(Exception):
    """Same class name as yfinance, without importing yfinance."""

    def __init__(self):
        super().__init__(
            "Too Many Requests. Rate limited. secret-host.example/v8"
        )


class Flaky:
    """Fails with ``error`` for the first ``failures`` calls, then succeeds."""

    def __init__(self, error, failures=None):
        self.error = error
        self.failures = failures
        self.calls = 0

    def fetch_company_info(self, ticker):
        self.calls += 1
        if self.failures is None or self.calls <= self.failures:
            raise self.error
        return sourced({"ticker": ticker, "n": self.calls})


class CompanyOnly:
    def fetch_company_info(self, ticker):
        return sourced({"ticker": ticker})


class CountingFake(FakeCollector):
    def __init__(self, clock=None):
        super().__init__(clock=clock or (lambda: _fixed_time()))
        self.calls = 0

    def fetch_company_info(self, ticker):
        self.calls += 1
        return super().fetch_company_info(ticker)

    def fetch_price_history(self, ticker, period="1y", interval="1d"):
        self.calls += 1
        return super().fetch_price_history(ticker, period, interval)


def _fixed_time():
    return datetime(2026, 9, 30, 18, 0, tzinfo=timezone.utc)


def _wrap(inner, **overrides):
    clock = overrides.pop("clock", None) or FakeClock()
    sleep = overrides.pop("sleep", None)
    if sleep is None:
        sleep = clock.sleep
    settings = {
        "clock": clock,
        "sleep": sleep,
        "rng": lambda low, high: high,
        "cache_ttl_seconds": 30,
        "rate_limit_per_minute": 100,
        "max_retries": 2,
        "backoff_base_seconds": 0.5,
        "backoff_max_seconds": 8,
        "max_cache_entries": 8,
    }
    settings.update(overrides)
    return ResilientCollector(inner, **settings), clock


def _build_settings(monkeypatch, **env):
    for name in _LIMIT_NAMES:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return Settings(_env_file=None)


def test_cache_hit_keeps_the_original_retrieved_at():
    """A hit returns the first fetch's provenance, not a new timestamp."""
    moments = []

    def provider_clock():
        moments.append(
            datetime(2026, 1, 1, len(moments) + 1, tzinfo=timezone.utc)
        )
        return moments[-1]

    inner = CountingFake(clock=provider_clock)
    wrapped, clock = _wrap(inner, cache_ttl_seconds=10)
    first = wrapped.fetch_company_info("DEMO_PL_TECH")
    clock.now = 9
    second = wrapped.fetch_company_info("DEMO_PL_TECH")

    assert inner.calls == 1
    assert second.provenance.retrieved_at == first.provenance.retrieved_at
    assert second.provenance == first.provenance
    assert second.provenance.synthetic is True
    assert second.value == first.value
    assert second.value is not first.value
    clock.now = 10
    third = wrapped.fetch_company_info("DEMO_PL_TECH")
    assert inner.calls == 2
    assert third.provenance.retrieved_at != first.provenance.retrieved_at


def test_cache_key_strips_and_uppercases_the_ticker():
    """``aapl`` and ``AAPL`` are one cache entry. The inner call is raw.

    The wrapper does not rewrite the argument it forwards. Only the
    key is normalized, so a later canonical ticker still hits.
    """

    class AnyTicker:
        def __init__(self):
            self.calls = 0
            self.seen = []

        def fetch_company_info(self, ticker):
            self.calls += 1
            self.seen.append(ticker)
            return sourced({"ticker": ticker})

        def fetch_price_history(self, ticker, period="1y", interval="1d"):
            self.calls += 1
            self.seen.append((ticker, period, interval))
            return sourced([{"ticker": ticker, "period": period}])

    inner = AnyTicker()
    wrapped, _clock = _wrap(inner)
    wrapped.fetch_company_info(" aapl ")
    second = wrapped.fetch_company_info("AAPL")

    assert inner.calls == 1
    assert inner.seen == [" aapl "]
    assert second.value["ticker"] == " aapl "

    wrapped.fetch_price_history(" msft ", period="1mo")
    wrapped.fetch_price_history("MSFT", "1mo", "1d")
    assert inner.calls == 2
    assert inner.seen[-1] == (" msft ", "1mo", "1d")


def test_mutating_a_hit_does_not_change_the_cached_value():
    inner = CountingFake()
    wrapped, _clock = _wrap(inner)
    first = wrapped.fetch_price_history("DEMO_PL_TECH", "1mo")
    first.value.clear()
    second = wrapped.fetch_price_history(
        "DEMO_PL_TECH", period="1mo", interval="1d"
    )

    assert inner.calls == 1
    assert len(second.value) == 21


def test_no_data_and_errors_are_not_cached():
    inner = CountingFake()
    wrapped, _clock = _wrap(inner)
    assert wrapped.fetch_company_info("NO_SUCH") is None
    assert wrapped.fetch_company_info("NO_SUCH") is None
    assert inner.calls == 2

    failing = Flaky(ProviderError("parse failed secret-token"))
    wrapped_fail, _clock = _wrap(failing, max_retries=1)
    with pytest.raises(ProviderError, match="parse failed"):
        wrapped_fail.fetch_company_info("AAA")
    with pytest.raises(ProviderError, match="parse failed"):
        wrapped_fail.fetch_company_info("AAA")
    assert failing.calls == 2


def test_cache_drops_the_least_recently_used_entry():
    inner = CountingFake()
    wrapped, _clock = _wrap(inner, max_cache_entries=2)
    wrapped.fetch_company_info("DEMO_PL_TECH")
    wrapped.fetch_company_info("DEMO_US_GROWTH")
    wrapped.fetch_company_info("DEMO_DE_INDUSTRY")
    before = inner.calls
    wrapped.fetch_company_info("DEMO_US_GROWTH")
    assert inner.calls == before
    wrapped.fetch_company_info("DEMO_PL_TECH")
    assert inner.calls == before + 1


def test_rate_limit_blocks_until_the_oldest_call_ages_out():
    inner = FakeCollector()
    wrapped, clock = _wrap(
        inner,
        rate_limit_per_minute=2,
        rate_limit_max_wait_seconds=60,
        total_deadline_seconds=120,
    )
    wrapped.fetch_company_info("DEMO_PL_TECH")
    wrapped.fetch_company_info("DEMO_US_GROWTH")
    started = time.perf_counter()
    wrapped.fetch_company_info("DEMO_DE_INDUSTRY")
    elapsed = time.perf_counter() - started

    # Both earlier calls are 60 seconds old, so one wait clears two slots
    # and the following call fits in the new window.
    assert elapsed < 1
    assert clock.slept == [60.0]
    wrapped.fetch_company_info("DEMO_JP_STABLE")
    assert clock.slept == [60.0]

    staggered, staggered_clock = _wrap(
        inner,
        rate_limit_per_minute=2,
        rate_limit_max_wait_seconds=60,
        total_deadline_seconds=120,
    )
    staggered.fetch_company_info("DEMO_PL_TECH")
    staggered_clock.now = 10
    staggered.fetch_company_info("DEMO_US_GROWTH")
    staggered.fetch_company_info("DEMO_DE_INDUSTRY")
    assert staggered_clock.slept == [50.0]


def test_cache_hits_do_not_spend_rate_limit_tokens():
    inner = FakeCollector()
    wrapped, clock = _wrap(
        inner,
        rate_limit_per_minute=1,
        rate_limit_max_wait_seconds=60,
        total_deadline_seconds=120,
    )
    wrapped.fetch_company_info("DEMO_PL_TECH")
    wrapped.fetch_company_info("DEMO_PL_TECH")
    assert clock.slept == []
    wrapped.fetch_company_info("DEMO_US_GROWTH")
    assert clock.slept == [60.0]


def test_rate_limit_wait_over_the_cap_fails_without_a_slot():
    """A wait longer than the cap fails immediately and takes no slot.

    The fake clock records the sleep. A rejected call must not move it,
    and must not be remembered: once the original slot ages out, the
    next call goes straight through.
    """
    inner = CountingFake()
    wrapped, clock = _wrap(
        inner,
        rate_limit_per_minute=1,
        rate_limit_max_wait_seconds=5,
    )
    wrapped.fetch_company_info("DEMO_PL_TECH")
    clock.now = 10
    with pytest.raises(ProviderError) as caught:
        wrapped.fetch_company_info("DEMO_US_GROWTH")

    assert str(caught.value) == TEMPORARY_FAILURE_MESSAGE
    assert caught.value.__cause__ is None
    assert clock.slept == []
    assert clock.now == 10
    assert inner.calls == 1

    clock.now = 60
    wrapped.fetch_company_info("DEMO_US_GROWTH")
    assert inner.calls == 2
    assert clock.slept == []


def test_rate_limit_wait_equal_to_the_cap_still_waits():
    inner = CountingFake()
    wrapped, clock = _wrap(
        inner,
        rate_limit_per_minute=1,
        rate_limit_max_wait_seconds=5,
    )
    wrapped.fetch_company_info("DEMO_PL_TECH")
    clock.now = 55
    wrapped.fetch_company_info("DEMO_US_GROWTH")
    assert clock.slept == [5.0]
    assert inner.calls == 2


def test_inflight_limit_fails_the_extra_call_without_waiting():
    """One permit. A second call does not sit on the rate-limit wait.

    The first call is inside the upstream fetch, so the rate-limit
    window is full and a waiter would sleep. The inflight limit
    refuses the second call before that sleep and does not take a slot.
    """
    entered = threading.Event()
    release = threading.Event()

    class Holding:
        def fetch_company_info(self, ticker):
            entered.set()
            assert release.wait(timeout=5)
            return sourced({"ticker": ticker})

    clock = FakeClock()
    wrapped, _clock = _wrap(
        Holding(),
        clock=clock,
        sleep=clock.sleep,
        rate_limit_per_minute=1,
        rate_limit_max_wait_seconds=60,
        total_deadline_seconds=120,
        max_inflight=1,
    )
    holder = threading.Thread(target=wrapped.fetch_company_info, args=("AAA",))
    holder.start()
    assert entered.wait(timeout=2)
    try:
        with pytest.raises(ProviderError) as caught:
            wrapped.fetch_company_info("BBB")
        assert str(caught.value) == TEMPORARY_FAILURE_MESSAGE
        assert clock.slept == []
        assert len(wrapped._attempts) == 1
    finally:
        release.set()
        holder.join(timeout=2)
    assert not holder.is_alive()


def test_a_second_thread_fails_fast_inside_the_rate_limit_cap():
    """Limit of 1, two real threads. The second call must not block.

    The first call is inside the upstream fetch, holding the only
    slot. The second would otherwise sleep for nearly 60 seconds.
    The cap is 5 seconds. Failing fast means the real clock moves
    far less than that, and the rejected call does not take a slot.
    """
    entered = threading.Event()
    release = threading.Event()

    class Holding:
        def fetch_company_info(self, ticker):
            entered.set()
            assert release.wait(timeout=5)
            return sourced({"ticker": ticker})

    wrapped, _clock = _wrap(
        Holding(),
        clock=time.monotonic,
        sleep=time.sleep,
        rate_limit_per_minute=1,
        rate_limit_max_wait_seconds=5,
    )
    holder = threading.Thread(target=wrapped.fetch_company_info, args=("AAA",))
    holder.start()
    assert entered.wait(timeout=2)
    started = time.monotonic()
    try:
        with pytest.raises(ProviderError) as caught:
            wrapped.fetch_company_info("BBB")
        elapsed = time.monotonic() - started
        assert str(caught.value) == TEMPORARY_FAILURE_MESSAGE
        assert elapsed < 1.0
        assert len(wrapped._attempts) == 1
    finally:
        release.set()
        holder.join(timeout=2)
    assert not holder.is_alive()


def test_deadline_cuts_off_retries_before_the_next_sleep():
    """Retries and waits together stay inside the deadline.

    The fake clock only moves when the wrapper sleeps. A backoff that
    would pass the deadline is not slept, and the error is the same
    fixed provider sentence.
    """
    inner = Flaky(YFRateLimitError())
    wrapped, clock = _wrap(
        inner,
        max_retries=4,
        backoff_base_seconds=0.5,
        backoff_max_seconds=8,
        total_deadline_seconds=1,
    )
    with pytest.raises(ProviderError) as caught:
        wrapped.fetch_company_info("AAA")

    assert str(caught.value) == TEMPORARY_FAILURE_MESSAGE
    assert caught.value.__cause__ is None
    assert "secret-host" not in str(caught.value)
    assert clock.slept == [0.5]
    assert sum(clock.slept) <= 1
    assert inner.calls == 2


def test_a_spent_deadline_does_not_start_another_upstream_call():
    inner = Flaky(YFRateLimitError())
    wrapped, clock = _wrap(
        inner,
        max_retries=2,
        backoff_base_seconds=1,
        backoff_max_seconds=1,
        total_deadline_seconds=1,
    )
    with pytest.raises(ProviderError) as caught:
        wrapped.fetch_company_info("AAA")

    assert str(caught.value) == TEMPORARY_FAILURE_MESSAGE
    assert clock.slept == [1.0]
    assert inner.calls == 1


def test_deadline_refuses_a_rate_limit_wait_that_would_not_fit():
    inner = CountingFake()
    wrapped, clock = _wrap(
        inner,
        rate_limit_per_minute=1,
        rate_limit_max_wait_seconds=60,
        total_deadline_seconds=15,
    )
    wrapped.fetch_company_info("DEMO_PL_TECH")
    clock.now = 10
    with pytest.raises(ProviderError) as caught:
        wrapped.fetch_company_info("DEMO_US_GROWTH")

    assert str(caught.value) == TEMPORARY_FAILURE_MESSAGE
    assert clock.slept == []
    assert inner.calls == 1
    clock.now = 60
    wrapped.fetch_company_info("DEMO_US_GROWTH")
    assert inner.calls == 2
    assert clock.slept == []


def test_backoff_stays_inside_the_exponential_cap():
    inner = Flaky(YFRateLimitError())
    wrapped, clock = _wrap(
        inner,
        max_retries=4,
        backoff_base_seconds=0.5,
        backoff_max_seconds=3,
    )
    with pytest.raises(ProviderError) as caught:
        wrapped.fetch_company_info("AAA")

    assert clock.slept == [0.5, 1.0, 2.0, 3.0]
    assert inner.calls == 5
    assert str(caught.value) == TEMPORARY_FAILURE_MESSAGE
    assert "secret-host" not in str(caught.value)
    assert caught.value.__cause__ is None


def test_backoff_clamps_a_rng_that_returns_huge_or_non_finite_values():
    for rng in (lambda low, high: 1e9, lambda low, high: float("nan")):
        inner = Flaky(TimeoutError("secret-host"))
        wrapped, clock = _wrap(
            inner,
            rng=rng,
            max_retries=2,
            backoff_base_seconds=1,
            backoff_max_seconds=3,
        )
        with pytest.raises(ProviderError) as caught:
            wrapped.fetch_company_info("AAA")
        assert clock.slept == [1.0, 2.0]
        assert "secret-host" not in str(caught.value)


def test_a_broken_rng_falls_back_to_the_ceiling():
    def broken(low, high):
        raise TypeError("rng failed secret")

    inner = Flaky(TimeoutError("secret-host"))
    wrapped, clock = _wrap(
        inner,
        rng=broken,
        max_retries=1,
        backoff_base_seconds=1,
        backoff_max_seconds=8,
    )
    with pytest.raises(ProviderError) as caught:
        wrapped.fetch_company_info("AAA")
    assert clock.slept == [1.0]
    assert "secret" not in str(caught.value)


def test_negative_jitter_does_not_stretch_the_wait():
    inner = Flaky(TimeoutError("secret-host"))
    wrapped, clock = _wrap(
        inner,
        rng=lambda low, high: -5,
        max_retries=1,
    )
    with pytest.raises(ProviderError, match=TEMPORARY_FAILURE_MESSAGE):
        wrapped.fetch_company_info("AAA")
    assert clock.slept == []
    assert inner.calls == 2


def test_zero_jitter_does_not_sleep_and_still_gives_up(caplog):
    inner = Flaky(YFRateLimitError())
    wrapped, clock = _wrap(
        inner,
        rng=lambda low, high: 0,
        max_retries=2,
    )
    with caplog.at_level("WARNING", logger="app.data_collectors.resilience"):
        with pytest.raises(ProviderError, match=TEMPORARY_FAILURE_MESSAGE):
            wrapped.fetch_company_info("AAA")

    assert clock.slept == []
    assert inner.calls == 3
    assert "secret-host" not in caplog.text
    assert "YFRateLimitError" in caplog.text


def test_success_after_a_transient_error_is_cached():
    inner = Flaky(TimeoutError("secret-host"), failures=1)
    wrapped, _clock = _wrap(inner, rng=lambda low, high: 0, max_retries=2)
    first = wrapped.fetch_company_info("AAA")
    second = wrapped.fetch_company_info("AAA")

    assert inner.calls == 2
    assert second.value["n"] == first.value["n"]
    assert second.provenance.retrieved_at == first.provenance.retrieved_at
    first.value["n"] = 99
    assert wrapped.fetch_company_info("AAA").value["n"] == 2


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("secret-host"),
        ConnectionError("secret-host"),
        requests.Timeout("secret-host"),
        requests.ConnectionError("secret-host"),
        YFRateLimitError(),
    ],
)
def test_transient_errors_are_retried(error):
    inner = Flaky(error, failures=1)
    wrapped, _clock = _wrap(inner, rng=lambda low, high: 0, max_retries=1)
    result = wrapped.fetch_company_info("AAA")

    assert inner.calls == 2
    assert result.value["ticker"] == "AAA"


def test_a_transient_context_is_retried_when_the_cause_is_not():
    """``raise ProviderError from ValueError`` can still hide a rate limit.

    ``__cause__`` is the ValueError. The rate-limit error stays on
    ``__context__``. That link is worth retrying. The exception text
    is not.
    """

    class Once:
        def __init__(self):
            self.calls = 0

        def fetch_company_info(self, ticker):
            self.calls += 1
            if self.calls == 1:
                try:
                    raise YFRateLimitError()
                except YFRateLimitError:
                    raise ProviderError("wrapped secret-host") from ValueError(
                        "parse"
                    )
            return sourced({"ticker": ticker})

    inner = Once()
    wrapped, clock = _wrap(inner, max_retries=1, rng=lambda low, high: 0)
    result = wrapped.fetch_company_info("AAA")

    assert inner.calls == 2
    assert result.value["ticker"] == "AAA"
    assert clock.slept == []


def test_rate_limit_hidden_inside_provider_error_is_retried():
    cause = YFRateLimitError()
    error = ProviderError("Yahoo Finance company info failed")
    error.__cause__ = cause
    inner = Flaky(error, failures=1)
    wrapped, _clock = _wrap(inner, rng=lambda low, high: 0, max_retries=1)

    assert wrapped.fetch_company_info("AAA").value["ticker"] == "AAA"
    assert inner.calls == 2


def test_http_429_is_retried_and_http_500_is_not():
    class StatusError(Exception):
        def __init__(self, code, via_response=False):
            super().__init__(f"status {code} secret-host")
            if via_response:
                self.response = type("Response", (), {"status_code": code})()
            else:
                self.status_code = code

    retried = Flaky(StatusError(429), failures=1)
    wrapped, _clock = _wrap(retried, rng=lambda low, high: 0, max_retries=1)
    assert wrapped.fetch_company_info("AAA") is not None
    assert retried.calls == 2

    via_response = Flaky(StatusError(429, via_response=True), failures=1)
    wrapped, _clock = _wrap(
        via_response, rng=lambda low, high: 0, max_retries=1
    )
    assert wrapped.fetch_company_info("AAA") is not None

    denied = Flaky(StatusError(500))
    wrapped, _clock = _wrap(denied, max_retries=4)
    with pytest.raises(ProviderError) as caught:
        wrapped.fetch_company_info("AAA")
    assert str(caught.value) == TEMPORARY_FAILURE_MESSAGE
    assert caught.value.__cause__ is None
    assert denied.calls == 1


def test_non_transient_errors_are_not_retried(caplog):
    parse = Flaky(ProviderError("parse failed"))
    wrapped, clock = _wrap(parse, max_retries=4)
    with pytest.raises(ProviderError, match="parse failed"):
        wrapped.fetch_company_info("AAA")
    assert parse.calls == 1
    assert clock.slept == []

    class ValueInner:
        def __init__(self):
            self.calls = 0

        def fetch_price_history(self, ticker, period="1y", interval="1d"):
            self.calls += 1
            raise ValueError("bad period secret")

    inner = ValueInner()
    wrapped, _clock = _wrap(inner, max_retries=4)
    with caplog.at_level("ERROR", logger="app.data_collectors.resilience"):
        with pytest.raises(ProviderError) as caught:
            wrapped.fetch_price_history("AAA", period="nope")
    assert str(caught.value) == TEMPORARY_FAILURE_MESSAGE
    assert caught.value.__cause__ is None
    assert "bad period" not in str(caught.value)
    assert "secret" not in caplog.text
    assert "ValueError" in caplog.text
    assert inner.calls == 1


def test_wrapper_exposes_only_the_capabilities_the_inner_collector_has():
    company, _clock = _wrap(CompanyOnly())
    assert isinstance(company, InstrumentLookup)
    assert not isinstance(company, PriceHistory)
    assert not isinstance(company, Fundamentals)
    assert not isinstance(company, FundAttributes)

    fake, _clock = _wrap(FakeCollector())
    assert isinstance(fake, InstrumentLookup)
    assert isinstance(fake, PriceHistory)
    assert isinstance(fake, Fundamentals)
    assert isinstance(fake, FundAttributes)


def test_threads_share_one_cache_without_a_second_fetch():
    inner = CountingFake()
    wrapped, _clock = _wrap(inner)
    first = wrapped.fetch_company_info("DEMO_PL_TECH")
    errors = []

    def read():
        try:
            got = wrapped.fetch_company_info("DEMO_PL_TECH")
            assert got.provenance.retrieved_at == first.provenance.retrieved_at
        except Exception as exc:  # pragma: no cover - assertion path
            errors.append(exc)

    threads = [threading.Thread(target=read) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert inner.calls == 1


def test_resilience_module_does_not_import_yfinance():
    tree = ast.parse(RESILIENCE_PATH.read_text(encoding="utf-8"))
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module.split(".")[0])
    assert "yfinance" not in modules


def test_constructor_rejects_limits_outside_the_settings_bounds():
    inner = CompanyOnly()
    with pytest.raises(ValueError):
        ResilientCollector(inner, cache_ttl_seconds=0)
    with pytest.raises(ValueError):
        ResilientCollector(inner, rate_limit_per_minute=0)
    with pytest.raises(ValueError):
        ResilientCollector(inner, rate_limit_per_minute=True)
    marker = "wait-secret-marker"
    with pytest.raises(ValueError) as caught:
        ResilientCollector(inner, rate_limit_max_wait_seconds=marker)
    assert marker not in str(caught.value)
    with pytest.raises(ValueError):
        ResilientCollector(inner, rate_limit_max_wait_seconds=-1)
    with pytest.raises(ValueError):
        ResilientCollector(inner, rate_limit_max_wait_seconds=61)
    with pytest.raises(ValueError):
        ResilientCollector(inner, rate_limit_max_wait_seconds=float("nan"))
    with pytest.raises(ValueError):
        ResilientCollector(inner, rate_limit_max_wait_seconds=True)
    with pytest.raises(ValueError):
        ResilientCollector(inner, total_deadline_seconds=0)
    with pytest.raises(ValueError):
        ResilientCollector(inner, total_deadline_seconds=121)
    with pytest.raises(ValueError) as caught:
        ResilientCollector(
            inner, total_deadline_seconds="deadline-secret-marker"
        )
    assert "deadline-secret-marker" not in str(caught.value)
    with pytest.raises(ValueError):
        ResilientCollector(inner, max_inflight=0)
    with pytest.raises(ValueError):
        ResilientCollector(inner, max_inflight=17)
    with pytest.raises(ValueError):
        ResilientCollector(inner, max_inflight=True)
    with pytest.raises(ValueError):
        ResilientCollector(inner, backoff_base_seconds=0)
    with pytest.raises(ValueError):
        ResilientCollector(inner, backoff_max_seconds=0)
    with pytest.raises(ValueError):
        ResilientCollector(inner, cache_ttl_seconds="slow")
    with pytest.raises(ValueError):
        ResilientCollector(
            inner,
            backoff_base_seconds=30,
            backoff_max_seconds=1,
        )


def test_an_unhashable_argument_is_not_cached():
    class Payload:
        def __init__(self):
            self.calls = 0

        def fetch_company_info(self, ticker, extra=None):
            self.calls += 1
            return sourced({"ticker": ticker})

    inner = Payload()
    wrapped, _clock = _wrap(inner)
    wrapped.fetch_company_info("AAA", extra={"secret": "x"})
    wrapped.fetch_company_info("AAA", extra={"secret": "x"})
    assert inner.calls == 2

    with pytest.raises(ProviderError) as caught:
        wrapped.fetch_company_info()
    assert str(caught.value) == TEMPORARY_FAILURE_MESSAGE
    assert inner.calls == 2


def test_default_cache_size_is_bounded():
    wrapped, _clock = _wrap(CompanyOnly())
    assert wrapped.max_cache_entries == 8
    plain = ResilientCollector(
        CompanyOnly(),
        clock=FakeClock(),
        sleep=FakeClock().sleep,
    )
    assert plain.max_cache_entries == DEFAULT_MAX_CACHE_ENTRIES


def test_collector_limit_defaults_and_bounds(monkeypatch):
    built = _build_settings(monkeypatch)
    assert built.COLLECTOR_CACHE_TTL_SECONDS == 300
    assert built.COLLECTOR_RATE_LIMIT_PER_MINUTE == 30
    assert built.COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS == 5
    assert built.COLLECTOR_TOTAL_DEADLINE_SECONDS == 15
    assert built.COLLECTOR_MAX_INFLIGHT == 4
    assert built.COLLECTOR_MAX_RETRIES == 2
    assert built.COLLECTOR_BACKOFF_BASE_SECONDS == 0.5
    assert built.COLLECTOR_BACKOFF_MAX_SECONDS == 8

    custom = _build_settings(
        monkeypatch,
        COLLECTOR_CACHE_TTL_SECONDS="10.5",
        COLLECTOR_RATE_LIMIT_PER_MINUTE="12",
        COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS="0",
        COLLECTOR_MAX_RETRIES="1",
        COLLECTOR_BACKOFF_BASE_SECONDS="0.25",
        COLLECTOR_BACKOFF_MAX_SECONDS="2",
    )
    assert custom.COLLECTOR_CACHE_TTL_SECONDS == 10.5
    assert custom.COLLECTOR_RATE_LIMIT_PER_MINUTE == 12
    assert custom.COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS == 0

    for name, value in (
        ("COLLECTOR_CACHE_TTL_SECONDS", "0"),
        ("COLLECTOR_CACHE_TTL_SECONDS", "86401"),
        ("COLLECTOR_CACHE_TTL_SECONDS", "nan"),
        ("COLLECTOR_RATE_LIMIT_PER_MINUTE", "0"),
        ("COLLECTOR_RATE_LIMIT_PER_MINUTE", "121"),
        ("COLLECTOR_RATE_LIMIT_PER_MINUTE", "1.5"),
        ("COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS", "-0.1"),
        ("COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS", "60.1"),
        ("COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS", "nan"),
        ("COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS", "inf"),
        ("COLLECTOR_TOTAL_DEADLINE_SECONDS", "0"),
        ("COLLECTOR_TOTAL_DEADLINE_SECONDS", "121"),
        ("COLLECTOR_TOTAL_DEADLINE_SECONDS", "nan"),
        ("COLLECTOR_MAX_INFLIGHT", "0"),
        ("COLLECTOR_MAX_INFLIGHT", "17"),
        ("COLLECTOR_MAX_RETRIES", "0"),
        ("COLLECTOR_MAX_RETRIES", "6"),
        ("COLLECTOR_BACKOFF_BASE_SECONDS", "0"),
        ("COLLECTOR_BACKOFF_BASE_SECONDS", "61"),
        ("COLLECTOR_BACKOFF_MAX_SECONDS", "0"),
        ("COLLECTOR_BACKOFF_MAX_SECONDS", "121"),
    ):
        with pytest.raises(Exception):
            _build_settings(monkeypatch, **{name: value})

    with pytest.raises(Exception):
        _build_settings(
            monkeypatch,
            COLLECTOR_BACKOFF_BASE_SECONDS="30",
            COLLECTOR_BACKOFF_MAX_SECONDS="1",
        )

    marker = "wait-secret-marker"
    with pytest.raises(Exception) as caught:
        _build_settings(
            monkeypatch,
            COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS=marker,
        )
    assert marker not in str(caught.value)
    deadline_marker = "deadline-secret-marker"
    with pytest.raises(Exception) as caught:
        _build_settings(
            monkeypatch,
            COLLECTOR_TOTAL_DEADLINE_SECONDS=deadline_marker,
        )
    assert deadline_marker not in str(caught.value)


def test_env_example_documents_the_collector_limits():
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    for name in _LIMIT_NAMES:
        assert name in text


class CountingTicker:
    calls = 0

    def __init__(self, symbol):
        type(self).calls += 1
        self.info = {
            "longName": "Count Co",
            "currency": "USD",
            "quoteType": "EQUITY",
        }


@pytest.mark.asyncio
async def test_yahoo_wrapper_reuses_the_cache_across_requests(
    client, monkeypatch
):
    monkeypatch.setattr(settings, "DATA_COLLECTOR", "yahoo")
    reset_cached_collector()
    CountingTicker.calls = 0
    monkeypatch.setattr(yahoo_finance.yf, "Ticker", CountingTicker)

    first = await client.post(FETCH_URL, json={"ticker": "AAPL"})
    second = await client.post(FETCH_URL, json={"ticker": "AAPL"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["company_id"] == first.json()["company_id"]
    assert CountingTicker.calls == 1


def test_yahoo_wrapper_reads_the_rate_limit_cap(monkeypatch):
    monkeypatch.setattr(settings, "DATA_COLLECTOR", "yahoo")
    monkeypatch.setattr(settings, "COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS", 7)
    reset_cached_collector()
    try:
        collector = get_collector()
        assert collector._rate_limit_max_wait == 7
    finally:
        reset_cached_collector()


@pytest.mark.asyncio
async def test_wrapper_give_up_is_502_and_no_data_stays_404(client):
    class Empty:
        def __init__(self):
            self.calls = 0

        def fetch_company_info(self, ticker):
            self.calls += 1
            return None

    empty = Empty()
    wrapped, _clock = _wrap(empty)
    client.app.dependency_overrides[get_collector] = lambda: wrapped
    first = await client.post(FETCH_URL, json={"ticker": "MISS"})
    second = await client.post(FETCH_URL, json={"ticker": "MISS"})
    assert first.status_code == 404
    assert second.status_code == 404
    assert empty.calls == 2

    giving_up, _clock = _wrap(
        Flaky(YFRateLimitError()),
        max_retries=1,
        rng=lambda low, high: 0,
    )
    client.app.dependency_overrides[get_collector] = lambda: giving_up
    response = await client.post(FETCH_URL, json={"ticker": "AAPL"})
    assert response.status_code == 502
    assert response.json()["detail"] == "Data provider error"
    assert "secret-host" not in response.text
    assert "Too Many Requests" not in response.text


@pytest.mark.asyncio
async def test_rate_limit_over_the_cap_is_still_502(client):
    """Failing the cap is a provider error, same status as a give-up."""
    inner = FakeCollector()
    wrapped, clock = _wrap(
        inner,
        rate_limit_per_minute=1,
        rate_limit_max_wait_seconds=5,
    )
    client.app.dependency_overrides[get_collector] = lambda: wrapped
    first = await client.post(FETCH_URL, json={"ticker": "DEMO_PL_TECH"})
    second = await client.post(FETCH_URL, json={"ticker": "DEMO_US_GROWTH"})

    assert first.status_code == 200
    assert second.status_code == 502
    assert second.json()["detail"] == "Data provider error"
    assert clock.slept == []
    assert "temporarily unavailable" not in second.text


@pytest.mark.asyncio
async def test_a_raw_value_error_from_the_collector_is_502(client):
    """A ValueError must not become HTTP 400 with the provider text."""

    class Bad:
        def fetch_company_info(self, ticker):
            raise ValueError("bad period secret-host")

    client.app.dependency_overrides[get_collector] = lambda: _wrap(Bad())[0]
    response = await client.post(FETCH_URL, json={"ticker": "AAPL"})
    assert response.status_code == 502
    assert response.json()["detail"] == "Data provider error"
    assert "secret-host" not in response.text
    assert "bad period" not in response.text


@pytest.mark.asyncio
async def test_saturated_collector_does_not_block_other_routes(client):
    """A stuck fetch must not freeze the company list or /ui.

    The thread pool is cut to three workers. One fetch holds the only
    inflight permit. Two more fetches would otherwise take the
    remaining workers and wait on the rate limit. They fail at once,
    and the list routes still answer.
    """
    entered = threading.Event()
    release = threading.Event()

    class Holding:
        def fetch_company_info(self, ticker):
            entered.set()
            assert release.wait(timeout=5)
            return sourced(
                {
                    "name": "Hold Co",
                    "ticker": ticker,
                    "currency": "USD",
                }
            )

    wrapped, _clock = _wrap(
        Holding(),
        clock=time.monotonic,
        sleep=time.sleep,
        rate_limit_per_minute=1,
        rate_limit_max_wait_seconds=60,
        total_deadline_seconds=120,
        max_inflight=1,
    )
    client.app.dependency_overrides[get_collector] = lambda: wrapped
    limiter = anyio.to_thread.current_default_thread_limiter()
    previous_tokens = limiter.total_tokens
    limiter.total_tokens = 3
    stuck = asyncio.create_task(
        client.post(FETCH_URL, json={"ticker": "HOLD"})
    )
    try:
        for _ in range(100):
            if entered.is_set():
                break
            await asyncio.sleep(0.01)
        assert entered.is_set()

        extras = [
            asyncio.create_task(
                client.post(FETCH_URL, json={"ticker": ticker})
            )
            for ticker in ("BBB", "CCC")
        ]
        done, pending = await asyncio.wait(extras, timeout=1)
        assert pending == set()
        for task in done:
            response = task.result()
            assert response.status_code == 502
            assert response.json()["detail"] == "Data provider error"

        started = time.monotonic()
        companies = await client.get("/api/v1/companies/?skip=0&limit=10")
        page = await client.get("/ui")
        assert time.monotonic() - started < 1
        assert companies.status_code == 200
        assert page.status_code == 200
    finally:
        release.set()
        limiter.total_tokens = previous_tokens
        await asyncio.wait_for(stuck, timeout=2)


def test_direct_sourced_round_trip_preserves_provenance_fields():
    """Guard the copy: a cache hit must not rebuild provenance."""
    when = datetime(2026, 4, 5, 6, 7, tzinfo=timezone.utc)
    original = Sourced(
        {"ticker": "AAA"},
        Provenance(source="stub", retrieved_at=when, synthetic=False),
    )
    inner = type("Once", (), {})()
    inner.calls = 0

    def fetch_company_info(ticker):
        inner.calls += 1
        return original

    inner.fetch_company_info = fetch_company_info
    wrapped, _clock = _wrap(inner)
    first = wrapped.fetch_company_info("AAA")
    second = wrapped.fetch_company_info("AAA")
    assert first.provenance.retrieved_at == when
    assert second.provenance.retrieved_at == when
    assert inner.calls == 1
