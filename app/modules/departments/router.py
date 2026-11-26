from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.pagination import Order
from app.core.responses import error_responses
from app.core.schemas import Cursor, PageResponse, SearchTerm
from app.modules.auth.public import require_permission
from app.modules.departments.dependencies import DepartmentServiceDep
from app.modules.departments.schemas import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
)

router = APIRouter(prefix="/departments", tags=["departments"])

can_read = Depends(require_permission("employees:read"))
can_write = Depends(require_permission("departments:write"))


@router.get(
    "",
    response_model=PageResponse[DepartmentResponse],
    dependencies=[can_read],
    responses=error_responses(),
)
async def list_departments(
    service: DepartmentServiceDep,
    q: SearchTerm | None = None,  # coincidencia parcial en el nombre
    sort: Literal["name", "created_at"] = "name",
    order: Order = "asc",
    after: Cursor | None = None,  # el next_cursor de la página anterior
):
    return await service.list_page(q=q, sort=sort, order=order, after=after)


@router.get(
    "/{department_id}",
    response_model=DepartmentResponse,
    dependencies=[can_read],
    responses=error_responses(404),
)
async def get_department(department_id: UUID, service: DepartmentServiceDep):
    return await service.get_detail(department_id)


@router.post(
    "",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[can_write],
    responses=error_responses(404, 409),
)
async def create_department(body: DepartmentCreate, service: DepartmentServiceDep):
    return await service.create(**body.model_dump())


@router.patch(
    "/{department_id}",
    response_model=DepartmentResponse,
    dependencies=[can_write],
    responses=error_responses(404, 409),
)
async def update_department(
    department_id: UUID, body: DepartmentUpdate, service: DepartmentServiceDep
):
    return await service.update(department_id, body.model_dump(exclude_unset=True))
