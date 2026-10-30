"""record when a thesis was closed

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-29

Adds ``theses.closed_at``, a nullable timestamp with a time zone:
the same column type as ``updated_at``. The application sets it when
a thesis is closed and clears it when the thesis is reopened.

A thesis that is already closed has no record of when that happened.
Its last edit is the closest known time, so upgrade copies
``updated_at`` into ``closed_at`` on closed rows. Active rows stay
NULL.

``op.add_column`` appends the column on both databases. The model
declares it last as well, so ``create_all`` builds the same order.

Downgrade drops the column. PostgreSQL does that in place. On SQLite,
batch mode copies ``theses``: it creates a table without the column,
copies the rows, drops the old table, and renames the copy. The copy
is built from the reflected table, so ``ck_theses_status``,
``fk_theses_company_id`` with ON DELETE CASCADE, and
``ix_theses_company_id`` come back under the same names. No table
references ``theses``, so this copy does not have to turn foreign
keys off, unlike the ``companies`` copy in revision 0007.

``down_revision`` is ``0007``, so Alembic keeps one head. The column
type and the SQL are literals. This file does not import application
or script code.
"""

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "theses",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE theses SET closed_at = updated_at WHERE status = 'closed'"
    )


def downgrade() -> None:
    # On PostgreSQL batch mode runs ALTER TABLE ... DROP COLUMN. On
    # SQLite it copies the table, as the module docstring describes.
    # resolve_fks=False reflects theses alone. Following the foreign
    # key would reflect companies as well, and SQLite warns that it
    # cannot read the upper(ticker) index there. The copy still
    # writes the foreign key; it only needs the referenced names.
    with op.batch_alter_table(
        "theses",
        reflect_kwargs={"resolve_fks": False},
    ) as batch:
        batch.drop_column("closed_at")
