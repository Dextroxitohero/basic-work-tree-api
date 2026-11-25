"""Lo que otros módulos pueden usar de departments."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.departments.exceptions import DepartmentNotFoundError
from app.modules.departments.ports import DepartmentStore
from app.modules.departments.repository import DepartmentRepository


class DepartmentDirectory:
    def __init__(self, departments: DepartmentStore) -> None:
        self._departments = departments

    async def ensure_exists(self, department_id: UUID) -> None:
        if await self._departments.get_by_id(department_id) is None:
            raise DepartmentNotFoundError()

    async def release_manager(self, employee_id: UUID) -> None:
        """Deja sin encargado los departamentos que dirigía el empleado."""
        await self._departments.clear_manager(employee_id)


def get_department_directory(session: AsyncSession) -> DepartmentDirectory:
    return DepartmentDirectory(DepartmentRepository(session))
