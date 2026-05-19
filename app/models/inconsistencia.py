"""Registro de inconsistencias detectadas en un trámite (SCRUM-170)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.incapacidad import Incapacidad


class Inconsistencia(Base):
    __tablename__ = "inconsistencias"

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
    tipo: Mapped[str] = mapped_column(String(80), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    incapacidad: Mapped[Incapacidad] = relationship(
        "Incapacidad",
        back_populates="inconsistencias",
    )

    def __repr__(self) -> str:
        return (
            f"<Inconsistencia id={self.id} incapacidad_id={self.incapacidad_id} "
            f"tipo={self.tipo!r}>"
        )
