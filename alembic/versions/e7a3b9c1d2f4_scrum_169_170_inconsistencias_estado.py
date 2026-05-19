"""SCRUM-169/170: tabla inconsistencias y estado inconsistencia_detectada

Revision ID: e7a3b9c1d2f4
Revises: c4d8e2f1a9b3
Create Date: 2026-05-18

"""

from collections.abc import Sequence

from alembic import op

revision: str = "e7a3b9c1d2f4"
down_revision: str | None = "c4d8e2f1a9b3"
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
                WHERE t.typname = 'incapacidadestado'
                  AND e.enumlabel = 'inconsistencia_detectada'
            ) THEN
                ALTER TYPE incapacidadestado
                    ADD VALUE 'inconsistencia_detectada';
            END IF;
        END $$
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS inconsistencias (
            id UUID PRIMARY KEY,
            incapacidad_id UUID NOT NULL
                REFERENCES incapacidades(id) ON DELETE CASCADE,
            tipo VARCHAR(80) NOT NULL,
            descripcion TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_inconsistencias_incapacidad_id "
        "ON inconsistencias (incapacidad_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS inconsistencias")
    # PostgreSQL no permite quitar valores de un ENUM de forma portable.
