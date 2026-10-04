"""Exercise an isolated loopback demo using only the standard library."""

import argparse
import ipaddress
import json
import sys
import uuid
from urllib import request as http
from urllib.error import HTTPError
from urllib.parse import urlsplit


class NoRedirect(http.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def loopback_base(value):
    parts = urlsplit(value)
    try:
        local = ipaddress.ip_address(parts.hostname or "").is_loopback
        port = parts.port
    except ValueError:
        local, port = False, None
    if (
        not local
        or parts.scheme != "http"
        or not port
        or parts.username is not None
        or parts.password is not None
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
    ):
        raise argparse.ArgumentTypeError(
            "Use HTTP with a loopback IP and port, e.g. http://127.0.0.1:8081"
        )
    return value.rstrip("/")


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def smoke(base):
    opener = http.build_opener(http.ProxyHandler({}), NoRedirect())

    def request(method, path, payload=None, expected=(200,)):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = http.Request(
            base + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            response = opener.open(req, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            status, body = response.status, response.read()
        check(
            status in expected,
            f"{method} {path}: HTTP {status}: {body[:300]!r}",
        )
        print(f"{method} {path}: {status}")
        return json.loads(body) if body else None

    company_path = metrics_path = None
    failures = []
    try:
        request("GET", "/")
        ticker = "DEMO" + uuid.uuid4().hex[:16].upper()
        company = request(
            "POST",
            "/api/v1/companies/",
            {
                "name": "Synthetic " + ticker,
                "ticker": ticker,
                "website": "https://example.com/",
                "currency": "USD",
            },
            (201,),
        )
        company_path = f"/api/v1/companies/{company['id']}"
        check(
            request("GET", company_path)["ticker"] == ticker, "Ticker mismatch"
        )
        check(
            isinstance(request("GET", "/api/v1/companies/"), list),
            "Not a list",
        )
        request("PUT", company_path, {"website": "https://example.org/"})
        check(
            request("GET", company_path)["website"] == "https://example.org/",
            "Website replacement did not persist",
        )
        request("PUT", company_path, {"website": "not-a-url"}, (422,))
        check(
            request("GET", company_path)["website"] == "https://example.org/",
            "Invalid URL changed stored website",
        )
        request("PUT", company_path, {"website": None})
        check(
            request("GET", company_path)["website"] is None,
            "Website not cleared",
        )
        metrics = request(
            "POST",
            "/api/v1/financial-metrics/",
            {
                "company_id": company["id"],
                "period_end": "2025-12-31T00:00:00Z",
                "period_type": "annual",
                "revenue": 1000000,
                "net_income": 100000,
            },
            (201,),
        )
        metrics_path = f"/api/v1/financial-metrics/{metrics['id']}"
        check(
            request("GET", metrics_path)["company_id"] == company["id"],
            "Metrics belong to wrong company",
        )
        request("PUT", metrics_path, {"revenue": 1100000})
        check(
            request("GET", metrics_path)["revenue"] == 1100000,
            "Revenue update did not persist",
        )
        rows = request(
            "GET", f"/api/v1/financial-metrics/company/{company['id']}"
        )
        check(
            any(row["id"] == metrics["id"] for row in rows),
            "Metrics not listed",
        )
        request("DELETE", metrics_path, expected=(204,))
        request("GET", metrics_path, expected=(404,))
        request("PUT", metrics_path, {"revenue": 1}, (404,))
        request("DELETE", company_path, expected=(204,))
        request("GET", company_path, expected=(404,))
        request("PUT", company_path, {"name": "Still synthetic"}, (404,))
    except Exception as error:
        failures.append(str(error))
    finally:
        # Keep the IDs until exit: retry cleanup even after a failed assertion.
        for path in (metrics_path, company_path):
            if path:
                try:
                    request("DELETE", path, expected=(204, 404))
                except Exception as error:
                    failures.append(f"Cleanup failed for {path}: {error}")
    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    if not failures:
        print("PASS: synthetic CRUD smoke and cleanup")
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        required=True,
        type=loopback_base,
        help="Isolated demo only; loopback does not prove DB isolation",
    )
    args = parser.parse_args()
    return smoke(args.base_url)


if __name__ == "__main__":
    sys.exit(main())
