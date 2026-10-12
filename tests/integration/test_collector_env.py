"""The collector setting and the network guard in integration runs.

The root ``conftest.py`` imports ``Settings`` before ``tests/conftest.py``
when the command selects ``integration``. These tests prove that
``DATA_COLLECTOR`` is still ``fake`` then, and that the guard leaves
integration tests alone. They open no connection.
"""

import socket

import pytest

from app.core.config import settings

pytestmark = pytest.mark.integration


def test_data_collector_is_fake_in_the_integration_selection():
    assert settings.DATA_COLLECTOR == "fake"


def test_integration_tests_are_exempt_from_the_network_guard(block_network):
    # The fixture yields a plain list and installs no patch.
    assert block_network == []
    assert socket.create_connection.__module__ == "socket"
    assert socket.getaddrinfo.__module__ == "socket"
