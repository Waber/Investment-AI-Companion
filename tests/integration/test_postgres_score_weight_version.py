"""The version increment is one SQL expression on PostgreSQL too."""

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.repositories.score_weights_repository import ScoreWeightsRepository
from app.scoring import default_weights

pytestmark = pytest.mark.integration


def test_postgres_version_increment_uses_the_stored_value(postgres_engine):
    """A concurrent update of ``version`` is not replaced by a stale + 1."""
    factory = sessionmaker(
        bind=postgres_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    first = factory()
    second = factory()
    try:
        first.execute(text("DELETE FROM score_weights"))
        first.commit()
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
        stored = second.execute(
            text(
                "SELECT version FROM score_weights "
                "WHERE instrument_type = 'STOCK'"
            )
        ).scalar()
        assert stored == 10
    finally:
        first.execute(text("DELETE FROM score_weights"))
        first.commit()
        first.close()
        second.close()
