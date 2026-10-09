"""Create synthetic fixtures through an isolated loopback HTTP API,
or into a sqlite file for the local /ui demo.

Dry run is the default. Loopback alone does not prove database isolation.
Existing rows are never updated or deleted. Runs are not atomic: concurrent
runs can conflict, and HTTP failures can leave successful writes behind.
Review the error, then rerun to discover persisted rows and resume; there is
no rollback or cleanup. A timed-out POST may have persisted without a reply.

``--database-url`` writes a sqlite file and does not read or change the
personal ``DATABASE_URL`` default. Any non-sqlite URL is refused, so this
command cannot be pointed at the personal PostgreSQL database.
"""

import argparse
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib import request as http
from urllib.parse import parse_qs, urlsplit

from scripts.smoke_demo import NoRedirect, loopback_base

FIXTURE_PATH = (
    Path(__file__)
    .resolve()
    .parents[1]
    .joinpath(
        "fixtures",
        "demo-v1.json",
    )
)
MARKER = "[IAC-DEMO-V1]"
COMPANIES = "/api/v1/companies/"
METRICS = "/api/v1/financial-metrics/"
COMPANY_FIELDS = {
    "name",
    "ticker",
    "description",
    "website",
    "country",
    "exchange",
    "currency",
    "sector",
    "industry",
}
METRIC_FIELDS = {
    "revenue",
    "net_income",
    "total_assets",
    "total_liabilities",
    "total_equity",
    "roe",
    "roa",
    "gross_margin",
    "net_margin",
    "current_ratio",
    "quick_ratio",
    "debt_to_equity",
    "debt_to_assets",
    "asset_turnover",
    "inventory_turnover",
    "revenue_growth",
    "net_income_growth",
    "pe_ratio",
    "pb_ratio",
    "ev_ebitda",
}


class SeedError(RuntimeError):
    """Validation, collision or HTTP failure, with any confirmed progress."""

    def __init__(self, message, summary=None):
        super().__init__(message)
        self.summary = summary


class HttpClient:
    """Standard-library JSON client with no proxies or redirect following."""

    def __init__(self, base_url):
        self.base_url = loopback_base(base_url)
        self.opener = http.build_opener(http.ProxyHandler({}), NoRedirect())

    def request(self, method, path, payload=None):
        if method not in {"GET", "POST"}:
            raise ValueError("Seeder only supports GET and POST")
        data = (
            None
            if payload is None
            else json.dumps(payload, allow_nan=False).encode("utf-8")
        )
        request = http.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with self.opener.open(request, timeout=10) as response:
            expected = 200 if method == "GET" else 201
            if response.status != expected:
                raise RuntimeError(f"{method} {path}: HTTP {response.status}")
            return json.loads(response.read())


def load_fixture():
    """Read only the versioned fixture beside the repository's scripts."""
    with FIXTURE_PATH.open(encoding="utf-8") as source:
        return json.load(source)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _period_key(row, *, naive_is_utc=False):
    """Return ``(period_type, utc_isoformat)`` for one metrics row.

    Fixture rows must include an offset. Rows read from the API may be
    naive when SQLite dropped the offset; those callers pass
    ``naive_is_utc=True`` so the naive clock is treated as UTC and a
    second ``--apply`` skips the row instead of inserting a duplicate.
    """
    period_type, period_end = row["period_type"], row["period_end"]
    _require(
        isinstance(period_type, str) and bool(period_type.strip()),
        "period_type must be a nonempty string",
    )
    _require(isinstance(period_end, str), "period_end must be an ISO string")
    instant = datetime.fromisoformat(period_end.replace("Z", "+00:00"))
    if instant.utcoffset() is None:
        _require(naive_is_utc, "period_end must be timezone aware")
        instant = instant.replace(tzinfo=timezone.utc)
    return period_type, instant.astimezone(timezone.utc).isoformat()


