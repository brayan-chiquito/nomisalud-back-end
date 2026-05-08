from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.extraccion_ia import ExtraccionIA
    from app.models.historial_estado import HistorialEstado
    from app.models.incapacidad import Incapacidad


class UserRole(str, enum.Enum):
    COLABORADOR = "colaborador"
    AUXILIAR_RRHH = "auxiliar_rrhh"
    COORDINADOR_RRHH = "coordinador_rrhh"
    ADMIN = "admin"


class TipoDocumento(str, enum.Enum):
    CC = "CC"
    CE = "CE"
    TI = "TI"
    PA = "PA"
    RC = "RC"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="userrole",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
    )
    nombre_completo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tipo_documento: Mapped[TipoDocumento | None] = mapped_column(
        Enum(
            TipoDocumento,
            name="tipodocumento",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    numero_documento: Mapped[str | None] = mapped_column(String(20), nullable=True)
    area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cargo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    eps_afiliacion: Mapped[str | None] = mapped_column(String(100), nullable=True)
    arl_afiliacion: Mapped[str | None] = mapped_column(String(100), nullable=True)
    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    incapacidades_como_colaborador: Mapped[list[Incapacidad]] = relationship(
        "Incapacidad",
        foreign_keys="[Incapacidad.colaborador_id]",
        back_populates="colaborador",
    )
    incapacidades_cargadas: Mapped[list[Incapacidad]] = relationship(
        "Incapacidad",
        foreign_keys="[Incapacidad.cargado_por]",
        back_populates="cargado_por_usuario",
    )
    extracciones_ia_verificadas: Mapped[list[ExtraccionIA]] = relationship(
        "ExtraccionIA",
        foreign_keys="[ExtraccionIA.verificado_por]",
        back_populates="verificador",
    )
    historial_estados: Mapped[list[HistorialEstado]] = relationship(
        "HistorialEstado",
        back_populates="usuario",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role!r}>"
