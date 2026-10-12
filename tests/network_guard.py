"""Helpers that make a unit test fail when it reaches the network.

``tests/conftest.py`` installs these through an autouse fixture. They
live in their own module so a test can import ``NetworkBlockedError``
without importing ``conftest`` a second time.
"""

import ipaddress
import socket
from typing import Any


class NetworkBlockedError(AssertionError):
    """A test tried to open a connection to a non-loopback address."""


def is_loopback(address: Any) -> bool:
    """True for a Unix socket path or a loopback host.

    Internet sockets pass ``(host, port, ...)`` tuples. Unix sockets
    pass a ``str`` or ``bytes`` path, which never leaves the machine.
    """
    if not isinstance(address, tuple):
        return True
    host = address[0]
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        # A hostname other than localhost would need a DNS lookup.
        return False


def refuse_remote(address: Any) -> None:
    if not is_loopback(address):
        raise NetworkBlockedError(
            f"Test tried to connect to {address!r}. Automated tests must "
            "not reach the network: use a fake or a stub."
        )


def install(monkeypatch) -> None:
    """Patch the three ways Python code opens a client connection."""
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_create_connection = socket.create_connection

    def connect(self, address):
        refuse_remote(address)
        return real_connect(self, address)

    def connect_ex(self, address):
        refuse_remote(address)
        return real_connect_ex(self, address)

    def create_connection(address, *args, **kwargs):
        refuse_remote(address)
        return real_create_connection(address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "create_connection", create_connection)
