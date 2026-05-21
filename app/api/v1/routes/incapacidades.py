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
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.extraccion_ia import ExtraccionIA
from app.models.historial_estado import HistorialEstado
from app.models.incapacidad import Incapacidad, IncapacidadEstado
from app.models.user import UserRole
from app.schemas.incapacidad import (
    ExtraccionIADetalleResponse,
    IncapacidadDetalleResponse,
    IncapacidadDocumentacionFaltanteRequest,
    IncapacidadDocumentacionFaltanteResponse,
    IncapacidadListItem,
    IncapacidadListResponse,
    IncapacidadPatchEstadoRequest,
    IncapacidadPatchEstadoResponse,
    IncapacidadUploadResponse,
    IncapacidadVerificarRequest,
    IncapacidadVerificarResponse,
    InconsistenciaDetalleResponse,
    MisIncapacidadItem,
    MisIncapacidadListResponse,
)
from app.schemas.token import TokenPayload
from app.services.datos_extraidos_ui import enrich_datos_extraidos_for_ui
from app.services.incapacidad_detail_service import (
    get_incapacidad_detalle,
    resolve_archivo_under_storage,
)
from app.services.incapacidad_documentacion_service import (
    IncapacidadDocumentacionError,
    registrar_documentacion_faltante,
)
from app.services.incapacidad_estado_service import (
    IncapacidadCambioEstadoError,
    aplicar_parche_estado_incapacidad,
)
from app.services.incapacidad_extraction_jobs import run_incapacidad_extraction_job
from app.services.incapacidad_list_service import (
    list_incapacidades_paginated,
    list_mis_incapacidades_paginated,
    total_pages,
)
from app.services.incapacidad_storage import IncapacidadStorageError
from app.services.incapacidad_upload_service import register_incapacidad_upload
from app.services.incapacidad_verify_service import (
    IncapacidadVerifyError,
    verify_incapacidad_manual,
)
from app.services.urgencia_service import parse_nivel_urgencia

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


def _ensure_puede_ver_incapacidad(actor: TokenPayload, colaborador_id: UUID) -> None:
    """Colaborador solo ve trámites propios; RRHH y admin ven todos."""
    if UserRole(actor.role) == UserRole.COLABORADOR:
        if UUID(actor.user_id) != colaborador_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permiso para ver esta incapacidad.",
            )


def _inconsistencias_to_schema(
    inc: Incapacidad,
) -> list[InconsistenciaDetalleResponse]:
    return [
        InconsistenciaDetalleResponse(
            id=item.id,
            tipo=item.tipo,
            descripcion=item.descripcion,
            created_at=item.created_at,
        )
        for item in sorted(inc.inconsistencias, key=lambda row: row.created_at)
    ]


def _extraccion_to_schema(ext: ExtraccionIA) -> ExtraccionIADetalleResponse:
    datos = enrich_datos_extraidos_for_ui(
        ext.datos_extraidos if isinstance(ext.datos_extraidos, dict) else {}
    )
    return ExtraccionIADetalleResponse(
        id=ext.id,
        incapacidad_id=ext.incapacidad_id,
        datos_extraidos=datos,
        campos_corregidos=ext.campos_corregidos,
        validaciones=ext.validaciones,
        raw_response=ext.raw_response,
        api_usada=ext.api_usada,
        modelo=ext.modelo,
        tokens_input=ext.tokens_input,
        tokens_output=ext.tokens_output,
        costo_usd=float(ext.costo_usd) if ext.costo_usd is not None else None,
        calidad_doc=ext.calidad_doc.value if ext.calidad_doc else None,
        verificado_por=ext.verificado_por,
        verificado_en=ext.verificado_en,
        created_at=ext.created_at,
    )


_ARCHIVO_MEDIA_TYPE = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
}


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


def _parse_urgencia_filtro(raw: str | None) -> str | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        return parse_nivel_urgencia(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Parámetro urgencia no es válido. Use: verde, amarillo o rojo.",
        ) from exc


