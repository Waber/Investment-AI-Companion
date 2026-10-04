"""Seeder unit tests: only in-memory HTTP fakes, never an app or database."""

import argparse
import copy
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from scripts import seed_demo as seed


def manifest():
    def entry(ticker):
        return {
            "company": {
                "name": ticker,
                "ticker": ticker,
                "description": "[IAC-DEMO-V1] Synthetic only",
                "website": "https://example.com/",
                "country": "US",
                "exchange": "DEMO",
                "currency": "USD",
                "sector": "Technology",
                "industry": "Software",
            },
            "metrics": [],
        }

    first = entry("DEMO_ONE")
    first["metrics"] = [
        {
            "period_end": "2025-12-31T00:00:00Z",
            "period_type": "annual",
            "revenue": 100,
            "net_income": -10,
            "pe_ratio": None,
        },
        {
            "period_end": "2024-12-31T00:00:00Z",
            "period_type": "annual",
            "revenue": 80,
        },
    ]
    return {
        "version": 1,
        "marker": "[IAC-DEMO-V1]",
        "companies": [first, entry("DEMO_EMPTY")],
    }


class FakeClient:
    def __init__(self, companies=(), metrics=()):
        self.companies = copy.deepcopy(list(companies))
        self.metrics = copy.deepcopy(list(metrics))
        self.calls = []
        self.fail_post = None
        self.posts = 0

    def request(self, method, path, payload=None):
        self.calls.append((method, path, copy.deepcopy(payload)))
        parsed = urlsplit(path)
        if method == "GET":
            query = parse_qs(parsed.query)
            skip, limit = int(query["skip"][0]), int(query["limit"][0])
            assert limit == 100
            if parsed.path == "/api/v1/companies/":
                rows = self.companies
            else:
                owner = int(parsed.path.rsplit("/", 1)[1])
                rows = [r for r in self.metrics if r["company_id"] == owner]
            end = skip + limit
            return copy.deepcopy(rows[skip:end])
        assert method == "POST", "No updates or deletes allowed"
        self.posts += 1
        if self.posts == self.fail_post:
            raise OSError("simulated HTTP failure")
        if parsed.path == "/api/v1/companies/":
            rows = self.companies
        else:
            rows = self.metrics
        row = dict(payload, id=max((r["id"] for r in rows), default=0) + 1)
        rows.append(row)
        return copy.deepcopy(row)


def test_create_then_repeat_with_no_writes():
    fixture, client = manifest(), FakeClient()
    original = copy.deepcopy(fixture)
    result = seed.seed_demo(fixture, client, apply=True)
    assert result["companies"] == {"created": 2, "skipped": 0, "pending": 0}
    assert result["metrics"] == {"created": 2, "skipped": 0, "pending": 0}
    assert [item["id"] for item in result["items"]] == [1, 1, 2, 2]
    assert all(item["status"] == "created" for item in result["items"])
    assert fixture == original
    client.calls.clear()
    result = seed.seed_demo(fixture, client, apply=True)
    assert result["companies"] == {"created": 0, "skipped": 2, "pending": 0}
    assert result["metrics"] == {"created": 0, "skipped": 2, "pending": 0}
    assert all(call[0] == "GET" for call in client.calls)


def test_preserves_edits_and_unrelated_rows():
    fixture, client = manifest(), FakeClient()
    seed.seed_demo(fixture, client, apply=True)
    client.companies[0].update(
        name="Edited",
        website=None,
        description=fixture["marker"] + " User notes",
        is_active=False,
    )
    client.metrics[0].update(revenue=12345, net_income=None)
    client.companies.append({"id": 90, "ticker": "OTHER"})
    client.metrics.append(dict(client.metrics[0], id=90, company_id=90))
    before = copy.deepcopy((client.companies, client.metrics))
    seed.seed_demo(fixture, client, apply=True)
    assert (client.companies, client.metrics) == before
    assert client.posts == 4


def test_offsets_match_same_instant_but_period_type_stays_distinct():
    fixture, client = manifest(), FakeClient()
    seed.seed_demo(fixture, client, apply=True)
    client.metrics[0]["period_end"] = "2025-12-31T02:00:00+02:00"
    result = seed.seed_demo(fixture, client, apply=True)
    assert result["metrics"]["skipped"] == 2
    fixture["companies"][0]["metrics"][0]["period_type"] = "quarterly"
    result = seed.seed_demo(fixture, client, apply=True)
    assert result["metrics"]["created"] == 1


