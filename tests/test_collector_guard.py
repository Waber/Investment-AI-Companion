"""The collector guard in fake time: capabilities and the cache."""

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
