from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.incapacidad import Incapacidad
    from app.models.user import User


class CalidadDocumento(str, enum.Enum):
    BUENA = "buena"
    REGULAR = "regular"
    MALA = "mala"


class ExtraccionIA(Base):
    __tablename__ = "extraccion_ia"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    incapacidad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incapacidades.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    datos_extraidos: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    campos_corregidos: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    validaciones: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    api_usada: Mapped[str | None] = mapped_column(String(50), nullable=True)
    modelo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tokens_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    costo_usd: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    calidad_doc: Mapped[CalidadDocumento | None] = mapped_column(
        Enum(
            CalidadDocumento,
            name="calidaddocumento",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    verificado_por: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    verificado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    incapacidad: Mapped[Incapacidad] = relationship(
        "Incapacidad",
        back_populates="extraccion_ia",
    )
    verificador: Mapped[User | None] = relationship(
        "User",
        back_populates="extracciones_ia_verificadas",
        foreign_keys=[verificado_por],
    )

    def __repr__(self) -> str:
        return f"<ExtraccionIA id={self.id} incapacidad_id={self.incapacidad_id}>"
