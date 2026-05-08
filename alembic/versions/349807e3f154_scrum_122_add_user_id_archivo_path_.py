"""scrum-122 add user_id archivo_path timestamps

Revision ID: 349807e3f154
Revises: b8e1f3a2c4d5
Create Date: 2026-05-07 23:30:06.810873

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "349807e3f154"
down_revision: str | None = "b8e1f3a2c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) Agregar columnas nuevas (NULL al inicio para backfill seguro)
    op.execute(
        """
        ALTER TABLE incapacidades
            ADD COLUMN IF NOT EXISTS user_id UUID,
            ADD COLUMN IF NOT EXISTS archivo_path TEXT,
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ
    """
    )

    # 2) Backfill: user_id se alinea con el titular (colaborador_id)
    op.execute(
        """
        UPDATE incapacidades
        SET user_id = colaborador_id
        WHERE user_id IS NULL
    """
    )

    # 3) created_at: usar fecha_recepcion si existe; si no, now()
    op.execute(
        """
        UPDATE incapacidades
        SET created_at = COALESCE(fecha_recepcion, now())
        WHERE created_at IS NULL
    """
    )

    # 4) Enforce NOT NULL y defaults
    op.execute(
        """
        ALTER TABLE incapacidades
            ALTER COLUMN user_id SET NOT NULL,
            ALTER COLUMN created_at SET NOT NULL,
            ALTER COLUMN created_at SET DEFAULT now()
    """
    )

    # 5) FK a users (integridad referencial)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_incapacidades_user_id'
            ) THEN
                ALTER TABLE incapacidades
                    ADD CONSTRAINT fk_incapacidades_user_id
                    FOREIGN KEY (user_id) REFERENCES users (id);
            END IF;
        END $$;
    """
    )

    # 6) Índice para consultas por user_id
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_incapacidades_user_id ON incapacidades (user_id)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE incapacidades DROP CONSTRAINT IF EXISTS fk_incapacidades_user_id"
    )
    op.execute("DROP INDEX IF EXISTS ix_incapacidades_user_id")
    op.execute(
        """
        ALTER TABLE incapacidades
            DROP COLUMN IF EXISTS created_at,
            DROP COLUMN IF EXISTS archivo_path,
            DROP COLUMN IF EXISTS user_id
    """
    )
