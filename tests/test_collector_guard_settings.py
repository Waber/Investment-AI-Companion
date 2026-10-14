"""COLLECTOR_* settings and the GuardPolicy built from them."""

from dataclasses import fields
from pathlib import Path

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

    assert getattr(built, name) == type(DEFAULTS[name])(value)  # noqa: E721


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


ROOT = Path(__file__).resolve().parents[1]


def test_every_guard_setting_is_documented():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    example = (ROOT / ".env.example").read_text(encoding="utf-8")

    for name in DEFAULTS:
        assert name in readme, name
        assert f"{name}=" in example, name
