from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID

from app.core.pagination import Order, Page
from app.modules.employees.directory import EmployeeDirectory
from app.modules.employees.exceptions import CircularManagerReferenceError, EmployeeNotFoundError
from app.modules.employees.models import Employee
from app.modules.employees.ports import Departments, EmployeeStore, Positions


@dataclass
class TreeNode:
    employee: Employee
    reports: list["TreeNode"] = field(default_factory=list)


class EmployeeService:
    """Reglas de negocio de empleados. No conoce HTTP ni SQL."""

    def __init__(
        self,
        employees: EmployeeStore,
        directory: EmployeeDirectory,
        positions: Positions,
        departments: Departments,
    ) -> None:
        self._employees = employees
        self._directory = directory
        self._positions = positions
        self._departments = departments

    async def list_page(
        self,
        *,
        is_active: bool | None,
        email: str | None,
        q: str | None,
        department_id: UUID | None,
        manager_id: UUID | None,
        has_manager: bool | None,
        job_title_id: UUID | None,
        sort: str,
        order: Order,
        after: str | None,
    ) -> Page[Employee]:
        return await self._employees.list_page(
            is_active=is_active,
            email=email,
            q=q,
            department_id=department_id,
            manager_id=manager_id,
            has_manager=has_manager,
            job_title_id=job_title_id,
            sort=sort,
            order=order,
            after=after,
        )

    async def get_detail(self, employee_id: UUID) -> Employee:
        employee = await self._employees.get_detail(employee_id)
        if employee is None:
            raise EmployeeNotFoundError()
        return employee

    async def list_reports(self, employee_id: UUID) -> Sequence[Employee]:
        await self._get(employee_id)
        return await self._employees.list_reports(employee_id)

    async def get_tree(self, employee_id: UUID) -> TreeNode:
        await self._get(employee_id)
        # El repositorio devuelve una lista plana; aquí se arma el árbol en dos pasadas.
        employees = await self._employees.list_subtree(employee_id)
        nodes = {employee.id: TreeNode(employee) for employee in employees}
        for node in nodes.values():
            parent = nodes.get(node.employee.manager_id)
            if parent is not None:
                parent.reports.append(node)
        return nodes[employee_id]

    # El * obliga a pasar los argumentos por nombre: evita confundir first_name con last_name.
    async def create(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        phone: str | None,
        hire_date: date,
        manager_id: UUID | None,
        department_id: UUID | None,
    ) -> Employee:
        if department_id is not None:
            await self._departments.ensure_exists(department_id)
        if manager_id is not None:
            # Un empleado nuevo no tiene subordinados: no puede crear un ciclo.
            await self._directory.ensure_can_manage(manager_id)
        return await self._employees.save(
            Employee(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                hire_date=hire_date,
                manager_id=manager_id,
                department_id=department_id,
            )
        )

    async def update(self, employee_id: UUID, changes: dict[str, Any]) -> Employee:
        """changes contiene SOLO los campos que envió el cliente."""
        employee = await self._get(employee_id)
        if changes.get("department_id") is not None:
            await self._departments.ensure_exists(changes["department_id"])
        if changes.get("manager_id") is not None:
            await self._ensure_valid_manager(employee_id, changes["manager_id"])

        if changes.get("is_active") is False and employee.is_active:
            await self._release_responsibilities(employee_id)
        for name, value in changes.items():
            setattr(employee, name, value)
        return await self._employees.save(employee)

    async def deactivate(self, employee_id: UUID) -> None:
        """Baja lógica. Idempotente: repetirla no cambia nada."""
        employee = await self._get(employee_id)
        if not employee.is_active:
            return
        await self._release_responsibilities(employee_id)
        employee.is_active = False
        await self._employees.save(employee)

    async def _release_responsibilities(self, employee_id: UUID) -> None:
        """Al dar de baja: cierra el puesto y libera a subordinados y departamentos."""
        await self._employees.lock_hierarchy()
        await self._positions.close_current(employee_id, date.today())
        await self._employees.clear_manager(employee_id)
        await self._departments.release_manager(employee_id)

    async def _ensure_valid_manager(self, employee_id: UUID, manager_id: UUID) -> None:
        if manager_id == employee_id:
            raise CircularManagerReferenceError()
        await self._directory.ensure_can_manage(manager_id)
        # Si el empleado ya está por encima del jefe propuesto, se cerraría un ciclo.
        if employee_id in await self._employees.get_ancestor_ids(manager_id):
            raise CircularManagerReferenceError()

    async def _get(self, employee_id: UUID) -> Employee:
        employee = await self._employees.get_by_id(employee_id)
        if employee is None:
            raise EmployeeNotFoundError()
        return employee