def validate_fixture(fixture):
    """Reject invalid manifests before HTTP requests, without model imports."""
    try:
        _require(isinstance(fixture, dict), "fixture must be an object")
        _require(
            set(fixture) == {"version", "marker", "companies"},
            "fixture requires version, marker and companies",
        )
        _require(
            type(fixture["version"]) is int and fixture["version"] == 1,
            "fixture version must be 1",
        )
        _require(fixture["marker"] == MARKER, f"marker must be {MARKER}")
        _require(
            isinstance(fixture["companies"], list),
            "companies must be a list",
        )
        tickers = set()
        for entry in fixture["companies"]:
            entry_fields = {"company", "metrics"}
            _require(
                isinstance(entry, dict) and set(entry) == entry_fields,
                "each entry requires company and metrics",
            )
            company = entry["company"]
            _require(
                isinstance(company, dict) and set(company) == COMPANY_FIELDS,
                "company has missing or unknown fields",
            )
            for field, value in company.items():
                nullable = field not in {"name", "ticker", "description"}
                _require(
                    (nullable and value is None)
                    or (isinstance(value, str) and bool(value.strip())),
                    f"company {field} must be a nonempty string"
                    + (" or null" if nullable else ""),
                )
            ticker = company["ticker"]
            _require(
                re.fullmatch(r"DEMO_[A-Z0-9_]+", ticker) is not None
                and len(ticker) <= 20,
                "ticker must use reserved DEMO_* namespace (max 20 chars)",
            )
            _require(ticker not in tickers, f"duplicate ticker: {ticker}")
            tickers.add(ticker)
            _require(
                company["description"].startswith(MARKER),
                f"{ticker}: description must start with {MARKER}",
            )
            if company["website"] is not None:
                url = urlsplit(company["website"])
                _require(
                    url.scheme in {"http", "https"} and bool(url.hostname),
                    f"{ticker}: website must be an HTTP(S) URL",
                )
                _require(
                    url.port is None or url.port > 0,
                    "invalid website port",
                )
            _require(
                isinstance(entry["metrics"], list),
                "metrics must be a list",
            )
            keys = set()
            for row in entry["metrics"]:
                _require(isinstance(row, dict), "metric must be an object")
                required = {"period_end", "period_type"}
                fields = set(row)
                _require(
                    required <= fields <= METRIC_FIELDS | required,
                    "metric has missing or unknown fields",
                )
                key = _period_key(row)
                _require(key not in keys, f"{ticker}: duplicate period: {key}")
                keys.add(key)
                for field in METRIC_FIELDS & row.keys():
                    value = row[field]
                    if value is None:
                        continue
                    _require(
                        type(value) in {int, float} and math.isfinite(value),
                        f"{ticker}: {field} must be finite numeric or null",
                    )
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise SeedError(f"Invalid fixture: {error}") from error


def _pages(client, path):
    skip = 0
    while True:
        rows = client.request("GET", f"{path}?skip={skip}&limit=100")
        _require(isinstance(rows, list), f"{path}: expected a list")
        yield from rows
        if len(rows) < 100:
            return
        skip += 100


def _row_id(row):
    value = row["id"]
    _require(type(value) is int and value > 0, "API returned invalid row ID")
    return value


def _summary(items, apply):
    result = {"dry_run": not apply, "items": items}
    for kind in ("companies", "metrics"):
        statuses = [item["status"] for item in items if item["kind"] == kind]
        result[kind] = {
            status: statuses.count(status)
            for status in ("created", "skipped", "pending")
        }
    return result