def test_paginates_companies_and_metrics_before_writes():
    fixture = manifest()
    company = dict(fixture["companies"][0]["company"], id=101)
    companies = [{"id": n, "ticker": f"OTHER{n}"} for n in range(1, 101)]
    metrics = [
        {
            "id": n,
            "company_id": 101,
            "period_type": "annual",
            "period_end": f"{1800 + n}-12-31T00:00:00Z",
        }
        for n in range(1, 101)
    ]
    metrics += [
        dict(row, id=101 + n, company_id=101)
        for n, row in enumerate(fixture["companies"][0]["metrics"])
    ]
    client = FakeClient(companies + [company], metrics)
    result = seed.seed_demo(fixture, client, apply=True)
    assert result["companies"]["skipped"] == 1
    assert result["metrics"]["skipped"] == 2
    page = "/api/v1/companies/?skip=100&limit=100"
    assert ("GET", page, None) in client.calls
    assert (
        "GET",
        "/api/v1/financial-metrics/company/101?skip=100&limit=100",
        None,
    ) in client.calls
    assert client.calls[-1][0] == "POST"
    assert all(call[0] == "GET" for call in client.calls[:-1])


@pytest.mark.parametrize("apply", [False, True])
@pytest.mark.parametrize("description", [None, "User-owned", " [IAC-DEMO-V1]"])
def test_later_collision_prevents_every_write(apply, description):
    fixture = manifest()
    collision = dict(fixture["companies"][1]["company"], id=101)
    collision["description"] = description
    earlier = [{"id": n, "ticker": f"OTHER{n}"} for n in range(100)]
    client = FakeClient(earlier + [collision])
    with pytest.raises(seed.SeedError, match="DEMO_EMPTY") as error:
        seed.seed_demo(fixture, client, apply=apply)
    assert client.posts == 0
    assert error.value.summary["companies"]["created"] == 0


def test_dry_run_plans_metrics_without_company_ids_or_writes():
    client = FakeClient()
    result = seed.seed_demo(manifest(), client)
    assert result["dry_run"] is True
    assert result["companies"]["pending"] == 2
    assert result["metrics"]["pending"] == 2
    assert all(item["id"] is None for item in result["items"])
    assert all(call[0] == "GET" for call in client.calls)


def test_partial_failure_reports_progress_and_rerun_resumes():
    client = FakeClient()
    client.fail_post = 3
    with pytest.raises(seed.SeedError, match="simulated") as error:
        seed.seed_demo(manifest(), client, apply=True)
    result = error.value.summary
    assert result["companies"] == {"created": 1, "skipped": 0, "pending": 1}
    assert result["metrics"] == {"created": 1, "skipped": 0, "pending": 1}
    result = seed.seed_demo(manifest(), client, apply=True)
    assert result["companies"] == {"created": 1, "skipped": 1, "pending": 0}
    assert result["metrics"] == {"created": 1, "skipped": 1, "pending": 0}
    assert len(client.companies) == len(client.metrics) == 2


@pytest.mark.parametrize(
    "bad",
    [
        None,
        {},
        {"version": True},
        {"version": 2},
        {"marker": ""},
        {"marker": "USER"},
        {"companies": {}},
    ],
)
def test_invalid_manifest_rejected_before_requests(bad):
    fixture = manifest()
    fixture = bad if bad is None or bad == {} else dict(fixture, **bad)
    client = FakeClient()
    with pytest.raises(seed.SeedError):
        seed.seed_demo(fixture, client, apply=True)
    assert client.calls == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("ticker", "AAPL"),
        ("ticker", None),
        ("name", 42),
        ("description", "not marked"),
        ("website", "not a URL"),
        ("country", []),
        ("unexpected", "field"),
    ],
)
def test_invalid_company_rejected_before_requests(field, value):
    fixture = manifest()
    fixture["companies"][1]["company"][field] = value
    client = FakeClient()
    with pytest.raises(seed.SeedError):
        seed.seed_demo(fixture, client, apply=True)
    assert not client.calls


@pytest.mark.parametrize(
    "field,value",
    [
        ("period_end", "2025-12-31"),
        ("period_end", "not a date"),
        ("period_end", None),
        ("period_type", 42),
        ("period_type", ""),
        ("revenue", float("nan")),
        ("revenue", float("inf")),
        ("revenue", "100"),
        ("revenue", True),
        ("company_id", 42),
        ("bogus_metric", 12),
    ],
)
def test_invalid_metric_rejected_before_requests(field, value):
    fixture = manifest()
    fixture["companies"][0]["metrics"][1][field] = value
    client = FakeClient()
    with pytest.raises(seed.SeedError):
        seed.seed_demo(fixture, client, apply=True)
    assert not client.calls


@pytest.mark.parametrize("duplicate", ["ticker", "period"])
def test_duplicate_fixture_keys_rejected(duplicate):
    fixture = manifest()
    first, second = fixture["companies"]
    if duplicate == "ticker":
        second["company"]["ticker"] = first["company"]["ticker"]
    else:
        row = dict(first["metrics"][0])
        row["period_end"] = "2025-12-30T19:00:00-05:00"
        first["metrics"].append(row)
    client = FakeClient()
    with pytest.raises(seed.SeedError):
        seed.seed_demo(fixture, client, apply=True)
    assert not client.calls


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com:8081",
        "http://localhost:8081",
        "https://127.0.0.1:8081",
        "http://127.0.0.1",
        "http://user:pass@127.0.0.1:8081",
        "http://127.0.0.1:8081/path",
        "http://127.0.0.1:8081?x=1",
        "http://127.0.0.1:8081#fragment",
        "http://127.0.0.1:99999",
        "http://[broken",
    ],
)
def test_http_client_rejects_unsafe_base_urls(url):
    with pytest.raises((argparse.ArgumentTypeError, ValueError)):
        seed.HttpClient(url)


