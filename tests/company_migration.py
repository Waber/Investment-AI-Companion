"""Apply revision 0001 to a connection that already has companies.

The application engine is not used. Callers pass the connection that
should change, including a PostgreSQL connection whose search_path
points at a scratch schema.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[1]

# The shape of companies before instrument_type and isin existed.
# Integer ids are inserted by the test. PostgreSQL does not add a
# sequence for a plain INTEGER primary key, and SQLite does not need one.
LEGACY_COMPANIES = """
CREATE TABLE companies (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    ticker VARCHAR(20) NOT NULL UNIQUE,
    currency VARCHAR(3) DEFAULT 'USD'
)
"""
LEGACY_METRICS = """
CREATE TABLE financial_metrics (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies (id)
)
"""


def _config(connection):
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


def upgrade_head(connection):
    command.upgrade(_config(connection), "head")


def downgrade_base(connection):
    command.downgrade(_config(connection), "base")
