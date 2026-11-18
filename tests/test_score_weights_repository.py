"""The stored version moves in the database, not in a stale object."""

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, create_db_engine
from app.repositories.score_weights_repository import ScoreWeightsRepository
from app.scoring import default_weights


def _factory():
    engine = create_db_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    # Keep the loaded version. The default expires it on commit, which
    # would hide a read of the in-memory number.
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def test_save_increments_the_version_stored_in_the_database():
    """A second session can change the version before this one saves.

    Adding 1 to the number this session loaded would ignore that
    change. The UPDATE has to add 1 to the value in the table.
    """
    factory = _factory()
    first = factory()
    second = factory()
    try:
        repo = ScoreWeightsRepository(first)
        created = repo.save("STOCK", default_weights("STOCK"))
        assert created.version == 2
        second.execute(
            text(
                "UPDATE score_weights SET version = 9 "
                "WHERE instrument_type = 'STOCK'"
            )
        )
        second.commit()
        saved = repo.save("STOCK", default_weights("STOCK"))
        assert saved.version == 10
        assert saved.weights
        again = second.execute(
            text(
                "SELECT version FROM score_weights "
                "WHERE instrument_type = 'STOCK'"
            )
        ).scalar()
        assert again == 10
    finally:
        first.close()
        second.close()


def test_a_lost_insert_is_retried_once_and_returns_the_row(monkeypatch):
    """Two first PUTs can both see an empty table.

    The loser of the unique key rolls back and writes the row that
    won, instead of returning the driver's error text.
    """
    factory = _factory()
    session = factory()
    try:
        ScoreWeightsRepository(session).save("ETF", default_weights("ETF"))
        real_get = ScoreWeightsRepository.get
        calls = {"n": 0}

        def hidden_once(self, instrument_type):
            calls["n"] += 1
            if calls["n"] == 1:
                return None
            return real_get(self, instrument_type)

        monkeypatch.setattr(ScoreWeightsRepository, "get", hidden_once)
        saved = ScoreWeightsRepository(session).save(
            "ETF", default_weights("ETF")
        )
        assert saved.version == 3
        assert "cost" in saved.weights
        assert calls["n"] >= 2
    finally:
        session.close()


def test_a_second_insert_conflict_is_a_fixed_error(monkeypatch):
    factory = _factory()
    session = factory()
    try:

        def _explode(*_args, **_kwargs):
            raise IntegrityError(
                "INSERT", {}, Exception("driver said unique violation")
            )

        monkeypatch.setattr(session, "commit", _explode)
        try:
            ScoreWeightsRepository(session).save("ETC", default_weights("ETC"))
        except Exception as error:
            assert type(error).__name__ == "ScoreWeightsSaveError"
            assert "driver said" not in str(error)
        else:
            raise AssertionError("the second conflict must fail")
    finally:
        session.close()
