"""Parametrización de plazos por entidad y tipo de incapacidad (SCRUM-173)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UnidadPlazo(str, enum.Enum):
    """Unidad temporal de entrada; se normaliza a días para cálculos."""

    DIAS = "dias"
    MESES = "meses"
    ANOS = "anos"


class EntidadPlazo(Base):
    __tablename__ = "entidades_plazos"
    __table_args__ = (
        UniqueConstraint(
            "entidad_nombre",
            "tipo_incapacidad",
            name="uq_entidades_plazos_entidad_tipo",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    entidad_nombre: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    tipo_incapacidad: Mapped[str] = mapped_column(
        String(80), nullable=False, index=True
    )
    valor_limite: Mapped[int] = mapped_column(Integer, nullable=False)
    unidad_limite: Mapped[UnidadPlazo] = mapped_column(
        Enum(
            UnidadPlazo,
            name="unidadplazo",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    dias_limite: Mapped[int] = mapped_column(Integer, nullable=False)
    dias_alerta: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<EntidadPlazo {self.entidad_nombre!r} "
            f"{self.tipo_incapacidad!r} {self.dias_limite}d>"
        )
