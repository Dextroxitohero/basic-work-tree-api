from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.responses import error_responses
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
    response_model=list[EmployeeResponse],
    dependencies=[can_read],
    responses=error_responses(),
)
async def list_employees(
    service: EmployeeServiceDep, is_active: bool = True, email: Email | None = None
):
    # Los parámetros simples que no están en la ruta se leen del query string.
    return await service.list_all(is_active=is_active, email=email)


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
