"""Historial de alertas de vencimiento enviadas (SCRUM-182)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.incapacidad import Incapacidad


class TipoAlerta(str, enum.Enum):
    """Categoría de alerta para control de duplicados."""

    VENCIMIENTO_AMARILLO = "vencimiento_amarillo"
    VENCIMIENTO_ROJO = "vencimiento_rojo"


class AlertaEnviada(Base):
    """Registro de notificación emitida para un trámite."""

    __tablename__ = "alertas_enviadas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    incapacidad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incapacidades.id", ondelete="CASCADE"),
        index=True,
    )
    tipo_alerta: Mapped[TipoAlerta] = mapped_column(
        Enum(
            TipoAlerta,
            name="tipoalerta",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        index=True,
    )
    enviada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    incapacidad: Mapped[Incapacidad] = relationship(
        "Incapacidad",
        back_populates="alertas_enviadas",
    )

    def __repr__(self) -> str:
        return (
            f"<AlertaEnviada id={self.id} incapacidad_id={self.incapacidad_id} "
            f"tipo={self.tipo_alerta!r}>"
        )
