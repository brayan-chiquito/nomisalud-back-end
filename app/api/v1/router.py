from fastapi import APIRouter

from app.api.v1.routes import (
    auth,
    colaboradores,
    conciliacion,
    demo,
    health,
    incapacidades,
    pagos,
    plazos_entidad,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(colaboradores.router)
api_router.include_router(incapacidades.router)
api_router.include_router(demo.router)
api_router.include_router(pagos.router)
api_router.include_router(conciliacion.router)
api_router.include_router(plazos_entidad.router)
