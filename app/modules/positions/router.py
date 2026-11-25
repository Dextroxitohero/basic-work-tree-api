from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.responses import error_responses
from app.modules.auth.public import require_permission
from app.modules.positions.dependencies import PositionServiceDep
from app.modules.positions.schemas import PositionCreate, PositionHistoryResponse

# Sub-recurso: un puesto siempre pertenece a un empleado.
router = APIRouter(prefix="/employees/{employee_id}/positions", tags=["positions"])

can_read = Depends(require_permission("employees:read"))
can_write = Depends(require_permission("positions:write"))


@router.get(
    "",
    response_model=list[PositionHistoryResponse],
    dependencies=[can_read],
    responses=error_responses(404),
)
async def list_positions(employee_id: UUID, service: PositionServiceDep):
    return await service.list_history(employee_id)


@router.get(
    "/current",
    response_model=PositionHistoryResponse,
    dependencies=[can_read],
    responses=error_responses(404),
)
async def get_current_position(employee_id: UUID, service: PositionServiceDep):
    return await service.get_current(employee_id)


@router.post(
    "",
    response_model=PositionHistoryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[can_write],
    responses=error_responses(404, 409),
)
async def assign_position(employee_id: UUID, body: PositionCreate, service: PositionServiceDep):
    return await service.assign(employee_id, **body.model_dump())
