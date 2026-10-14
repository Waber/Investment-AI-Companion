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