@router.get(
    "",
    response_model=IncapacidadListResponse,
    summary="Listado paginado de incapacidades",
    description=(
        "Devuelve incapacidades con filtros opcionales (`estado`, `tipo`, `entidad`, "
        "`urgencia`) y paginación (`page`). El rol colaborador solo ve sus trámites; "
        "RRHH y admin ven el universo completo."
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
    urgencia: str | None = Query(
        None,
        description="Filtrar por nivel de urgencia calculado: verde, amarillo o rojo",
    ),
    pago_retrasado: bool | None = Query(
        None,
        description="Si es true, solo trámites marcados con pago retrasado (SCRUM-193)",
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
    urgencia_filtro = _parse_urgencia_filtro(urgencia)
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
        urgencia_filtro=urgencia_filtro,
        pago_retrasado=pago_retrasado,
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
            urgencia=r.urgencia,
            pago_retrasado=r.pago_retrasado,
        )
        for r in rows
    ]
    return IncapacidadListResponse(
        items=items,
        total=total,
        pages=total_pages(total, page_size),
    )


@router.get(
    "/mias",
    response_model=MisIncapacidadListResponse,
    summary="Mis incapacidades",
    description=(
        "Listado paginado de trámites donde el usuario autenticado es el titular "
        "(`colaborador_id` del JWT). Cada ítem incluye el estado actual y "
        "`updated_at` (última modificación)."
    ),
)
async def list_mis_incapacidades(
    page: int = Query(1, ge=1, description="Número de página (base 1)"),
    current_user: TokenPayload = Depends(require_roles(UserRole.COLABORADOR)),
    db: AsyncSession = Depends(get_db),
) -> MisIncapacidadListResponse:
    user_id = UUID(current_user.user_id)
    settings = get_settings()
    page_size = settings.INCAPACIDADES_PAGE_SIZE
    rows, total = await list_mis_incapacidades_paginated(
        db,
        colaborador_id=user_id,
        page=page,
        page_size=page_size,
    )
    items = [
        MisIncapacidadItem(
            id=inc.id,
            radicado=inc.radicado,
            estado=inc.estado.value,
            updated_at=inc.updated_at,
        )
        for inc in rows
    ]
    return MisIncapacidadListResponse(
        items=items,
        total=total,
        pages=total_pages(total, page_size),
    )


@router.get(
    "/{incapacidad_id}",
    response_model=IncapacidadDetalleResponse,
    summary="Detalle de incapacidad",
    description=(
        "Devuelve el trámite, la extracción IA asociada (si existe) y la URL para "
        "descargar el documento. Mismas reglas de acceso que el listado."
    ),
)
async def get_incapacidad_por_id(
    incapacidad_id: UUID,
    request: Request,
    current_user: TokenPayload = Depends(
        require_roles(
            UserRole.COLABORADOR,
            UserRole.AUXILIAR_RRHH,
            UserRole.COORDINADOR_RRHH,
            UserRole.ADMIN,
        )
    ),
    db: AsyncSession = Depends(get_db),
) -> IncapacidadDetalleResponse:
    bundle = await get_incapacidad_detalle(db, incapacidad_id)
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incapacidad no encontrada.",
        )
    inc = bundle.incapacidad
    _ensure_puede_ver_incapacidad(current_user, inc.colaborador_id)

    archivo_url: str | None = None
    if inc.archivo_path and inc.archivo_path.strip():
        archivo_url = str(
            request.url_for(
                "download_incapacidad_archivo",
                incapacidad_id=str(inc.id),
            )
        )

    ext_schema = (
        _extraccion_to_schema(bundle.extraccion_ia)
        if bundle.extraccion_ia is not None
        else None
    )

    return IncapacidadDetalleResponse(
        id=inc.id,
        radicado=inc.radicado,
        estado=inc.estado.value,
        colaborador_id=inc.colaborador_id,
        colaborador_nombre=bundle.colaborador_nombre,
        colaborador_email=bundle.colaborador_email,
        cargado_por=inc.cargado_por,
        user_id=inc.user_id,
        archivo_uuid=inc.archivo_uuid,
        archivo_tipo=inc.archivo_tipo.value if inc.archivo_tipo else None,
        archivo_tamano_bytes=inc.archivo_tamano_bytes,
        documentacion_faltante=inc.documentacion_faltante,
        fecha_recepcion=inc.fecha_recepcion,
        created_at=inc.created_at,
        updated_at=inc.updated_at,
        extraccion_ia=ext_schema,
        inconsistencias=_inconsistencias_to_schema(inc),
        archivo_url=archivo_url,
    )


@router.get(
    "/{incapacidad_id}/archivo",
    name="download_incapacidad_archivo",
    summary="Descargar documento adjunto",
    description="Sirve el archivo almacenado; requiere el mismo JWT que el detalle.",
    response_class=FileResponse,
)
async def download_incapacidad_archivo(
    incapacidad_id: UUID,
    current_user: TokenPayload = Depends(
        require_roles(
            UserRole.COLABORADOR,
            UserRole.AUXILIAR_RRHH,
            UserRole.COORDINADOR_RRHH,
            UserRole.ADMIN,
        )
    ),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    bundle = await get_incapacidad_detalle(db, incapacidad_id)
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incapacidad no encontrada.",
        )
    inc = bundle.incapacidad
    _ensure_puede_ver_incapacidad(current_user, inc.colaborador_id)

    settings = get_settings()
    storage = Path(settings.UPLOAD_STORAGE_DIR)
    path = resolve_archivo_under_storage(inc.archivo_path, storage)
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivo no disponible.",
        )

    if inc.archivo_tipo:
        ext = inc.archivo_tipo.value
    else:
        ext = path.suffix.lower().lstrip(".")
    media = _ARCHIVO_MEDIA_TYPE.get(ext, "application/octet-stream")
    filename = f"{inc.radicado}.{ext}"
    return FileResponse(
        path,
        media_type=media,
        filename=filename,
    )


