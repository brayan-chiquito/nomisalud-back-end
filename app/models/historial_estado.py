from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.incapacidad import IncapacidadEstado

if TYPE_CHECKING:
    from app.models.incapacidad import Incapacidad
    from app.models.user import User

_INCAPACIDAD_ESTADO_ENUM = Enum(
    IncapacidadEstado,
    name="incapacidadestado",
    create_type=False,
    values_callable=lambda x: [e.value for e in x],
)


class HistorialEstado(Base):
    __tablename__ = "historial_estados"

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
    estado_anterior: Mapped[IncapacidadEstado | None] = mapped_column(
        _INCAPACIDAD_ESTADO_ENUM,
        nullable=True,
    )
    estado_nuevo: Mapped[IncapacidadEstado] = mapped_column(
        _INCAPACIDAD_ESTADO_ENUM,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        index=True,
    )
    observacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    incapacidad: Mapped[Incapacidad] = relationship(
        "Incapacidad",
        back_populates="historial_estados",
    )
    usuario: Mapped[User] = relationship(
        "User",
        back_populates="historial_estados",
    )

    def __repr__(self) -> str:
        return f"<HistorialEstado id={self.id} incapacidad_id={self.incapacidad_id}>"
