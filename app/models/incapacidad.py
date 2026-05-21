from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.alerta_enviada import AlertaEnviada
    from app.models.extraccion_ia import ExtraccionIA
    from app.models.historial_estado import HistorialEstado
    from app.models.inconsistencia import Inconsistencia
    from app.models.pago_incapacidad import PagoIncapacidad
    from app.models.user import User


class ArchivoTipo(str, enum.Enum):
    PDF = "pdf"
    JPG = "jpg"
    PNG = "png"


class IncapacidadEstado(str, enum.Enum):
    RECIBIDA = "recibida"
    PROCESANDO_IA = "procesando_ia"
    EN_VERIFICACION = "en_verificacion"
    DOC_INCOMPLETA = "doc_incompleta"
    TRANSCRITA = "transcrita"
    COBRADA = "cobrada"
    RECHAZADA = "rechazada"
    PAGADA = "pagada"
    INCONSISTENCIA_DETECTADA = "inconsistencia_detectada"


class Incapacidad(Base):
    __tablename__ = "incapacidades"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    radicado: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    colaborador_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        index=True,
    )
    cargado_por: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        index=True,
    )
    archivo_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True)
    archivo_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    archivo_tipo: Mapped[ArchivoTipo | None] = mapped_column(
        Enum(
            ArchivoTipo,
            name="archivotipo",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    archivo_tamano_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estado: Mapped[IncapacidadEstado] = mapped_column(
        Enum(
            IncapacidadEstado,
            name="incapacidadestado",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        index=True,
    )
    documentacion_faltante: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        nullable=True,
    )
    fecha_recepcion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
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

    colaborador: Mapped[User] = relationship(
        "User",
        foreign_keys=[colaborador_id],
        back_populates="incapacidades_como_colaborador",
    )
    cargado_por_usuario: Mapped[User] = relationship(
        "User",
        foreign_keys=[cargado_por],
        back_populates="incapacidades_cargadas",
    )
    extraccion_ia: Mapped[ExtraccionIA | None] = relationship(
        "ExtraccionIA",
        back_populates="incapacidad",
        uselist=False,
    )
    historial_estados: Mapped[list[HistorialEstado]] = relationship(
        "HistorialEstado",
        back_populates="incapacidad",
    )
    inconsistencias: Mapped[list[Inconsistencia]] = relationship(
        "Inconsistencia",
        back_populates="incapacidad",
        cascade="all, delete-orphan",
    )
    alertas_enviadas: Mapped[list[AlertaEnviada]] = relationship(
        "AlertaEnviada",
        back_populates="incapacidad",
        cascade="all, delete-orphan",
    )
    pagos_vinculos: Mapped[list[PagoIncapacidad]] = relationship(
        "PagoIncapacidad",
        back_populates="incapacidad",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        rid = self.radicado
        st = self.estado
        return f"<Incapacidad id={self.id} radicado={rid!r} estado={st}>"
