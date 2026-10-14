"""Shared helper for test collectors that stand in for a real provider.

A collector returns ``Sourced`` (a value plus its provenance), not a
plain dict. ``sourced`` wraps a dict so each stub stays one line.
"""

from datetime import datetime, timezone
from typing import Any, Dict

from app.data_collectors.base import Provenance, Sourced
from app.data_collectors.fake import FakeCollector

STUB_RETRIEVED_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def sourced(value: Dict[str, Any]) -> Sourced[Dict[str, Any]]:
    """Wrap ``value`` the way a real collector would."""
    return Sourced(
        value=value,
        provenance=Provenance(source="stub", retrieved_at=STUB_RETRIEVED_AT),
    )


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
