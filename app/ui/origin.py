"""Same-origin check for state-changing /ui requests.

There is no login and no session, so a CSRF token would have nothing
to bind to. A browser still sends a cross-site form POST with cookies
it has for this host (the language cookie is one). The check below
refuses that post.

The browser sets ``Origin`` and the page cannot. When ``Origin`` is
missing, the ``Referer`` URL is used the same way. The scheme, host,
and port must match this request. ``TrustedHostMiddleware`` already
rejects a ``Host`` outside ``ALLOWED_HOSTS``, so a match is one of
those hosts and not an open redirect. The check relies on
``TrustedHostMiddleware``, so ``ALLOWED_HOSTS`` must stay
loopback-only (DNS rebinding).

The pages send ``Referrer-Policy: same-origin``. ``no-referrer`` makes
Chrome put ``Origin: null`` on an ordinary form POST and omit
``Referer``, so this check would refuse every save. ``same-origin``
still withholds the address from a company website.

``http://127.0.0.1`` and ``http://127.0.0.1:80`` are the same endpoint.
Any other port must be written out. ``https`` does not match ``http``.

Safe methods (GET, HEAD, OPTIONS, TRACE) are not checked by
``require_same_origin``. They do not change stored rows. The
language cookie is set by ``POST /ui/language/{code}``. That POST
is an unsafe method, so this dependency checks it. The PL and EN
controls are small same-origin forms with a hidden ``next`` field.
A same-origin form POST sends ``Origin``. A missing or blank
``Origin`` falls back to ``Referer``. A cross-site ``Origin``
fails even when ``Referer`` is ours. A cross-site ``Referer``
with no ``Origin`` fails.

``GET /ui/language/{code}`` does not set the cookie. An old
bookmark or a typed URL redirects to ``/ui`` (or to a safe
``next``) and is not a 403. An unknown code is the HTML 404 and
does not set a cookie. A cross-site POST of an unknown code is
403, because the dependency runs before the route sees the code.
"""

from urllib.parse import urlsplit

from fastapi import Request

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
_DEFAULT_PORTS = {"http": 80, "https": 443}


class OriginRejected(Exception):
    """The stated origin is not this request's own scheme, host, and port."""


def _endpoint(value):
    """Return ``(scheme, host, port)`` or None when ``value`` is not http(s).

    A comma, a space, or a username is rejected. Those show up in a
    forged header, not in a browser's Origin.
    """
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate or candidate.casefold() == "null":
        return None
    if any(character in candidate for character in " \t\r\n,"):
        return None
    parts = urlsplit(candidate)
    scheme = parts.scheme.casefold()
    if scheme not in _DEFAULT_PORTS:
        return None
    if parts.username is not None or parts.password is not None:
        return None
    host = parts.hostname
    if not host:
        return None
    try:
        port = parts.port
    except ValueError:
        return None
    if port is None:
        port = _DEFAULT_PORTS[scheme]
    return scheme, host.casefold(), port


def _stated_endpoint(request):
    """Origin when the header is present, otherwise the Referer URL."""
    origin = request.headers.get("origin")
    if origin is not None and origin.strip():
        return _endpoint(origin)
    referer = request.headers.get("referer")
    if referer is not None and referer.strip():
        return _endpoint(referer)
    return None


def origin_allowed(request):
    """True when the stated endpoint is this request's own.

    Used for unsafe methods, including the language-switch POST. A
    missing or blank ``Origin`` falls back to ``Referer``. Neither
    header means the caller did not name an endpoint.
    """
    expected = _endpoint(str(request.base_url))
    stated = _stated_endpoint(request)
    if expected is None or stated is None:
        return False
    return expected == stated


def require_same_origin(request: Request):
    """Dependency: reject a state-changing request from another origin.

    Wired on both /ui routers so a new POST cannot forget the check.
    """
    if request.method.upper() in _SAFE_METHODS:
        return
    if not origin_allowed(request):
        raise OriginRejected()


def forbidden_page(request: Request, exc: OriginRejected):
    """HTML 403. ``exc`` is unused; the status is the whole message.

    Imported lazily. This module is imported by the page router, and
    the page router owns the shared security headers.
    """
    from app.ui.router import _with_ui_headers
    from app.ui.templating import render

    return _with_ui_headers(render(request, "forbidden.html", status_code=403))
