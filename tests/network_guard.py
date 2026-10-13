"""Helpers that make a unit test fail when it reaches the network.

``tests/conftest.py`` installs these through an autouse fixture. They
live in their own module so a test can import ``NetworkBlockedError``
without importing ``conftest`` a second time.

What the guard sees: Python code that connects through the ``socket``
module (``requests``, ``urllib3``, ``httpx``, ``http.client``) and any
name lookup through ``socket.getaddrinfo`` or ``gethostbyname``.

What it cannot see: clients written in C that open their own sockets.
That is ``libpq`` (psycopg2, the PostgreSQL driver) and ``libcurl``
(``curl_cffi``, which yfinance prefers). The root ``conftest.py`` sets
``YF_DISABLE_CURL_CFFI`` so yfinance uses ``requests`` instead, which
the guard does see. Windows' asyncio proactor loop (``ConnectEx``) is
also not covered.
"""

import ipaddress
import socket
from typing import Any, List


class NetworkBlockedError(AssertionError):
    """A test tried to reach a non-loopback address or host name."""


# Every blocked attempt is recorded here. Code under test may swallow
# the exception (``except Exception``), so the autouse fixture also
# fails the test at teardown while this list is not empty.
ATTEMPTS: List[str] = []


def is_loopback_host(host: Any) -> bool:
    """True for ``localhost`` and loopback IP addresses (v4 and v6)."""
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if not isinstance(host, str):
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        # Another host name would need a DNS lookup.
        return False


def is_loopback(address: Any) -> bool:
    """True for a Unix socket path or a loopback address tuple.

    Internet sockets pass ``(host, port, ...)`` tuples. Unix sockets
    pass a ``str`` or ``bytes`` path, which never leaves the machine.
    """
    if not isinstance(address, tuple):
        return True
    return is_loopback_host(address[0])


def refuse_remote(address: Any) -> None:
    if not is_loopback(address):
        _refuse(f"connect to {address!r}")


def refuse_remote_host(host: Any) -> None:
    # None means "the local machine" for getaddrinfo (passive lookups).
    if host is not None and not is_loopback_host(host):
        _refuse(f"resolve the host name {host!r}")


def _refuse(action: str) -> None:
    message = (
        f"Test tried to {action}. Automated tests must not reach the "
        "network: use a fake or a stub."
    )
    ATTEMPTS.append(message)
    raise NetworkBlockedError(message)


def install(monkeypatch) -> None:
    """Patch the ways Python code connects or looks up a host name."""
    ATTEMPTS.clear()
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_create_connection = socket.create_connection
    real_getaddrinfo = socket.getaddrinfo
    real_gethostbyname = socket.gethostbyname

    def connect(self, address):
        refuse_remote(address)
        return real_connect(self, address)

    def connect_ex(self, address):
        refuse_remote(address)
        return real_connect_ex(self, address)

    def create_connection(address, *args, **kwargs):
        refuse_remote(address)
        return real_create_connection(address, *args, **kwargs)

    def getaddrinfo(host, *args, **kwargs):
        refuse_remote_host(host)
        return real_getaddrinfo(host, *args, **kwargs)

    def gethostbyname(host):
        refuse_remote_host(host)
        return real_gethostbyname(host)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "create_connection", create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(socket, "gethostbyname", gethostbyname)
