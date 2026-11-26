from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Row, Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import (
    Order,
    Page,
    SortSpec,
    apply_page,
    build_page,
    contains_pattern,
    parse_aware_datetime,
)
from app.core.repository import flush
from app.modules.departments.exceptions import DepartmentNameExistsError
from app.modules.departments.models import Department
from app.modules.employees.models import Employee

# Constraint de la DB -> error de este módulo.
_CONFLICTS = {"uq_departments_name": DepartmentNameExistsError}

# Columnas por las que se puede ordenar (?sort=).
_SORTS = {
    spec.name: spec
    for spec in (
        SortSpec("name", Department.name),
        SortSpec("created_at", Department.created_at, parse_aware_datetime),
    )
}


class DepartmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _with_count(self) -> Select:
        """SELECT de departamentos con su número de empleados activos.

        El subquery correlacionado cuenta, para cada departamento, sus empleados activos en
        el mismo query: no hay un query extra por departamento (problema N+1).
        """
        active_employees = (
            select(func.count(Employee.id))
            .where(Employee.department_id == Department.id, Employee.is_active)
            .correlate(Department)
            .scalar_subquery()
        )
        return select(Department, active_employees.label("employee_count"))

    @staticmethod
    def _attach_count(rows: Sequence[Row]) -> list[Department]:
        departments = []
        for department, employee_count in rows:
            department.employee_count = employee_count
            departments.append(department)
        return departments

    async def get_by_id(self, department_id: UUID) -> Department | None:
        return await self._session.get(Department, department_id)

    async def get_detail(self, department_id: UUID) -> Department | None:
        stmt = self._with_count().where(Department.id == department_id)
        departments = self._attach_count((await self._session.execute(stmt)).all())
        return departments[0] if departments else None

    async def list_page(
        self, *, q: str | None, sort: str, order: Order, after: str | None
    ) -> Page[Department]:
        stmt = self._with_count()
        if q is not None:
            stmt = stmt.where(Department.name.ilike(contains_pattern(q), escape="\\"))
        spec = _SORTS[sort]
        stmt = apply_page(stmt, spec=spec, id_column=Department.id, order=order, after=after)
        departments = self._attach_count((await self._session.execute(stmt)).all())
        return build_page(departments, spec=spec, order=order)

    async def clear_manager(self, manager_id: UUID) -> None:
        await self._session.execute(
            update(Department).where(Department.manager_id == manager_id).values(manager_id=None)
        )

    async def save(self, department: Department) -> Department:
        self._session.add(department)
        await flush(self._session, _CONFLICTS)
        # Se vuelve a leer para devolver también employee_count. populate_existing refresca
        # el objeto que ya está en memoria con lo que hay en la DB.
        stmt = (
            self._with_count()
            .where(Department.id == department.id)
            .execution_options(populate_existing=True)
        )
        return self._attach_count((await self._session.execute(stmt)).all())[0]
