"""SCRUM-200: rol contabilidad en enum userrole

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-05-20

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = 'userrole'
                  AND e.enumlabel = 'contabilidad'
            ) THEN
                ALTER TYPE userrole ADD VALUE 'contabilidad';
            END IF;
        END $$
    """)


def downgrade() -> None:
    # PostgreSQL no permite quitar valores de un ENUM de forma portable.
    pass
