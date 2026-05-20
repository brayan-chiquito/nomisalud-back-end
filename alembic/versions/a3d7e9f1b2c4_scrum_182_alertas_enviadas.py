"""SCRUM-182: tabla alertas_enviadas

Revision ID: a3d7e9f1b2c4
Revises: f2c8a1b3d4e5
Create Date: 2026-05-18

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a3d7e9f1b2c4"
down_revision: str | None = "f2c8a1b3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tipoalerta') THEN
                CREATE TYPE tipoalerta AS ENUM (
                    'vencimiento_amarillo',
                    'vencimiento_rojo'
                );
            END IF;
        END $$
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS alertas_enviadas (
            id UUID PRIMARY KEY,
            incapacidad_id UUID NOT NULL
                REFERENCES incapacidades(id) ON DELETE CASCADE,
            tipo_alerta tipoalerta NOT NULL,
            enviada_en TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_alertas_enviadas_incapacidad_id "
        "ON alertas_enviadas (incapacidad_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_alertas_enviadas_tipo_alerta "
        "ON alertas_enviadas (tipo_alerta)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_alertas_enviadas_enviada_en "
        "ON alertas_enviadas (enviada_en)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_alertas_enviadas_dedup "
        "ON alertas_enviadas (incapacidad_id, tipo_alerta, enviada_en DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS alertas_enviadas")
    op.execute("DROP TYPE IF EXISTS tipoalerta")
