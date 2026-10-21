"""Alembic uses the caller's connection and can render UTCDateTime."""

from pathlib import Path

from sqlalchemy import text

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.config import settings
from app.core.database import create_db_engine
from tests.company_migration import (
    LEGACY_COMPANIES,
    LEGACY_METRICS,
    upgrade_head,
)

ROOT = Path(__file__).resolve().parents[1]


def test_alembic_script_has_one_head():
    """One head: 0006 revises 0005.

    0005 is notes and theses, 0004 is the watchlist, and 0003 is
    the unique ticker index. 0003 revises 0002.
    """
    config = Config(str(ROOT / "alembic.ini"))
    heads = ScriptDirectory.from_config(config).get_heads()
    assert heads == ["0006"]


def test_version_num_format_is_a_literal_percent():
    """A single percent in alembic.ini is ConfigParser interpolation.

    ``%%04d`` is the literal ``%04d`` Alembic uses for a new revision
    id. A single ``%`` raises ``InterpolationSyntaxError`` on every
    alembic command.
    """
    config = Config(str(ROOT / "alembic.ini"))
    assert config.get_main_option("version_num_format") == "%04d"


def test_supplied_connection_does_not_open_the_settings_url(
    tmp_path, monkeypatch
):
    """A closed port would fail the upgrade if settings were read."""
    monkeypatch.setattr(
        settings,
        "DATABASE_URL",
        "postgresql://postgres:postgres@127.0.0.1:1/not_used",
    )
    engine = create_db_engine(f"sqlite:///{tmp_path / 'linked.db'}")
    with engine.begin() as connection:
        connection.execute(text(LEGACY_COMPANIES))
        connection.execute(text(LEGACY_METRICS))
    with engine.connect() as connection:
        upgrade_head(connection)
        stored = connection.execute(
            text("SELECT instrument_type FROM companies")
        ).fetchall()
    assert stored == []
    engine.dispose()


def test_autogenerate_imports_utc_datetime(tmp_path):
    """An empty database makes autogenerate render the timestamp columns.

    The generated upgrade must import UTCDateTime. The fully qualified
    ``app.core.utc_datetime.UTCDateTime`` form raises NameError because
    the name ``app`` does not exist in that file.
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    config = Config(str(ROOT / "alembic.ini"))
    written = None
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            # Stamp without creating tables. Autogenerate then renders
            # the model, including UTCDateTime, against an empty file.
            command.stamp(config, "head")
            script = command.revision(
                config,
                message="render check",
                autogenerate=True,
                rev_id="9998",
            )
        written = Path(script.path)
        source = written.read_text()
    finally:
        if written is not None and written.exists():
            written.unlink()
        engine.dispose()

    assert "from app.core.utc_datetime import UTCDateTime" in source
    assert "UTCDateTime(timezone=True)" in source
    assert "app.core.utc_datetime.UTCDateTime" not in source
    # PriceAmount is not imported in a migration. The column is the
    # numeric type Alembic already knows how to render.
    assert "sa.Numeric(20, 8)" in source
    assert "PriceAmount" not in source
