"""SCRUM-193: marca pago_retrasado y dias_promedio_pago en plazos

Revision ID: e9f1a2b3c4d5
Revises: c8e9f1a2b3d4
Create Date: 2026-05-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e9f1a2b3c4d5"
down_revision: str | None = "c8e9f1a2b3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "incapacidades",
        sa.Column(
            "pago_retrasado",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "ix_incapacidades_pago_retrasado",
        "incapacidades",
        ["pago_retrasado"],
    )
    op.add_column(
        "entidades_plazos",
        sa.Column("dias_promedio_pago", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("entidades_plazos", "dias_promedio_pago")
    op.drop_index("ix_incapacidades_pago_retrasado", table_name="incapacidades")
    op.drop_column("incapacidades", "pago_retrasado")
