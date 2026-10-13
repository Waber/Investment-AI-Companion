"""Tests for the provider-neutral data-collector contracts."""

import dataclasses
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional

import pytest

from app.data_collectors.base import (
    COMPANY_INFO_FIELDS,
    FUND_ATTRIBUTE_FIELDS,
    KEY_METRIC_FIELDS,
    InstrumentLookup,
    PriceBar,
    PriceHistory,
    Provenance,
    ProviderError,
    Sourced,
)


def _provenance() -> Provenance:
    return Provenance(
        source="stub",
        retrieved_at=datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc),
    )


def test_provenance_rejects_naive_retrieved_at():
    with pytest.raises(ValueError):
        Provenance(source="stub", retrieved_at=datetime(2026, 1, 2, 3, 4))


def test_provenance_stores_aware_value_as_the_same_instant_in_utc():
    plus_two = timezone(timedelta(hours=2))
    local = datetime(2026, 1, 2, 5, 4, tzinfo=plus_two)

    provenance = Provenance(source="stub", retrieved_at=local)

    assert provenance.retrieved_at == local
    assert provenance.retrieved_at.utcoffset() == timedelta(0)
    assert provenance.retrieved_at.hour == 3


@pytest.mark.parametrize("source", ["", "   "])
def test_provenance_rejects_blank_source(source):
    with pytest.raises(ValueError):
        Provenance(
            source=source,
            retrieved_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )


def test_provenance_defaults_are_unknown_as_of_and_not_synthetic():
    provenance = _provenance()

    assert provenance.as_of is None
    assert provenance.synthetic is False


def test_value_objects_are_immutable():
    provenance = _provenance()
    sourced = Sourced(value={"name": "x"}, provenance=provenance)
    bar = PriceBar(
        day=date(2026, 1, 2), open=1.0, high=2.0, low=0.5, close=1.5, volume=10
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        provenance.source = "other"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        sourced.value = {}  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        bar.close = 9.0  # type: ignore[misc]


class _LookupOnly:
    """Implements one capability and never names the protocol."""

    def fetch_company_info(
        self, ticker: str
    ) -> Optional[Sourced[Dict[str, Any]]]:
        return None


def test_stub_with_one_method_matches_only_that_capability():
    stub = _LookupOnly()

    assert isinstance(stub, InstrumentLookup)
    assert not isinstance(stub, PriceHistory)


def test_provider_error_is_not_a_value_error():
    assert issubclass(ProviderError, Exception)
    assert not issubclass(ProviderError, ValueError)


@pytest.mark.parametrize(
    "fields", [COMPANY_INFO_FIELDS, KEY_METRIC_FIELDS, FUND_ATTRIBUTE_FIELDS]
)
def test_field_constants_have_no_duplicates(fields):
    assert len(fields) == len(set(fields))