@router.put(
    "/{incapacidad_id}/verificar",
    response_model=IncapacidadVerificarResponse,
    summary="Verificar datos extraídos (RRHH / admin)",
    description=(
        "Registra la revisión humana sobre la extracción IA: `confirmar` deja el "
        "trámite en `en_verificacion` (y opcionalmente actualiza `datos_extraidos`); "
        "`rechazar` pasa a `rechazada` y guarda `motivo_rechazo` en "
        "`documentacion_faltante`."
    ),
)
async def verificar_incapacidad_extraccion(
    incapacidad_id: UUID,
    body: IncapacidadVerificarRequest,
    current_user: TokenPayload = Depends(
        require_roles(
            UserRole.AUXILIAR_RRHH,
            UserRole.COORDINADOR_RRHH,
            UserRole.ADMIN,
        )
    ),
    db: AsyncSession = Depends(get_db),
) -> IncapacidadVerificarResponse:
    try:
        inc = await verify_incapacidad_manual(
            db,
            incapacidad_id=incapacidad_id,
            actor_id=UUID(current_user.user_id),
            accion=body.accion.value,
            motivo_rechazo=body.motivo_rechazo,
            datos_extraidos=body.datos_extraidos,
        )
    except IncapacidadVerifyError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
        ) from exc
    return IncapacidadVerificarResponse(
        id=inc.id,
        radicado=inc.radicado,
        estado=inc.estado.value,
    )


@router.patch(
    "/{incapacidad_id}/estado",
    response_model=IncapacidadPatchEstadoResponse,
    summary="Cambiar estado del trámite (RRHH / admin)",
    description=(
        "Aplica una transición válida en la máquina de estados y registra "
        "`historial_estados` con estado anterior, nuevo, usuario y marca de tiempo."
    ),
)
async def patch_incapacidad_estado(
    incapacidad_id: UUID,
    body: IncapacidadPatchEstadoRequest,
    current_user: TokenPayload = Depends(
        require_roles(
            UserRole.AUXILIAR_RRHH,
            UserRole.COORDINADOR_RRHH,
            UserRole.ADMIN,
        )
    ),
    db: AsyncSession = Depends(get_db),
) -> IncapacidadPatchEstadoResponse:
    try:
        inc, estado_anterior = await aplicar_parche_estado_incapacidad(
            db,
            incapacidad_id=incapacidad_id,
            actor_id=UUID(current_user.user_id),
            nuevo_estado=body.estado,
            observacion=body.observacion,
        )
    except IncapacidadCambioEstadoError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
        ) from exc
    return IncapacidadPatchEstadoResponse(
        id=inc.id,
        radicado=inc.radicado,
        estado=inc.estado.value,
        estado_anterior=estado_anterior.value,
    )


@router.put(
    "/{incapacidad_id}/documentacion-faltante",
    response_model=IncapacidadDocumentacionFaltanteResponse,
    summary="Registrar documentación faltante (RRHH / admin)",
    description=(
        "Persiste la lista de documentos pendientes en `documentacion_faltante` "
        "y deja el trámite en `doc_incompleta` (desde `en_verificacion`). "
        "Si ya está en `doc_incompleta`, solo actualiza la lista."
    ),
)
async def registrar_documentacion_faltante_incapacidad(
    incapacidad_id: UUID,
    body: IncapacidadDocumentacionFaltanteRequest,
    current_user: TokenPayload = Depends(
        require_roles(
            UserRole.AUXILIAR_RRHH,
            UserRole.COORDINADOR_RRHH,
            UserRole.ADMIN,
        )
    ),
    db: AsyncSession = Depends(get_db),
) -> IncapacidadDocumentacionFaltanteResponse:
    try:
        inc, estado_anterior = await registrar_documentacion_faltante(
            db,
            incapacidad_id=incapacidad_id,
            actor_id=UUID(current_user.user_id),
            documentos=body.documentos,
            observacion=body.observacion,
        )
    except IncapacidadDocumentacionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
        ) from exc
    docs = inc.documentacion_faltante or []
    return IncapacidadDocumentacionFaltanteResponse(
        id=inc.id,
        radicado=inc.radicado,
        estado=inc.estado.value,
        estado_anterior=estado_anterior.value,
        documentacion_faltante=docs,
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
