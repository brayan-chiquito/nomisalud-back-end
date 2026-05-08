from pydantic import BaseModel, Field


class IncapacidadUploadResponse(BaseModel):
    """Solo radicado y estado del trámite tras registrar la carga."""

    radicado: str = Field(..., max_length=20, description="Número de radicado único")
    estado: str = Field(..., description="Estado persistido del trámite")
