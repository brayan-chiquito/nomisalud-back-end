"""SCRUM-128: columna raw_response en extraccion_ia

Revision ID: c4d8e2f1a9b3
Revises: 349807e3f154
Create Date: 2026-05-09

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c4d8e2f1a9b3"
down_revision: str | None = "349807e3f154"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE extraccion_ia
            ADD COLUMN IF NOT EXISTS raw_response TEXT
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE extraccion_ia DROP COLUMN IF EXISTS raw_response")