def test_http_transport_safety(monkeypatch):
    seen = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return b"[]"

    class Opener:
        def open(self, request, timeout):
            seen.update(request=request, timeout=timeout)
            return Response()

    def build_opener(*handlers):
        seen["handlers"] = handlers
        return Opener()

    monkeypatch.setattr(seed.http, "build_opener", build_opener)
    client = seed.HttpClient("http://127.0.0.1:8081/")
    assert client.request("GET", "/api/v1/companies/") == []
    assert seen["timeout"] == 10
    proxy, redirect = seen["handlers"]
    assert proxy.proxies == {}
    assert redirect.redirect_request(None, None, 302, "", {}, "") is None
    Response.status = 201
    payload = {"name": "Synthetic"}
    assert client.request("POST", "/api/v1/companies/", payload) == []
    assert json.loads(seen["request"].data) == payload
    assert seen["request"].get_method() == "POST"
    with pytest.raises(ValueError, match="GET and POST"):
        client.request("DELETE", "/api/v1/companies/1")
    Response.status = 302
    with pytest.raises(RuntimeError, match="302"):
        client.request("GET", "/api/v1/companies/")


def test_cli_defaults_to_dry_run_and_emits_json(monkeypatch, capsys):
    client = FakeClient()
    monkeypatch.setattr(seed, "load_fixture", manifest)
    monkeypatch.setattr(seed, "HttpClient", lambda base: client)
    assert seed.main(["--base-url", "http://127.0.0.1:8081"]) == 0
    assert json.loads(capsys.readouterr().out)["dry_run"] is True
    assert client.posts == 0
    client.fail_post = 2
    assert seed.main(["--base-url", "http://127.0.0.1:8081", "--apply"]) == 1
    output = capsys.readouterr()
    assert json.loads(output.out)["companies"]["created"] == 1
    assert "simulated" in output.err


def test_fixture_path_is_fixed_relative_to_module(monkeypatch, tmp_path):
    root = seed.Path(__file__).resolve().parents[1]
    assert seed.FIXTURE_PATH == root / "fixtures" / "demo-v1.json"
    monkeypatch.chdir(tmp_path)
    fixture = seed.load_fixture()
    client = FakeClient()
    result = seed.seed_demo(fixture, client)
    assert result["companies"]["pending"] == len(fixture["companies"])
    assert result["metrics"]["pending"] == sum(
        len(entry["metrics"]) for entry in fixture["companies"]
    )
    assert client.posts == 0


def test_failed_later_metrics_preflight_does_not_create_earlier_company():
    fixture = manifest()
    company = dict(fixture["companies"][1]["company"], id=1)

    class FailingReadClient(FakeClient):
        def request(self, method, path, payload=None):
            if "financial-metrics" in path:
                raise OSError("preflight failed")
            return super().request(method, path, payload)

    client = FailingReadClient([company])
    with pytest.raises(seed.SeedError, match="preflight failed"):
        seed.seed_demo(fixture, client, apply=True)
    assert client.posts == 0


def test_lost_post_reply_resumes_from_persisted_rows():
    class LostReplyClient(FakeClient):
        def request(self, method, path, payload=None):
            result = super().request(method, path, payload)
            if method == "POST" and self.posts == 2:
                raise TimeoutError("reply lost after server commit")
            return result

    client = LostReplyClient()
    with pytest.raises(seed.SeedError, match="reply lost") as error:
        seed.seed_demo(manifest(), client, apply=True)
    assert error.value.summary["metrics"]["created"] == 0
    result = seed.seed_demo(manifest(), client, apply=True)
    assert result["metrics"] == {"created": 1, "skipped": 1, "pending": 0}
    assert len(client.metrics) == 2


@pytest.mark.parametrize(
    "target,key",
    [
        ("entry", "company"),
        ("entry", "metrics"),
        ("company", "ticker"),
        ("company", "website"),
        ("metric", "period_type"),
        ("metric", "period_end"),
    ],
)
def test_missing_required_fields_rejected_before_requests(target, key):
    fixture = manifest()
    entry = fixture["companies"][0]
    objects = {
        "entry": entry,
        "company": entry["company"],
        "metric": entry["metrics"][0],
    }
    del objects[target][key]
    client = FakeClient()
    with pytest.raises(seed.SeedError):
        seed.seed_demo(fixture, client, apply=True)
    assert not client.calls
