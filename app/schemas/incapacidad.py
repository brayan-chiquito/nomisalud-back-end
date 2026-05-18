import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.incapacidad import IncapacidadEstado


class IncapacidadUploadResponse(BaseModel):
    """Solo radicado y estado del trámite tras registrar la carga."""

    radicado: str = Field(..., max_length=20, description="Número de radicado único")
    estado: str = Field(..., description="Estado persistido del trámite")


class IncapacidadListItem(BaseModel):
    """Resumen de un trámite para listados."""

    id: uuid.UUID
    radicado: str
    estado: str
    colaborador_id: uuid.UUID
    colaborador_nombre: str | None = Field(
        None,
        description=(
            "Nombre en perfil (`users.nombre_completo`); null si no está cargado"
        ),
    )
    colaborador_email: str | None = Field(
        None,
        description="Email del usuario colaborador (`users.email`)",
    )
    archivo_tipo: str | None
    fecha_recepcion: datetime
    entidad_nombre: str | None = Field(
        None,
        description="Extracción IA: `datos_extraidos.entidad.nombre`",
    )
    entidad_tipo: str | None = Field(
        None,
        description=(
            "Extracción IA: `datos_extraidos.entidad.tipo` "
            "(EPS, ARL, IPS, medico_particular, hospital_publico)"
        ),
    )
    entidad_nit: str | None = Field(
        None,
        description="Extracción IA: `datos_extraidos.entidad.nit`",
    )
    entidad_ciudad: str | None = Field(
        None,
        description="Extracción IA: `datos_extraidos.entidad.ciudad`",
    )
    incapacidad_tipo_extraido: str | None = Field(
        None,
        description=(
            "Extracción IA: `datos_extraidos.incapacidad.tipo` "
            "(clasificación en documento; distinto de archivo_tipo)"
        ),
    )


class IncapacidadListResponse(BaseModel):
    items: list[IncapacidadListItem]
    total: int = Field(..., ge=0)
    pages: int = Field(..., ge=0)


class MisIncapacidadItem(BaseModel):
    """Resumen de un trámite propio del colaborador autenticado (SCRUM-141)."""

    id: uuid.UUID
    radicado: str
    estado: str = Field(..., description="Estado actual del trámite")
    updated_at: datetime = Field(
        ...,
        description="Fecha y hora de la última modificación del registro",
    )


class MisIncapacidadListResponse(BaseModel):
    items: list[MisIncapacidadItem]
    total: int = Field(..., ge=0)
    pages: int = Field(..., ge=0)


class ExtraccionIADetalleResponse(BaseModel):
    """Campos persistidos de la extracción IA (tabla `extraccion_ia`)."""

    id: uuid.UUID
    incapacidad_id: uuid.UUID
    datos_extraidos: dict[str, Any]
    campos_corregidos: dict[str, Any] | None
    validaciones: dict[str, Any] | None
    raw_response: str | None
    api_usada: str | None
    modelo: str | None
    tokens_input: int | None
    tokens_output: int | None
    costo_usd: float | None
    calidad_doc: str | None
    verificado_por: uuid.UUID | None
    verificado_en: datetime | None
    created_at: datetime


class IncapacidadDetalleResponse(BaseModel):
    """Detalle del trámite: registro principal, extracción IA y URL del adjunto."""

    id: uuid.UUID
    radicado: str
    estado: str
    colaborador_id: uuid.UUID
    colaborador_nombre: str | None = None
    colaborador_email: str | None = None
    cargado_por: uuid.UUID
    user_id: uuid.UUID
    archivo_uuid: str | None
    archivo_tipo: str | None
    archivo_tamano_bytes: int | None
    documentacion_faltante: list[str] | None
    fecha_recepcion: datetime
    created_at: datetime
    updated_at: datetime
    extraccion_ia: ExtraccionIADetalleResponse | None
    archivo_url: str | None = Field(
        None,
        description=(
            "URL absoluta para descargar el documento "
            "(GET mismo host, requiere el mismo JWT)"
        ),
    )


class IncapacidadVerificarAccion(str, enum.Enum):
    CONFIRMAR = "confirmar"
    RECHAZAR = "rechazar"


class IncapacidadVerificarRequest(BaseModel):
    """Cuerpo para revisión humana de la extracción IA."""

    accion: IncapacidadVerificarAccion
    motivo_rechazo: str | None = Field(
        None,
        description="Obligatorio si accion=rechazar; texto persistente del motivo",
    )
    datos_extraidos: dict[str, Any] | None = Field(
        None,
        description=(
            "Si se envía con confirmar, reemplaza por completo `datos_extraidos` "
            "en la fila `extraccion_ia`"
        ),
    )

    @model_validator(mode="after")
    def _motivo_si_rechazo(self):
        if self.accion == IncapacidadVerificarAccion.RECHAZAR:
            if self.motivo_rechazo is None or not str(self.motivo_rechazo).strip():
                raise ValueError("motivo_rechazo es obligatorio al rechazar.")
        return self


class IncapacidadVerificarResponse(BaseModel):
    id: uuid.UUID
    radicado: str
    estado: str


class IncapacidadPatchEstadoRequest(BaseModel):
    """Cuerpo para cambiar estado del trámite (transiciones validadas en servidor)."""

    estado: IncapacidadEstado
    observacion: str | None = Field(
        None,
        max_length=4000,
        description="Motivo u observación de auditoría (opcional)",
    )


class IncapacidadPatchEstadoResponse(BaseModel):
    id: uuid.UUID
    radicado: str
    estado: str
    estado_anterior: str
