import uuid
from datetime import datetime

from pydantic import BaseModel, Field


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
