"""Shared helper for test collectors that stand in for a real provider.

A collector returns ``Sourced`` (a value plus its provenance), not a
plain dict. ``sourced`` wraps a dict so each stub stays one line.
"""

from datetime import datetime, timezone
from typing import Any, Dict

from app.data_collectors.base import Provenance, Sourced

STUB_RETRIEVED_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def sourced(value: Dict[str, Any]) -> Sourced[Dict[str, Any]]:
    """Wrap ``value`` the way a real collector would."""
    return Sourced(
        value=value,
        provenance=Provenance(source="stub", retrieved_at=STUB_RETRIEVED_AT),
    )
