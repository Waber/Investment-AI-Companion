"""Same-origin check used by state-changing /ui forms."""

from starlette.requests import Request

from app.ui.origin import _endpoint, origin_allowed, require_same_origin


def _request(method="POST", headers=None, scheme="http", host="127.0.0.1"):
    raw_headers = [(b"host", host.encode("ascii"))]
    for name, value in (headers or {}).items():
        raw_headers.append(
            (name.lower().encode("ascii"), value.encode("latin-1"))
        )
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": scheme,
        "path": "/ui/companies",
        "raw_path": b"/ui/companies",
        "query_string": b"",
        "headers": raw_headers,
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 80),
    }
    return Request(scope)


def test_endpoint_rejects_junk_and_normalizes_the_default_port():
    assert _endpoint(None) is None
    assert _endpoint("") is None
    assert _endpoint("   ") is None
    assert _endpoint("null") is None
    assert _endpoint("NULL") is None
    assert _endpoint("javascript:alert(1)") is None
    assert _endpoint("http://user:secret@127.0.0.1") is None
    assert _endpoint("http://127.0.0.1, http://evil.example") is None
    assert _endpoint("http://127.0.0.1:99999") is None
    assert _endpoint("http://") is None
    assert _endpoint("http:///missing-host") is None
    assert _endpoint("http://127.0.0.1") == ("http", "127.0.0.1", 80)
    assert _endpoint("HTTP://127.0.0.1:80/ui") == ("http", "127.0.0.1", 80)
    assert _endpoint("https://127.0.0.1") == ("https", "127.0.0.1", 443)
    assert _endpoint("http://127.0.0.1:8000") == ("http", "127.0.0.1", 8000)


def test_origin_must_match_scheme_host_and_port():
    ok = _request(headers={"origin": "http://127.0.0.1"})
    assert origin_allowed(ok) is True
    explicit_port = _request(headers={"origin": "http://127.0.0.1:80"})
    assert origin_allowed(explicit_port) is True
    https = _request(headers={"origin": "https://127.0.0.1"})
    assert origin_allowed(https) is False
    other_port = _request(headers={"origin": "http://127.0.0.1:8000"})
    assert origin_allowed(other_port) is False
    evil = _request(headers={"origin": "http://evil.example"})
    assert origin_allowed(evil) is False
    # A bad Origin is not rescued by a same-site Referer.
    both = _request(
        headers={
            "origin": "http://evil.example",
            "referer": "http://127.0.0.1/ui/companies/new",
        }
    )
    assert origin_allowed(both) is False


def test_referer_is_only_the_fallback_and_get_is_not_checked():
    missing = _request()
    assert origin_allowed(missing) is False
    referer = _request(
        headers={"referer": "http://127.0.0.1/ui/companies/new"}
    )
    assert origin_allowed(referer) is True
    blank_origin = _request(
        headers={
            "origin": "   ",
            "referer": "http://127.0.0.1/ui",
        }
    )
    assert origin_allowed(blank_origin) is True
    evil_referer = _request(headers={"referer": "http://evil.example/form"})
    assert origin_allowed(evil_referer) is False
    # A suffix, a dotted host, or userinfo must not look like loopback.
    # localhost and 127.0.0.1 are different hosts.
    for referer in (
        "http://127.0.0.1:8000.evil",
        "http://127.0.0.1.evil",
        "http://127.0.0.1:8000@evil",
        "http://localhost/ui/companies/new",
    ):
        forged = _request(headers={"referer": referer})
        assert origin_allowed(forged) is False, referer
    swapped = _request(
        host="localhost",
        headers={"referer": "http://127.0.0.1/ui/companies/new"},
    )
    assert origin_allowed(swapped) is False
    # GET does not change rows, so a foreign Origin is ignored.
    require_same_origin(
        _request(method="GET", headers={"origin": "http://evil.example"})
    )
    require_same_origin(_request(method="HEAD"))
