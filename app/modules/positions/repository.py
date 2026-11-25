from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.repository import flush
from app.modules.positions.exceptions import OverlappingPositionError
from app.modules.positions.models import PositionHistory

# Constraint de la DB -> error de este módulo.
_CONFLICTS = {
    "uq_position_history_employee_id_start_date": OverlappingPositionError,
    "uq_position_history_active": OverlappingPositionError,
}


class PositionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _base_query(self) -> Select:
        return select(PositionHistory).options(selectinload(PositionHistory.job_title))

    async def list_by_employee(self, employee_id: UUID) -> Sequence[PositionHistory]:
        stmt = (
            self._base_query()
            .where(PositionHistory.employee_id == employee_id)
            .order_by(PositionHistory.start_date.desc())
        )
        return (await self._session.scalars(stmt)).all()

    async def get_current(self, employee_id: UUID) -> PositionHistory | None:
        stmt = self._base_query().where(
            PositionHistory.employee_id == employee_id,
            PositionHistory.end_date.is_(None),
        )
        return await self._session.scalar(stmt)

    async def get_latest(self, employee_id: UUID) -> PositionHistory | None:
        """El puesto más reciente, esté abierto o cerrado."""
        stmt = (
            self._base_query()
            .where(PositionHistory.employee_id == employee_id)
            .order_by(PositionHistory.start_date.desc())
            .limit(1)
        )
        return await self._session.scalar(stmt)

    async def save(self, position: PositionHistory) -> PositionHistory:
        self._session.add(position)
        await flush(self._session, _CONFLICTS)
        # Se relee para devolverlo con job_title cargado.
        stmt = (
            self._base_query()
            .where(PositionHistory.id == position.id)
            .execution_options(populate_existing=True)
        )
        return (await self._session.scalars(stmt)).one()
