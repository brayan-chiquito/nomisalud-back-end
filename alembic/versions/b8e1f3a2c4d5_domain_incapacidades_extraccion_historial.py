"""users profile fields, incapacidades, extraccion_ia, historial_estados

Revision ID: b8e1f3a2c4d5
Revises: 3f8a9c12b4e7
Create Date: 2026-04-09 00:00:00.000000
"""

# DDL con bloques DO $$ y líneas largas hacia pg_catalog.
# ruff: noqa: E501

from collections.abc import Sequence

from alembic import op

revision: str = "b8e1f3a2c4d5"
down_revision: str | None = "3f8a9c12b4e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tipodocumento') THEN
                CREATE TYPE tipodocumento AS ENUM ('CC', 'CE', 'TI', 'PA', 'RC');
            END IF;
        END $$
    """)

    op.execute("""
        ALTER TABLE users
            ADD COLUMN nombre_completo VARCHAR(200),
            ADD COLUMN tipo_documento tipodocumento,
            ADD COLUMN numero_documento VARCHAR(20),
            ADD COLUMN area VARCHAR(100),
            ADD COLUMN cargo VARCHAR(100),
            ADD COLUMN eps_afiliacion VARCHAR(100),
            ADD COLUMN arl_afiliacion VARCHAR(100),
            ADD COLUMN activo BOOLEAN NOT NULL DEFAULT true,
            ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'archivotipo') THEN
                CREATE TYPE archivotipo AS ENUM ('pdf', 'jpg', 'png');
            END IF;
        END $$
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'incapacidadestado') THEN
                CREATE TYPE incapacidadestado AS ENUM (
                    'recibida',
                    'procesando_ia',
                    'en_verificacion',
                    'doc_incompleta',
                    'transcrita',
                    'cobrada',
                    'rechazada',
                    'pagada'
                );
            END IF;
        END $$
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'calidaddocumento') THEN
                CREATE TYPE calidaddocumento AS ENUM ('buena', 'regular', 'mala');
            END IF;
        END $$
    """)

    op.execute("""
        CREATE TABLE incapacidades (
            id UUID NOT NULL,
            radicado VARCHAR(20) NOT NULL,
            colaborador_id UUID NOT NULL,
            cargado_por UUID NOT NULL,
            archivo_uuid VARCHAR(36),
            archivo_tipo archivotipo,
            archivo_tamano_bytes INTEGER,
            estado incapacidadestado NOT NULL,
            documentacion_faltante TEXT[],
            fecha_recepcion TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT pk_incapacidades PRIMARY KEY (id),
            CONSTRAINT uq_incapacidades_radicado UNIQUE (radicado),
            CONSTRAINT fk_incapacidades_colaborador
                FOREIGN KEY (colaborador_id) REFERENCES users (id),
            CONSTRAINT fk_incapacidades_cargado_por
                FOREIGN KEY (cargado_por) REFERENCES users (id)
        )
    """)
    op.execute(
        "CREATE INDEX ix_incapacidades_radicado ON incapacidades (radicado)"
    )
    op.execute("CREATE INDEX ix_incapacidades_estado ON incapacidades (estado)")
    op.execute(
        "CREATE INDEX ix_incapacidades_fecha_recepcion ON incapacidades (fecha_recepcion)"
    )
    op.execute(
        "CREATE INDEX ix_incapacidades_colaborador_id ON incapacidades (colaborador_id)"
    )
    op.execute(
        "CREATE INDEX ix_incapacidades_cargado_por ON incapacidades (cargado_por)"
    )

    op.execute("""
        CREATE TABLE extraccion_ia (
            id UUID NOT NULL,
            incapacidad_id UUID NOT NULL,
            datos_extraidos JSONB NOT NULL DEFAULT '{}'::jsonb,
            campos_corregidos JSONB,
            validaciones JSONB,
            api_usada VARCHAR(50),
            modelo VARCHAR(80),
            tokens_input INTEGER,
            tokens_output INTEGER,
            costo_usd NUMERIC(8, 6),
            calidad_doc calidaddocumento,
            verificado_por UUID,
            verificado_en TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT pk_extraccion_ia PRIMARY KEY (id),
            CONSTRAINT uq_extraccion_ia_incapacidad_id UNIQUE (incapacidad_id),
            CONSTRAINT fk_extraccion_ia_incapacidad
                FOREIGN KEY (incapacidad_id) REFERENCES incapacidades (id) ON DELETE CASCADE,
            CONSTRAINT fk_extraccion_ia_verificado_por
                FOREIGN KEY (verificado_por) REFERENCES users (id)
        )
    """)
    op.execute(
        "CREATE INDEX ix_extraccion_ia_incapacidad_id ON extraccion_ia (incapacidad_id)"
    )
    op.execute(
        "CREATE INDEX ix_extraccion_ia_verificado_por ON extraccion_ia (verificado_por)"
    )

    op.execute("""
        CREATE TABLE historial_estados (
            id UUID NOT NULL,
            incapacidad_id UUID NOT NULL,
            estado_anterior incapacidadestado,
            estado_nuevo incapacidadestado NOT NULL,
            user_id UUID NOT NULL,
            observacion TEXT,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT pk_historial_estados PRIMARY KEY (id),
            CONSTRAINT fk_historial_estados_incapacidad
                FOREIGN KEY (incapacidad_id) REFERENCES incapacidades (id) ON DELETE CASCADE,
            CONSTRAINT fk_historial_estados_user
                FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    op.execute(
        "CREATE INDEX ix_historial_estados_incapacidad_id ON historial_estados (incapacidad_id)"
    )
    op.execute(
        "CREATE INDEX ix_historial_estados_timestamp ON historial_estados (timestamp)"
    )
    op.execute(
        "CREATE INDEX ix_historial_estados_user_id ON historial_estados (user_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS historial_estados")
    op.execute("DROP TABLE IF EXISTS extraccion_ia")
    op.execute("DROP TABLE IF EXISTS incapacidades")
    op.execute("DROP TYPE IF EXISTS calidaddocumento")
    op.execute("DROP TYPE IF EXISTS incapacidadestado")
    op.execute("DROP TYPE IF EXISTS archivotipo")

    op.execute("""
        ALTER TABLE users
            DROP COLUMN IF EXISTS created_at,
            DROP COLUMN IF EXISTS activo,
            DROP COLUMN IF EXISTS arl_afiliacion,
            DROP COLUMN IF EXISTS eps_afiliacion,
            DROP COLUMN IF EXISTS cargo,
            DROP COLUMN IF EXISTS area,
            DROP COLUMN IF EXISTS numero_documento,
            DROP COLUMN IF EXISTS tipo_documento,
            DROP COLUMN IF EXISTS nombre_completo
    """)
    op.execute("DROP TYPE IF EXISTS tipodocumento")
