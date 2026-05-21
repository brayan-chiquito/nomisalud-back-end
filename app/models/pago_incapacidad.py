"""Tabla pivote pagos ↔ incapacidades (SCRUM-184)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.incapacidad import Incapacidad
    from app.models.pago import Pago


class PagoIncapacidad(Base):
    __tablename__ = "pagos_incapacidades"

    pago_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pagos.id", ondelete="CASCADE"),
        primary_key=True,
    )
    incapacidad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incapacidades.id", ondelete="CASCADE"),
        primary_key=True,
    )

    pago: Mapped[Pago] = relationship("Pago", back_populates="incapacidades_vinculos")
    incapacidad: Mapped[Incapacidad] = relationship(
        "Incapacidad",
        back_populates="pagos_vinculos",
    )
