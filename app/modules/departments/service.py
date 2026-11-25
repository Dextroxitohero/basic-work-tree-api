from collections.abc import Sequence
from typing import Any
from uuid import UUID

from app.modules.departments.exceptions import DepartmentNotFoundError
from app.modules.departments.models import Department
from app.modules.departments.ports import DepartmentStore, Managers


class DepartmentService:
    def __init__(self, departments: DepartmentStore, managers: Managers) -> None:
        self._departments = departments
        self._managers = managers

    async def list_all(self) -> Sequence[Department]:
        return await self._departments.list_all()

    async def get_detail(self, department_id: UUID) -> Department:
        department = await self._departments.get_detail(department_id)
        if department is None:
            raise DepartmentNotFoundError()
        return department

    async def create(self, *, name: str, manager_id: UUID | None) -> Department:
        if manager_id is not None:
            await self._managers.ensure_can_manage(manager_id)
        return await self._departments.save(Department(name=name, manager_id=manager_id))

    async def update(self, department_id: UUID, changes: dict[str, Any]) -> Department:
        department = await self._departments.get_by_id(department_id)
        if department is None:
            raise DepartmentNotFoundError()
        if changes.get("manager_id") is not None:
            await self._managers.ensure_can_manage(changes["manager_id"])
        for field, value in changes.items():
            setattr(department, field, value)
        return await self._departments.save(department)
