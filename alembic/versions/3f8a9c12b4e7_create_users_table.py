"""create users table

Revision ID: 3f8a9c12b4e7
Revises:
Create Date: 2026-04-02 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "3f8a9c12b4e7"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Crear el tipo ENUM con SQL puro evita que SQLAlchemy reutilice la
    # instancia del modelo (que tiene create_type=True) y vuelva a intentar
    # crearlo dentro de op.create_table().
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
                CREATE TYPE userrole AS ENUM (
                    'colaborador',
                    'auxiliar_rrhh',
                    'coordinador_rrhh',
                    'admin'
                );
            END IF;
        END $$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          UUID         NOT NULL,
            email       VARCHAR(255) NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role        userrole     NOT NULL,
            CONSTRAINT pk_users        PRIMARY KEY (id),
            CONSTRAINT uq_users_email  UNIQUE (email)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TYPE IF EXISTS userrole")
