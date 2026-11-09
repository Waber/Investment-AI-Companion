"""Proof that a create request is the local demo seeder.

Ordinary company and metric JSON has no ``source`` field and no
``is_synthetic`` field. A caller cannot choose those values.

``seed_demo --base-url`` may mark a new company synthetic and set
``source`` to ``demo`` only when all of these are true:

- ``DEMO_SEED_ENABLED`` is true. It defaults to false, so a
  production process ignores the header.
- ``request.client.host`` is loopback (``127.0.0.1`` or ``::1``).
  This helper does not read ``X-Forwarded-For`` itself. Uvicorn's
  default is ``proxy_headers=True`` and
  ``forwarded_allow_ips=127.0.0.1``. That middleware rewrites
  ``request.client`` from ``X-Forwarded-For`` when the TCP peer is
  ``127.0.0.1``. ``::1`` is not in that default list, so a peer of
  ``::1`` is not rewritten. After a rewrite, a remote address
  fails the loopback check and the row stays manual.
- The header is 64 lowercase hex characters and matches the HMAC
  of this process's ``SECRET_KEY``. Anything else, including a
  non-ASCII value of the same length, is not a token. The create
  stays manual. It does not raise.

Updates do not call this helper. A matching header cannot change
a row that already exists.
"""

import hmac
import re
from hashlib import sha256

DEMO_SEED_HEADER = "X-IAC-Demo-Seed"
_PURPOSE = b"iac-seed-demo-v1"
_LOOPBACK_PEERS = frozenset({"127.0.0.1", "::1"})
# sha256 hex digest. Upper case is a different string and is rejected.
_TOKEN_RE = re.compile(r"^[0-9a-f]{64}$")


def demo_seed_token(secret):
    """Return the header value for this secret. The secret stays put."""
    if not isinstance(secret, str) or secret == "":
        raise ValueError("demo seed token needs a secret")
    return hmac.new(secret.encode("utf-8"), _PURPOSE, sha256).hexdigest()


def _is_seed_token(value):
    """True for 64 lowercase hex characters. Other text is not compared."""
    return isinstance(value, str) and _TOKEN_RE.fullmatch(value) is not None


def demo_seed_authorized(*, client_host, header, expected_token):
    """True only for a loopback peer with the exact hex token.

    A value that is not 64 lowercase hex characters returns false
    before ``compare_digest``. That call raises ``TypeError`` on a
    non-ASCII ``str``, which would turn the create into HTTP 500.
    """
    if client_host not in _LOOPBACK_PEERS:
        return False
    if not _is_seed_token(header) or not _is_seed_token(expected_token):
        return False
    return hmac.compare_digest(header, expected_token)


def request_is_demo_seed(request, secret, *, enabled):
    """Read the peer and the header. The body is not consulted.

    ``enabled`` is ``settings.DEMO_SEED_ENABLED``. False skips the
    header, so a malformed value cannot raise.
    """
    if enabled is not True:
        return False
    client = request.client
    host = None if client is None else client.host
    return demo_seed_authorized(
        client_host=host,
        header=request.headers.get(DEMO_SEED_HEADER),
        expected_token=demo_seed_token(secret),
    )
