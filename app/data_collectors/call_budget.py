"""One deadline shared by a collector call and the HTTP requests inside it.

The guard starts the deadline when a cache miss begins. The Yahoo
collector reads how much time is left, so several HTTP requests in one
method share that budget instead of each getting a fresh timeout.

``contextvars`` is the Python tool for a value that belongs to the
current task. A thread sees the value set in that thread, and a new
thread copies the value from the thread that started it. The collector
method signatures stay the same, which is why the deadline is not an
extra argument (a Java method would take the deadline as a parameter,
or read it from a ``ThreadLocal``).
"""

from contextvars import ContextVar, Token
from typing import Callable, Optional, Tuple

Clock = Callable[[], float]

# (absolute deadline on the clock's scale, the clock). None means the
# caller did not set a budget, and each HTTP request uses its own
# timeout.
_budget: ContextVar[Optional[Tuple[float, Clock]]] = ContextVar(
    "collector_call_budget", default=None
)


def push_budget(deadline_at: float, clock: Clock) -> Token:
    """Start a budget. ``pop_budget`` must be called with the token."""
    return _budget.set((deadline_at, clock))


def pop_budget(token: Token) -> None:
    """Restore the budget that was active before ``push_budget``."""
    _budget.reset(token)


def has_budget() -> bool:
    """True when the current thread already has a collector deadline."""
    return _budget.get() is not None


def remaining(default: float) -> float:
    """Seconds left for the next request, or ``default`` when no budget.

    The result is never negative. ``0`` means the deadline has already
    passed and the caller should not start another long request.
    """
    current = _budget.get()
    if current is None:
        return default
    deadline_at, clock = current
    left = deadline_at - clock()
    if left <= 0:
        return 0.0
    if left < default:
        return left
    return default
