"""Rutas HTTP para trámites de incapacidad."""

from pathlib import Path
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.historial_estado import HistorialEstado
from app.models.incapacidad import IncapacidadEstado
from app.models.user import UserRole
from app.schemas.incapacidad import (
    IncapacidadListItem,
    IncapacidadListResponse,
    IncapacidadUploadResponse,
)
from app.schemas.token import TokenPayload
from app.services.incapacidad_extraction_jobs import run_incapacidad_extraction_job
from app.services.incapacidad_list_service import (
    list_incapacidades_paginated,
    total_pages,
)
from app.services.incapacidad_storage import IncapacidadStorageError
from app.services.incapacidad_upload_service import register_incapacidad_upload

router = APIRouter(prefix="/incapacidades", tags=["Incapacidades"])


def _ensure_puede_cargar_para_colaborador(
    actor: TokenPayload,
    colaborador_id: UUID,
) -> None:
    """Colaborador solo para sí mismo; RRHH y admin pueden cargar para otros."""
    actor_id = UUID(actor.user_id)
    if colaborador_id == actor_id:
        return
    role = UserRole(actor.role)
    if role in (
        UserRole.AUXILIAR_RRHH,
        UserRole.COORDINADOR_RRHH,
        UserRole.ADMIN,
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No puede cargar incapacidades para otro colaborador.",
    )


def _parse_estado_filtro(raw: str | None) -> IncapacidadEstado | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        return IncapacidadEstado(raw.strip().lower())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Parámetro estado no es un valor válido.",
        ) from exc


@router.get(
    "",
    response_model=IncapacidadListResponse,
    summary="Listado paginado de incapacidades",
    description=(
        "Devuelve incapacidades con filtros opcionales (`estado`, `tipo`, `entidad`) "
        "y paginación (`page`). El rol colaborador solo ve sus trámites; RRHH y admin "
        "ven el universo completo."
    ),
)
async def list_incapacidades(
    page: int = Query(1, ge=1, description="Número de página (base 1)"),
    estado: str | None = Query(None, description="Filtrar por estado del trámite"),
    tipo: str | None = Query(
        None,
        description=(
            "Tipo de archivo (pdf, jpg, png) o tipo de incapacidad en datos extraídos"
        ),
    ),
    entidad: str | None = Query(
        None, description="Subcadena del nombre de entidad (datos extraídos)"
    ),
    current_user: TokenPayload = Depends(
        require_roles(
            UserRole.COLABORADOR,
            UserRole.AUXILIAR_RRHH,
            UserRole.COORDINADOR_RRHH,
            UserRole.ADMIN,
        )
    ),
    db: AsyncSession = Depends(get_db),
) -> IncapacidadListResponse:
    estado_enum = _parse_estado_filtro(estado)
    colaborador_id_scope: UUID | None = None
    if UserRole(current_user.role) == UserRole.COLABORADOR:
        colaborador_id_scope = UUID(current_user.user_id)

    settings = get_settings()
    page_size = settings.INCAPACIDADES_PAGE_SIZE
    rows, total = await list_incapacidades_paginated(
        db,
        page=page,
        page_size=page_size,
        estado=estado_enum,
        tipo=tipo,
        entidad=entidad,
        colaborador_id_scope=colaborador_id_scope,
    )
    items = [
        IncapacidadListItem(
            id=r.incapacidad.id,
            radicado=r.incapacidad.radicado,
            estado=r.incapacidad.estado.value,
            colaborador_id=r.incapacidad.colaborador_id,
            colaborador_nombre=r.colaborador_nombre,
            colaborador_email=r.colaborador_email,
            archivo_tipo=r.incapacidad.archivo_tipo.value
            if r.incapacidad.archivo_tipo
            else None,
            fecha_recepcion=r.incapacidad.fecha_recepcion,
            entidad_nombre=r.entidad_nombre,
            entidad_tipo=r.entidad_tipo,
            entidad_nit=r.entidad_nit,
            entidad_ciudad=r.entidad_ciudad,
            incapacidad_tipo_extraido=r.incapacidad_tipo_extraido,
        )
        for r in rows
    ]
    return IncapacidadListResponse(
        items=items,
        total=total,
        pages=total_pages(total, page_size),
    )


@router.post(
    "/upload",
    response_model=IncapacidadUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Carga de documento de incapacidad (multipart)",
    description=(
        "Recibe un archivo (PDF, JPG o PNG), lo guarda en disco y crea el registro "
        "en `incapacidades`. La respuesta es inmediata con el radicado; el estado "
        "pasa a `procesando_ia` y la extracción con Gemini se ejecuta en segundo plano."
        " Opcionalmente `colaborador_id` indica el titular del trámite; "
        "si se omite, se asume el usuario autenticado."
    ),
)
async def upload_incapacidad_documento(
    background_tasks: BackgroundTasks,
    archivo: UploadFile = File(..., description="Archivo PDF, JPG/JPEG o PNG"),
    colaborador_id: str | None = Form(
        None,
        description="UUID del colaborador titular; por defecto, el usuario del token",
    ),
    current_user: TokenPayload = Depends(
        require_roles(
            UserRole.COLABORADOR,
            UserRole.AUXILIAR_RRHH,
            UserRole.COORDINADOR_RRHH,
            UserRole.ADMIN,
        )
    ),
    db: AsyncSession = Depends(get_db),
) -> IncapacidadUploadResponse:
    if colaborador_id is None or colaborador_id.strip() == "":
        colaborador_uuid = UUID(current_user.user_id)
    else:
        try:
            colaborador_uuid = UUID(colaborador_id.strip())
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="colaborador_id debe ser un UUID válido.",
            ) from exc

    _ensure_puede_cargar_para_colaborador(current_user, colaborador_uuid)

    settings = get_settings()
    cargado_por_uuid = UUID(current_user.user_id)

    try:
        row = await register_incapacidad_upload(
            db,
            upload=archivo,
            colaborador_id=colaborador_uuid,
            cargado_por_id=cargado_por_uuid,
            storage_dir=Path(settings.UPLOAD_STORAGE_DIR),
            max_upload_bytes=settings.MAX_UPLOAD_BYTES,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except IncapacidadStorageError as exc:
        msg = str(exc)
        if "supera el tamaño máximo" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=msg,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo escribir el archivo en el almacenamiento.",
        ) from exc

    prev_estado = row.estado
    row.estado = IncapacidadEstado.PROCESANDO_IA
    db.add(
        HistorialEstado(
            incapacidad_id=row.id,
            estado_anterior=prev_estado,
            estado_nuevo=IncapacidadEstado.PROCESANDO_IA,
            user_id=cargado_por_uuid,
            observacion="Documento recibido; extracción IA en cola.",
        )
    )
    if row.archivo_path:
        background_tasks.add_task(
            run_incapacidad_extraction_job,
            row.id,
            row.archivo_path,
            cargado_por_uuid,
        )

    return IncapacidadUploadResponse(
        radicado=row.radicado,
        estado=row.estado.value,
    )
