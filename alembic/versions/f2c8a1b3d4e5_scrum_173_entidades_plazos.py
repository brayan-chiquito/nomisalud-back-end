"""SCRUM-173: tabla entidades_plazos

Revision ID: f2c8a1b3d4e5
Revises: e7a3b9c1d2f4
Create Date: 2026-05-18

"""

from collections.abc import Sequence

from alembic import op

revision: str = "f2c8a1b3d4e5"
down_revision: str | None = "e7a3b9c1d2f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'unidadplazo') THEN
                CREATE TYPE unidadplazo AS ENUM ('dias', 'meses', 'anos');
            END IF;
        END $$
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS entidades_plazos (
            id UUID PRIMARY KEY,
            entidad_nombre VARCHAR(120) NOT NULL,
            tipo_incapacidad VARCHAR(80) NOT NULL,
            valor_limite INTEGER NOT NULL,
            unidad_limite unidadplazo NOT NULL,
            dias_limite INTEGER NOT NULL,
            dias_alerta INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_entidades_plazos_entidad_tipo
                UNIQUE (entidad_nombre, tipo_incapacidad)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_entidades_plazos_entidad_nombre "
        "ON entidades_plazos (entidad_nombre)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_entidades_plazos_tipo_incapacidad "
        "ON entidades_plazos (tipo_incapacidad)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS entidades_plazos")
    op.execute("DROP TYPE IF EXISTS unidadplazo")