def seed_demo(fixture, client, *, apply=False):
    """Preflight, then optionally create missing rows in fixture order.

    ``client.request(method, path, payload=None)`` returns JSON or raises.
    The returned JSON-ready summary contains companies/metrics counts and items
    with kind, ticker, status and id; metrics also contain company_id and their
    normalized period key. Pending new rows have no ID. ``SeedError.summary``
    holds this structure on preflight/write failure (None for bad fixtures).
    Counts describe confirmed responses, not unacknowledged server commits.
    """
    validate_fixture(fixture)
    items, plans = [], []
    for entry in fixture["companies"]:
        ticker = entry["company"]["ticker"]
        company_item = {
            "kind": "companies",
            "ticker": ticker,
            "status": "pending",
            "id": None,
        }
        items.append(company_item)
        metric_items = []
        for row in entry["metrics"]:
            period_type, period_end = _period_key(row)
            item = {
                "kind": "metrics",
                "ticker": ticker,
                "status": "pending",
                "id": None,
                "company_id": None,
                "period_type": period_type,
                "period_end": period_end,
            }
            items.append(item)
            metric_items.append(item)
        plans.append((entry, company_item, metric_items))

    try:
        wanted = {entry["company"]["ticker"] for entry in fixture["companies"]}
        existing = {}
        for row in _pages(client, COMPANIES):
            ticker = row["ticker"]
            if ticker not in wanted:
                continue
            _require(
                ticker not in existing,
                f"Conflict: ambiguous ticker {ticker}",
            )
            _require(
                isinstance(row.get("description"), str)
                and row["description"].startswith(fixture["marker"]),
                f"Conflict: {ticker} lacks demo marker; no overwrite allowed",
            )
            existing[ticker] = row

        # Finish every read before the first POST, including later companies.
        for entry, company_item, metric_items in plans:
            company = existing.get(company_item["ticker"])
            if company is None:
                continue
            company_id = _row_id(company)
            company_item.update(status="skipped", id=company_id)
            existing_metrics = {}
            path = f"{METRICS}company/{company_id}"
            for row in _pages(client, path):
                _require(
                    row["company_id"] == company_id,
                    "Metrics company mismatch",
                )
                key = _period_key(row, naive_is_utc=True)
                _require(
                    key not in existing_metrics,
                    f"Conflict: ambiguous metric for "
                    f"{company_item['ticker']}: {key}",
                )
                existing_metrics[key] = _row_id(row)
            for item in metric_items:
                item["company_id"] = company_id
                key = item["period_type"], item["period_end"]
                if key in existing_metrics:
                    item.update(status="skipped", id=existing_metrics[key])

        if apply:
            for entry, company_item, metric_items in plans:
                if company_item["status"] == "pending":
                    row = client.request("POST", COMPANIES, entry["company"])
                    company_item.update(status="created", id=_row_id(row))
                company_id = company_item["id"]
                for item in metric_items:
                    item["company_id"] = company_id
                for payload, item in zip(entry["metrics"], metric_items):
                    if item["status"] != "pending":
                        continue
                    row = client.request(
                        "POST", METRICS, dict(payload, company_id=company_id)
                    )
                    item.update(status="created", id=_row_id(row))
    except Exception as error:
        raise SeedError(
            f"Seeding stopped: {error}. No rollback or overwrite; "
            "review and rerun to resume. Concurrent runs are not atomic.",
            _summary(items, apply),
        ) from error
    return _summary(items, apply)


