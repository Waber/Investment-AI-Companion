"""demo-v2 seeding skips rows that are already stored.

The client is in memory. It does not open a database and it does not
read the large fixture. The sqlite file and the one-command demo are
covered by the tests that load ``fixtures/demo-v2.json``.
"""

import copy

import pytest

from scripts import seed_demo as seed


def _fixture():
    company = {
        "name": "Demo One",
        "ticker": "DEMO_ONE",
        "description": "[IAC-DEMO-V2] Synthetic only",
        "website": "https://example.com/",
        "country": "Poland",
        "exchange": "GPW",
        "currency": "PLN",
        "sector": "Technology",
        "industry": "Software",
        "instrument_type": "STOCK",
    }
    return {
        "version": 2,
        "marker": "[IAC-DEMO-V2]",
        "as_of": "2026-09-30",
        "companies": [
            {
                "company": company,
                "metrics": [
                    {
                        "period_end": "2025-12-31T00:00:00Z",
                        "period_type": "annual",
                        "revenue": 10,
                    }
                ],
                "prices": [
                    {
                        "date": "2026-01-05",
                        "open": 1.0,
                        "high": 2.0,
                        "low": 0.5,
                        "close": 1.5,
                        "volume": 10,
                        "currency": "PLN",
                        "source": "[IAC-DEMO-V2]",
                        "retrieved_at": "2026-09-30T18:00:00Z",
                    }
                ],
            }
        ],
    }


class _Client:
    def __init__(self):
        self.companies = []
        self.metrics = []
        self.prices = []

    def request(self, method, path, payload=None):
        if method == "GET" and path.startswith("/api/v1/companies/"):
            return copy.deepcopy(self.companies)
        if method == "GET" and path.startswith(
            "/api/v1/financial-metrics/company/"
        ):
            owner = int(path.rsplit("/", 1)[1].split("?", 1)[0])
            return [row for row in self.metrics if row["company_id"] == owner]
        if method == "GET" and path.startswith("/api/v1/instruments/"):
            owner = int(path.split("/")[4])
            return [
                row for row in self.prices if row["instrument_id"] == owner
            ]
        if method == "POST" and path == "/api/v1/companies/":
            row = dict(payload, id=len(self.companies) + 1)
            self.companies.append(row)
            return copy.deepcopy(row)
        if method == "POST" and path == "/api/v1/financial-metrics/":
            row = dict(payload, id=len(self.metrics) + 1)
            self.metrics.append(row)
            return copy.deepcopy(row)
        if method == "POST" and path.startswith("/api/v1/instruments/"):
            owner = int(path.split("/")[4])
            row = dict(payload, id=len(self.prices) + 1, instrument_id=owner)
            self.prices.append(row)
            return copy.deepcopy(row)
        raise AssertionError(method + " " + path)


def test_second_apply_skips_prices_as_well_as_companies():
    fixture = _fixture()
    client = _Client()
    first = seed.seed_demo(fixture, client, apply=True)
    assert first["companies"]["created"] == 1
    assert first["metrics"]["created"] == 1
    assert first["prices"]["created"] == 1
    assert len(client.prices) == 1

    second = seed.seed_demo(fixture, client, apply=True)
    assert second["companies"] == {
        "created": 0,
        "skipped": 1,
        "pending": 0,
    }
    assert second["metrics"]["skipped"] == 1
    assert second["prices"] == {
        "created": 0,
        "skipped": 1,
        "pending": 0,
    }
    assert len(client.prices) == 1


def test_dry_run_leaves_prices_pending():
    fixture = _fixture()
    client = _Client()
    result = seed.seed_demo(fixture, client, apply=False)
    assert result["dry_run"] is True
    assert result["prices"] == {"created": 0, "skipped": 0, "pending": 1}
    assert client.companies == []
    assert client.prices == []


def test_resume_inserts_only_the_missing_price():
    fixture = _fixture()
    client = _Client()
    client.companies.append(
        {
            "id": 7,
            "ticker": "DEMO_ONE",
            "description": "[IAC-DEMO-V2] Synthetic only",
        }
    )
    client.metrics.append(
        {
            "id": 3,
            "company_id": 7,
            "period_type": "annual",
            "period_end": "2025-12-31T00:00:00+00:00",
        }
    )
    result = seed.seed_demo(fixture, client, apply=True)
    assert result["companies"]["skipped"] == 1
    assert result["metrics"]["skipped"] == 1
    assert result["prices"]["created"] == 1
    assert len(client.prices) == 1


