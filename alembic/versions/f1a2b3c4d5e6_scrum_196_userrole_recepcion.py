"""SCRUM-196: rol recepcion en enum userrole

Revision ID: f1a2b3c4d5e6
Revises: e9f1a2b3c4d5
Create Date: 2026-05-20

"""

from collections.abc import Sequence

from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e9f1a2b3c4d5"
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
                  AND e.enumlabel = 'recepcion'
            ) THEN
                ALTER TYPE userrole ADD VALUE 'recepcion';
            END IF;
        END $$
    """)


def downgrade() -> None:
    # PostgreSQL no permite quitar valores de un ENUM de forma portable.
    pass
