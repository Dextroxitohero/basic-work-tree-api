from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from app.modules.positions.exceptions import NoActivePositionError, OverlappingPositionError
from app.modules.positions.models import PositionHistory
from app.modules.positions.ports import Employees, JobTitles, PositionStore


class PositionService:
    def __init__(
        self, positions: PositionStore, employees: Employees, job_titles: JobTitles
    ) -> None:
        self._positions = positions
        self._employees = employees
        self._job_titles = job_titles

    async def list_history(self, employee_id: UUID) -> Sequence[PositionHistory]:
        await self._employees.ensure_exists(employee_id)
        return await self._positions.list_by_employee(employee_id)

    async def get_current(self, employee_id: UUID) -> PositionHistory:
        await self._employees.ensure_exists(employee_id)
        position = await self._positions.get_current(employee_id)
        if position is None:
            raise NoActivePositionError()
        return position

    async def assign(
        self,
        employee_id: UUID,
        *,
        job_title_id: UUID,
        salary: Decimal,
        start_date: date,
        notes: str | None,
    ) -> PositionHistory:
        """Asigna un puesto nuevo y cierra el anterior (todo en la misma transacción)."""
        await self._employees.ensure_active(employee_id)
        await self._job_titles.ensure_assignable(job_title_id)

        latest = await self._positions.get_latest(employee_id)
        if latest is not None:
            # Si el último puesto sigue abierto, el nuevo debe empezar después de su inicio;
            # si ya está cerrado, después de su fin.
            if start_date <= (latest.end_date or latest.start_date):
                raise OverlappingPositionError()
            if latest.end_date is None:
                latest.end_date = start_date - timedelta(days=1)
                # Primero se cierra y luego se inserta: la DB nunca permite dos puestos activos.
                await self._positions.save(latest)

        return await self._positions.save(
            PositionHistory(
                employee_id=employee_id,
                job_title_id=job_title_id,
                salary=salary,
                start_date=start_date,
                notes=notes,
            )
        )
