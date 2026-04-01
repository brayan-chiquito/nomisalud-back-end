from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/", summary="Health check básico")
async def health_check():
    return {
        "status": "ok",
        "message": "Hola Mundo desde NomiSalud API",
    }


@router.get("/db", summary="Health check de base de datos")
async def health_check_db(db: AsyncSession = Depends(get_db)):
    """Verifica que la conexión a la base de datos está activa."""
    result = await db.execute(text("SELECT 1"))
    result.scalar()
    return {
        "status": "ok",
        "database": "conectada",
    }
