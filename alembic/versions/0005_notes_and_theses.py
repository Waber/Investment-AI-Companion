"""add notes and theses

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-21

Creates ``notes`` and ``theses``. Both reference ``companies.id``
with ON DELETE CASCADE, so deleting a company removes its research.
This revision does not rebuild ``companies``.

This revises ``0004``, the watchlist revision. The file used to be
``0033``. After the revisions ahead merged, this one moved to
``0005`` so Alembic has a single head. The slug stays
``notes_and_theses``. Lengths, the status CHECK, and the revision
ids are literals. This file does not import application or script
code.

SQLite and PostgreSQL both receive the same CREATE TABLE. The
status CHECK is in the table definition, which SQLite accepts.
There is no PostgreSQL ENUM, because one column type has to work
on both databases.

A database that ``create_all`` already built has these tables.
Stamp that database (``alembic stamp head``). Running ``upgrade``
there would try to create the tables again. A database that
stopped at revision ``0004`` can upgrade.
"""

import sqlalchemy as sa

from alembic import op

# Lengths and the status CHECK are copied here on purpose.
# Importing them from ``app.models.research`` would rewrite this
# revision when those constants change. 10000 is the note body
# and the thesis body. 200 is the title. 5000 is thesis-breakers.
# 6 is the length of ``active`` and of ``closed``.

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notes",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.String(length=10000), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
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
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.String(length=10000), nullable=False),
        sa.Column(
            "thesis_breakers",
            sa.String(length=5000),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "status",
            sa.String(length=6),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'closed')",
            name="ck_theses_status",
        ),
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
