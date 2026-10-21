"""add notes and theses

Revision ID: 0033
Revises: 0001
Create Date: 2026-10-21

Creates ``notes`` and ``theses``. Both reference ``companies.id``
with ON DELETE CASCADE, so deleting a company removes its research.
This revision does not rebuild ``companies``.

``0033`` is the issue number, not the next integer after ``0001``.
Open pull requests #83 and #87 each add a revision named ``0002``,
and the watchlist work for #32 adds one too. This file's
``down_revision`` is master's current head (``0001``). After those
merge, point ``down_revision`` at the new head. The revision id
stays ``0033`` so it does not collide with those ``0002`` files.

SQLite and PostgreSQL both receive the same CREATE TABLE. The
status CHECK is in the table definition, which SQLite accepts.
There is no PostgreSQL ENUM, because one column type has to work
on both databases.
"""

import sqlalchemy as sa

from alembic import op
from app.core.utc_datetime import UTCDateTime
from app.models.research import (
    NOTE_BODY_MAX,
    THESIS_BODY_MAX,
    THESIS_BREAKERS_MAX,
    THESIS_STATUS_CHECK,
    THESIS_TITLE_MAX,
    ThesisStatus,
)

revision = "0033"
down_revision = "0001"
branch_labels = None
depends_on = None

_STATUS_LENGTH = max(len(item.value) for item in ThesisStatus)


def upgrade() -> None:
    op.create_table(
        "notes",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.String(length=NOTE_BODY_MAX), nullable=False),
        sa.Column("created_at", UTCDateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", UTCDateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_notes_company_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_notes_company_id", "notes", ["company_id"])
    op.create_table(
        "theses",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=THESIS_TITLE_MAX), nullable=False),
        sa.Column("body", sa.String(length=THESIS_BODY_MAX), nullable=False),
        sa.Column(
            "thesis_breakers",
            sa.String(length=THESIS_BREAKERS_MAX),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "status",
            sa.String(length=_STATUS_LENGTH),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("created_at", UTCDateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", UTCDateTime(), server_default=sa.func.now()),
        sa.CheckConstraint(THESIS_STATUS_CHECK, name="ck_theses_status"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_theses_company_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_theses_company_id", "theses", ["company_id"])


def downgrade() -> None:
    op.drop_index("ix_theses_company_id", table_name="theses")
    op.drop_table("theses")
    op.drop_index("ix_notes_company_id", table_name="notes")
    op.drop_table("notes")
