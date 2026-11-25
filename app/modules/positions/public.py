"""Lo que otros módulos pueden usar de positions."""

from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.positions.ports import PositionStore
from app.modules.positions.repository import PositionRepository


class PositionCloser:
    def __init__(self, positions: PositionStore) -> None:
        self._positions = positions

    async def close_current(self, employee_id: UUID, end_date: date) -> None:
        """Cierra el puesto activo, si lo hay."""
        position = await self._positions.get_current(employee_id)
        if position is not None:
            position.end_date = end_date
            await self._positions.save(position)


def get_position_closer(session: AsyncSession) -> PositionCloser:
    return PositionCloser(PositionRepository(session))
