"""Registro de pagos y vínculo con incapacidades (SCRUM-184)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.pago_incapacidad import PagoIncapacidad
    from app.models.user import User


class PagoEstado(str, enum.Enum):
    """Estado operativo del pago (filtros y reportes)."""

    REGISTRADO = "registrado"
    ANULADO = "anulado"


class Pago(Base):
    __tablename__ = "pagos"
    __table_args__ = (
        UniqueConstraint(
            "entidad_origen",
            "referencia",
            name="uq_pagos_entidad_origen_referencia",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    entidad_origen: Mapped[str] = mapped_column(String(120), index=True)
    referencia: Mapped[str] = mapped_column(String(120), index=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    fecha_operacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        index=True,
    )
    estado: Mapped[PagoEstado] = mapped_column(
        Enum(
            PagoEstado,
            name="pagoestado",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=PagoEstado.REGISTRADO,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    usuario: Mapped[User] = relationship("User", back_populates="pagos")
    incapacidades_vinculos: Mapped[list[PagoIncapacidad]] = relationship(
        "PagoIncapacidad",
        back_populates="pago",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Pago id={self.id} ref={self.referencia!r} "
            f"entidad={self.entidad_origen!r}>"
        )
