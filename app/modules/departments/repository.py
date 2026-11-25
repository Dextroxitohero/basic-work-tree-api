from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.repository import flush
from app.modules.departments.exceptions import DepartmentNameExistsError
from app.modules.departments.models import Department
from app.modules.employees.models import Employee
from app.modules.positions.models import PositionHistory

# Constraint de la DB -> error de este módulo.
_CONFLICTS = {"uq_departments_name": DepartmentNameExistsError}


class DepartmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, department_id: UUID) -> Department | None:
        return await self._session.get(Department, department_id)

    async def get_detail(self, department_id: UUID) -> Department | None:
        # selectinload carga la relación con UN query extra en total, no uno por empleado.
        stmt = (
            select(Department)
            .where(Department.id == department_id)
            .options(
                selectinload(Department.employees)
                .selectinload(Employee.current_position)
                .selectinload(PositionHistory.job_title)
            )
        )
        return await self._session.scalar(stmt)

    async def list_all(self) -> Sequence[Department]:
        return (await self._session.scalars(select(Department).order_by(Department.name))).all()

    async def clear_manager(self, manager_id: UUID) -> None:
        await self._session.execute(
            update(Department).where(Department.manager_id == manager_id).values(manager_id=None)
        )

    async def save(self, department: Department) -> Department:
        self._session.add(department)
        await flush(self._session, _CONFLICTS)
        return department
