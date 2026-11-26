from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.pagination import Order
from app.core.responses import error_responses
from app.core.schemas import Cursor, PageResponse, SearchTerm
from app.modules.auth.public import require_permission
from app.modules.employees.dependencies import EmployeeServiceDep
from app.modules.employees.schemas import (
    Email,
    EmployeeCreate,
    EmployeeDetail,
    EmployeeResponse,
    EmployeeTreeNode,
    EmployeeUpdate,
)

router = APIRouter(prefix="/employees", tags=["employees"])

can_read = Depends(require_permission("employees:read"))
can_write = Depends(require_permission("employees:write"))


# response_model filtra y valida la salida: aunque el ORM tenga más campos, al cliente
# solo llegan los declarados en el contrato.
@router.get(
    "",
    response_model=PageResponse[EmployeeResponse],
    dependencies=[can_read],
    responses=error_responses(),
)
async def list_employees(
    service: EmployeeServiceDep,
    # Los parámetros simples que no están en la ruta se leen del query string.
    # Omitir is_active devuelve activos e inactivos.
    is_active: bool | None = None,
    email: Email | None = None,  # coincidencia exacta
    q: SearchTerm | None = None,  # coincidencia parcial en nombre, apellido y email
    department_id: UUID | None = None,
    manager_id: UUID | None = None,
    has_manager: bool | None = None,  # false: las raíces del organigrama
    job_title_id: UUID | None = None,  # puesto actual
    sort: Literal["last_name", "first_name", "hire_date", "created_at"] = "last_name",
    order: Order = "asc",
    after: Cursor | None = None,  # el next_cursor de la página anterior
):
    return await service.list_page(
        is_active=is_active,
        email=email,
        q=q,
        department_id=department_id,
        manager_id=manager_id,
        has_manager=has_manager,
        job_title_id=job_title_id,
        sort=sort,
        order=order,
        after=after,
    )


@router.get(
    "/{employee_id}",
    response_model=EmployeeDetail,
    dependencies=[can_read],
    responses=error_responses(404),
)
async def get_employee(employee_id: UUID, service: EmployeeServiceDep):
    return await service.get_detail(employee_id)


@router.post(
    "",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[can_write],
    responses=error_responses(404, 409),
)
async def create_employee(body: EmployeeCreate, service: EmployeeServiceDep):
    return await service.create(**body.model_dump())


@router.patch(
    "/{employee_id}",
    response_model=EmployeeResponse,
    dependencies=[can_write],
    responses=error_responses(404, 409),
)
async def update_employee(employee_id: UUID, body: EmployeeUpdate, service: EmployeeServiceDep):
    return await service.update(employee_id, body.model_dump(exclude_unset=True))


@router.delete(
    "/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[can_write],
    responses=error_responses(404),
)
async def deactivate_employee(employee_id: UUID, service: EmployeeServiceDep) -> None:
    await service.deactivate(employee_id)


@router.get(
    "/{employee_id}/reports",
    response_model=list[EmployeeResponse],
    dependencies=[can_read],
    responses=error_responses(404),
)
async def list_direct_reports(employee_id: UUID, service: EmployeeServiceDep):
    return await service.list_reports(employee_id)


@router.get(
    "/{employee_id}/tree",
    response_model=EmployeeTreeNode,
    dependencies=[can_read],
    responses=error_responses(404),
)
async def get_employee_tree(employee_id: UUID, service: EmployeeServiceDep):
    return await service.get_tree(employee_id)
