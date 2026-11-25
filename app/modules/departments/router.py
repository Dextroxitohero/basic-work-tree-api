from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.responses import error_responses
from app.modules.auth.public import require_permission
from app.modules.departments.dependencies import DepartmentServiceDep
from app.modules.departments.schemas import (
    DepartmentCreate,
    DepartmentDetail,
    DepartmentResponse,
    DepartmentUpdate,
)

router = APIRouter(prefix="/departments", tags=["departments"])

can_read = Depends(require_permission("employees:read"))
can_write = Depends(require_permission("departments:write"))


@router.get(
    "",
    response_model=list[DepartmentResponse],
    dependencies=[can_read],
    responses=error_responses(),
)
async def list_departments(service: DepartmentServiceDep):
    return await service.list_all()


@router.get(
    "/{department_id}",
    response_model=DepartmentDetail,
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