def test_ambiguous_or_mismatched_prices_stop_the_seed():
    fixture = _fixture()
    stored = {
        "id": 7,
        "ticker": "DEMO_ONE",
        "description": "[IAC-DEMO-V2] Synthetic only",
    }
    duplicate = _Client()
    duplicate.companies.append(dict(stored))
    duplicate.prices.extend(
        [
            {
                "id": 1,
                "instrument_id": 7,
                "date": "2026-01-05",
                "source": "[IAC-DEMO-V2]",
            },
            {
                "id": 2,
                "instrument_id": 7,
                "date": "2026-01-05",
                "source": "[IAC-DEMO-V2]",
            },
        ]
    )
    with pytest.raises(seed.SeedError, match="ambiguous price"):
        seed.seed_demo(fixture, duplicate, apply=True)

    class ReturnEveryPrice(_Client):
        def request(self, method, path, payload=None):
            if method == "GET" and "/prices" in path:
                return copy.deepcopy(self.prices)
            return super().request(method, path, payload)

    mismatch = ReturnEveryPrice()
    mismatch.companies.append(dict(stored))
    mismatch.prices.append(
        {
            "id": 1,
            "instrument_id": 99,
            "date": "2026-01-05",
            "source": "[IAC-DEMO-V2]",
        }
    )
    with pytest.raises(seed.SeedError, match="instrument mismatch"):
        seed.seed_demo(fixture, mismatch, apply=True)

    class NotAList(_Client):
        def request(self, method, path, payload=None):
            if method == "GET" and "/prices" in path:
                return {"prices": []}
            return super().request(method, path, payload)

    wrong_shape = NotAList()
    wrong_shape.companies.append(dict(stored))
    with pytest.raises(seed.SeedError, match="expected a list"):
        seed.seed_demo(fixture, wrong_shape, apply=True)


def test_a_price_post_failure_keeps_the_summary():
    fixture = _fixture()

    class FailPrices(_Client):
        def request(self, method, path, payload=None):
            if method == "POST" and path.startswith("/api/v1/instruments/"):
                raise OSError("price post failed")
            return super().request(method, path, payload)

    client = FailPrices()
    with pytest.raises(seed.SeedError, match="price post failed") as caught:
        seed.seed_demo(fixture, client, apply=True)
    assert caught.value.summary["companies"]["created"] == 1
    assert caught.value.summary["prices"]["pending"] == 1


def test_price_path_helpers():
    assert seed._price_instrument_id("/api/v1/instruments/12/prices") == 12
    assert seed._price_instrument_id("/api/v1/instruments/nope/prices") is None
    assert seed._price_instrument_id("/api/v1/companies/") is None
    start, end = seed._price_query_range(
        {"from": ["2026-01-05"], "to": ["2026-01-06"]}
    )
    assert (start.isoformat(), end.isoformat()) == ("2026-01-05", "2026-01-06")
    assert seed._price_query_range({}) == (None, None)


def test_price_json_normalizes_a_naive_retrieval_clock():
    from datetime import date, datetime, timezone
    from types import SimpleNamespace

    from scripts.seed_demo import SqliteSeedClient

    naive = SqliteSeedClient._price_json(
        SimpleNamespace(
            id=1,
            instrument_id=2,
            bar_date=date(2026, 1, 5),
            open_price=1.0,
            high_price=2.0,
            low_price=0.5,
            close_price=1.5,
            volume=10,
            currency="PLN",
            source="[IAC-DEMO-V2]",
            retrieved_at=datetime(2026, 9, 30, 18, 0, 0),
        )
    )
    assert naive["retrieved_at"] == "2026-09-30T18:00:00Z"
    aware = SqliteSeedClient._price_json(
        SimpleNamespace(
            id=1,
            instrument_id=2,
            bar_date=date(2026, 1, 5),
            open_price=1.0,
            high_price=2.0,
            low_price=0.5,
            close_price=1.5,
            volume=10,
            currency="PLN",
            source="[IAC-DEMO-V2]",
            retrieved_at=datetime(2026, 9, 30, 20, 0, tzinfo=timezone.utc),
        )
    )
    assert aware["date"] == "2026-01-05"
    assert aware["retrieved_at"] == "2026-09-30T20:00:00Z"


def test_a_price_without_the_marker_is_rejected_before_writes():
    fixture = _fixture()
    fixture["companies"][0]["prices"][0]["source"] = "fake"
    client = _Client()
    try:
        seed.seed_demo(fixture, client, apply=True)
    except seed.SeedError as error:
        assert error.summary is None
        assert "source" in str(error)
    else:
        raise AssertionError("invalid price source was accepted")
    assert client.companies == []
