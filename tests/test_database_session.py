"""get_db yields one session per request and always closes it."""

import pytest

from app.core import database


class FakeSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


@pytest.fixture
def fake_session(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)
    return session


def test_get_db_yields_session_and_closes_after_request(fake_session):
    dependency = database.get_db()

    assert next(dependency) is fake_session
    assert fake_session.closed is False

    with pytest.raises(StopIteration):
        next(dependency)
    assert fake_session.closed is True


def test_get_db_closes_session_when_request_fails(fake_session):
    dependency = database.get_db()
    next(dependency)

    with pytest.raises(RuntimeError):
        dependency.throw(RuntimeError("endpoint failed"))

    assert fake_session.closed is True
