from fastapi import APIRouter

from app.modules.departments.router import router as departments_router
from app.modules.employees.router import router as employees_router
from app.modules.job_titles.router import router as job_titles_router
from app.modules.positions.router import router as positions_router

# El prefijo de versión permite publicar un /api/v2 sin romper a los clientes actuales.
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(employees_router)
api_router.include_router(positions_router)
api_router.include_router(departments_router)
api_router.include_router(job_titles_router)
