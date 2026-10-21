"""Notes and theses on PostgreSQL.

The cases live in ``tests.research_cases``. This module only opens
the PostgreSQL session. Without ``-m integration`` pytest deselects
the module.
"""

import pytest

from tests.research_cases import ResearchBehavior

pytestmark = pytest.mark.integration


class TestResearchNotesPostgres(ResearchBehavior):
    """The shared cases, against PostgreSQL."""


@pytest.fixture
def session(postgres_session_factory):
    db = postgres_session_factory()
    try:
        yield db
    finally:
        db.close()
