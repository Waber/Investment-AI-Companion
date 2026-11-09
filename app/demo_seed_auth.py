"""Proof that a create request is the local demo seeder.

Ordinary company and metric JSON has no ``source`` field and no
``is_synthetic`` field. A caller cannot choose those values.

``seed_demo --base-url`` is the one other writer. It may mark a
new company synthetic and set ``source`` to ``demo`` only when
both of these are true:

- The peer address is loopback (``127.0.0.1`` or ``::1``). The
  check reads the connection peer, not ``Host`` or
  ``X-Forwarded-For``.
- The header value is the HMAC of this process's ``SECRET_KEY``.
  The header is not a source name. ``demo``, ``1``, and a blank
  value do not match.

Updates do not call this helper. A matching header cannot change
a row that already exists. A wrong header, or a remote peer, is
the same as no header: the create stays ``manual`` and not
synthetic.
"""

import hmac
from hashlib import sha256

DEMO_SEED_HEADER = "X-IAC-Demo-Seed"
_PURPOSE = b"iac-seed-demo-v1"
_LOOPBACK_PEERS = frozenset({"127.0.0.1", "::1"})


def demo_seed_token(secret):
    """Return the header value for this secret. The secret stays put."""
    if not isinstance(secret, str) or secret == "":
        raise ValueError("demo seed token needs a secret")
    return hmac.new(secret.encode("utf-8"), _PURPOSE, sha256).hexdigest()


def demo_seed_authorized(*, client_host, header, expected_token):
    """True only for a loopback peer with the exact token.

    A length mismatch still runs a compare, so the function does
    not raise and does not return early on the first different
    character. ``compare_digest`` requires equal lengths, so a
    different length is compared against the expected token
    itself and then rejected.
    """
    if client_host not in _LOOPBACK_PEERS:
        return False
    if not isinstance(header, str) or not isinstance(expected_token, str):
        return False
    if len(header) != len(expected_token):
        hmac.compare_digest(expected_token, expected_token)
        return False
    return hmac.compare_digest(header, expected_token)


def request_is_demo_seed(request, secret):
    """Read the peer and the header. The body is not consulted."""
    client = request.client
    host = None if client is None else client.host
    return demo_seed_authorized(
        client_host=host,
        header=request.headers.get(DEMO_SEED_HEADER),
        expected_token=demo_seed_token(secret),
    )
