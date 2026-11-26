from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.pagination import Order
from app.core.responses import error_responses
from app.core.schemas import SearchTerm
from app.modules.auth.public import require_permission
from app.modules.job_titles.dependencies import JobTitleServiceDep
from app.modules.job_titles.schemas import JobTitleCreate, JobTitleResponse, JobTitleUpdate

# prefix antepone la ruta a todos los endpoints; tags los agrupa en Swagger UI.
router = APIRouter(prefix="/job-titles", tags=["job titles"])

# Se usan en dependencies=[...] porque solo importa el efecto (validar), no el valor devuelto.
can_read = Depends(require_permission("employees:read"))
can_write = Depends(require_permission("job-titles:write"))


@router.get(
    "",
    response_model=list[JobTitleResponse],
    dependencies=[can_read],
    responses=error_responses(),
)
async def list_job_titles(
    service: JobTitleServiceDep,
    is_active: bool | None = None,  # omitirlo devuelve activos e inactivos
    q: SearchTerm | None = None,  # coincidencia parcial en el nombre
    sort: Literal["name"] = "name",
    order: Order = "asc",
):
    return await service.list_all(is_active=is_active, q=q, order=order)


@router.get(
    "/{job_title_id}",
    response_model=JobTitleResponse,
    dependencies=[can_read],
    responses=error_responses(404),
)
async def get_job_title(job_title_id: UUID, service: JobTitleServiceDep):
    return await service.get(job_title_id)


@router.post(
    "",
    response_model=JobTitleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[can_write],
    responses=error_responses(409),
)
async def create_job_title(body: JobTitleCreate, service: JobTitleServiceDep):
    # El servicio recibe datos simples, no el schema: no depende del contrato HTTP.
    return await service.create(**body.model_dump())


@router.patch(
    "/{job_title_id}",
    response_model=JobTitleResponse,
    dependencies=[can_write],
    responses=error_responses(404, 409),
)
async def update_job_title(job_title_id: UUID, body: JobTitleUpdate, service: JobTitleServiceDep):
    # exclude_unset: solo los campos que el cliente envió de verdad.
    return await service.update(job_title_id, body.model_dump(exclude_unset=True))