class SqliteSeedClient:
    """Answer ``seed_demo`` HTTP paths with the company repositories.

    The seeder was written for an HTTP API. The /ui demo needs those
    same rows in a sqlite file before uvicorn starts. This client keeps
    the create/skip rules in ``seed_demo`` and only changes the transport.
    The session is one the caller opened on the sqlite URL. This class
    does not read ``settings.DATABASE_URL``.
    """

    def __init__(self, session):
        from app.repositories.company_repository import CompanyRepository
        from app.repositories.financial_metrics_repository import (
            FinancialMetricsRepository,
        )

        self.companies = CompanyRepository(session)
        self.metrics = FinancialMetricsRepository(session)

    def request(self, method, path, payload=None):
        from app.core.utc_datetime import as_utc
        from app.models.company import CompanyCreate
        from app.models.financial_metrics import FinancialMetricsCreate

        parsed = urlsplit(path)
        query = parse_qs(parsed.query)
        skip = int(query.get("skip", ["0"])[0])
        limit = int(query.get("limit", ["100"])[0])
        if method == "GET" and parsed.path == COMPANIES:
            rows = self.companies.get_all(skip=skip, limit=limit)
            return [self._company_json(row) for row in rows]
        company_prefix = f"{METRICS}company/"
        if method == "GET" and parsed.path.startswith(company_prefix):
            company_id = int(parsed.path.removeprefix(company_prefix))
            rows = self.metrics.get_by_company(
                company_id, skip=skip, limit=limit
            )
            return [self._metric_json(row, as_utc) for row in rows]
        if method == "POST" and parsed.path == COMPANIES:
            created = self.companies.create(CompanyCreate(**payload))
            return self._company_json(created)
        if method == "POST" and parsed.path == METRICS:
            created = self.metrics.create(FinancialMetricsCreate(**payload))
            return self._metric_json(created, as_utc)
        raise ValueError(f"Unsupported seed request: {method} {path}")

    @staticmethod
    def _company_json(row):
        return {
            "id": row.id,
            "ticker": row.ticker,
            "description": row.description,
        }

    @staticmethod
    def _metric_json(row, as_utc):
        return {
            "id": row.id,
            "company_id": row.company_id,
            "period_type": row.period_type,
            "period_end": as_utc(row.period_end).isoformat(),
        }


def _sqlite_file_url(database_url):
    """Return a sqlite URL, or raise without echoing the URL.

    A mistake here must not open the personal PostgreSQL database, and
    the error text must not repeat a password that was pasted into the
    command.
    """
    from sqlalchemy.engine.url import make_url
    from sqlalchemy.exc import ArgumentError

    try:
        parsed = make_url(database_url)
    except ArgumentError as error:
        raise ValueError("Invalid database URL.") from error
    if parsed.get_backend_name() != "sqlite":
        raise ValueError(
            "The demo seed only accepts a sqlite URL. "
            "It does not use or change the personal DATABASE_URL."
        )
    if not parsed.database:
        raise ValueError("The sqlite URL is missing a file path.")
    if parsed.database != ":memory:":
        parent = Path(parsed.database).parent
        if str(parent) not in {"", "."}:
            parent.mkdir(parents=True, exist_ok=True)
    return database_url


def seed_sqlite_database(database_url, *, apply, fixture=None):
    """Create tables on a sqlite URL and run the demo-v1 seeder.

    The engine is built from ``database_url`` alone. Importing the
    application also builds the process-wide engine from settings, but
    this function never connects with that engine and never assigns
    ``settings.DATABASE_URL``.
    """
    from sqlalchemy.orm import sessionmaker

    from app.core.database import Base, create_db_engine
    from app.models.database_models import CompanyDB, FinancialMetricsDB

    database_url = _sqlite_file_url(database_url)
    mapped = {CompanyDB.__tablename__, FinancialMetricsDB.__tablename__}
    engine = create_db_engine(database_url)
    try:
        missing = mapped - set(Base.metadata.tables)
        if missing:
            raise RuntimeError(f"Demo seed is missing tables: {missing}")
        Base.metadata.create_all(bind=engine)
        session = sessionmaker(
            autocommit=False, autoflush=False, bind=engine
        )()
        try:
            return seed_demo(
                load_fixture() if fixture is None else fixture,
                SqliteSeedClient(session),
                apply=apply,
            )
        finally:
            session.close()
    finally:
        engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--base-url", type=loopback_base)
    target.add_argument(
        "--database-url",
        help=(
            "Seed this sqlite file directly. "
            "Does not read or change the personal DATABASE_URL."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Explicitly enable writes; default is a dry run",
    )
    args = parser.parse_args(argv)
    try:
        if args.database_url is not None:
            result = seed_sqlite_database(args.database_url, apply=args.apply)
        else:
            result = seed_demo(
                load_fixture(),
                HttpClient(args.base_url),
                apply=args.apply,
            )
    except (SeedError, OSError, ValueError) as error:
        if isinstance(error, SeedError) and error.summary is not None:
            print(json.dumps(error.summary, indent=2))
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
