from uuid import UUID

from app.modules.employees.exceptions import (
    EmployeeInactiveError,
    EmployeeNotFoundError,
    InactiveManagerError,
)
from app.modules.employees.ports import EmployeeStore


class EmployeeDirectory:
    """Comprobaciones sobre empleados que comparten varios módulos."""

    def __init__(self, employees: EmployeeStore) -> None:
        self._employees = employees

    async def ensure_exists(self, employee_id: UUID) -> None:
        if await self._employees.get_by_id(employee_id) is None:
            raise EmployeeNotFoundError()

    async def ensure_active(self, employee_id: UUID) -> None:
        # El lock va ANTES de leer, para que nadie dé de baja al empleado mientras lo usamos.
        # Se libera solo al terminar la transacción.
        await self._employees.lock_hierarchy()
        employee = await self._employees.get_by_id(employee_id)
        if employee is None:
            raise EmployeeNotFoundError()
        if not employee.is_active:
            raise EmployeeInactiveError()

    async def ensure_can_manage(self, employee_id: UUID) -> None:
        """Un jefe o encargado debe existir y estar activo."""
        await self._employees.lock_hierarchy()
        manager = await self._employees.get_by_id(employee_id)
        if manager is None:
            raise EmployeeNotFoundError("El jefe indicado no existe")
        if not manager.is_active:
            raise InactiveManagerError()
