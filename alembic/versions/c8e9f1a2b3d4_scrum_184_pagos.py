"""SCRUM-184: tablas pagos y pagos_incapacidades

Revision ID: c8e9f1a2b3d4
Revises: a3d7e9f1b2c4
Create Date: 2026-05-20

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c8e9f1a2b3d4"
down_revision: str | None = "a3d7e9f1b2c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'pagoestado') THEN
                CREATE TYPE pagoestado AS ENUM ('registrado', 'anulado');
            END IF;
        END $$
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS pagos (
            id UUID PRIMARY KEY,
            entidad_origen VARCHAR(120) NOT NULL,
            referencia VARCHAR(120) NOT NULL,
            monto NUMERIC(18, 2) NOT NULL,
            fecha_operacion TIMESTAMPTZ NOT NULL,
            user_id UUID NOT NULL REFERENCES users(id),
            estado pagoestado NOT NULL DEFAULT 'registrado',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_pagos_entidad_origen_referencia
                UNIQUE (entidad_origen, referencia)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_pagos_entidad_origen ON pagos (entidad_origen)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_pagos_referencia ON pagos (referencia)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_pagos_fecha_operacion ON pagos (fecha_operacion)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_pagos_user_id ON pagos (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pagos_estado ON pagos (estado)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS pagos_incapacidades (
            pago_id UUID NOT NULL REFERENCES pagos(id) ON DELETE CASCADE,
            incapacidad_id UUID NOT NULL REFERENCES incapacidades(id) ON DELETE CASCADE,
            PRIMARY KEY (pago_id, incapacidad_id)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_pagos_incap_pago ON pagos_incapacidades (pago_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_pagos_incap_incap "
        "ON pagos_incapacidades (incapacidad_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pagos_incapacidades")
    op.execute("DROP TABLE IF EXISTS pagos")
    op.execute("DROP TYPE IF EXISTS pagoestado")
