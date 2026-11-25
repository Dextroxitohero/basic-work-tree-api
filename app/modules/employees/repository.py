from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.repository import flush
from app.modules.employees.exceptions import EmailAlreadyExistsError
from app.modules.employees.models import Employee
from app.modules.positions.models import PositionHistory

# Número arbitrario que identifica el lock de la jerarquía en PostgreSQL.
_HIERARCHY_LOCK_ID = 7_401


# Constraint de la DB -> error de este módulo.
_CONFLICTS = {"uq_employees_email": EmailAlreadyExistsError}


class EmployeeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _base_query(self) -> Select:
        # Todo EmployeeResponse incluye el puesto actual y su título, así que se cargan siempre.
        return select(Employee).options(
            selectinload(Employee.current_position).selectinload(PositionHistory.job_title)
        )

    async def get_by_id(self, employee_id: UUID) -> Employee | None:
        return await self._session.scalar(self._base_query().where(Employee.id == employee_id))

    async def get_detail(self, employee_id: UUID) -> Employee | None:
        stmt = (
            self._base_query()
            .where(Employee.id == employee_id)
            .options(
                selectinload(Employee.position_history).selectinload(PositionHistory.job_title),
                selectinload(Employee.direct_reports)
                .selectinload(Employee.current_position)
                .selectinload(PositionHistory.job_title),
            )
        )
        return await self._session.scalar(stmt)

    async def list_all(self, *, is_active: bool, email: str | None) -> Sequence[Employee]:
        stmt = self._base_query().where(Employee.is_active == is_active)
        if email is not None:
            stmt = stmt.where(Employee.email == email)
        stmt = stmt.order_by(Employee.last_name, Employee.first_name)
        return (await self._session.scalars(stmt)).all()

    async def list_reports(self, manager_id: UUID) -> Sequence[Employee]:
        stmt = (
            self._base_query()
            .where(Employee.manager_id == manager_id, Employee.is_active)
            .order_by(Employee.last_name, Employee.first_name)
        )
        return (await self._session.scalars(stmt)).all()

    async def list_subtree(self, root_id: UUID) -> Sequence[Employee]:
        """El empleado raíz y todos sus subordinados activos, a cualquier profundidad.

        CTE recursivo (WITH RECURSIVE): un solo query recorre todo el árbol, en vez de
        hacer un query por nivel.
        """
        tree = select(Employee.id).where(Employee.id == root_id).cte("tree", recursive=True)
        tree = tree.union(
            select(Employee.id)
            .join(tree, Employee.manager_id == tree.c.id)
            .where(Employee.is_active)
        )
        stmt = (
            self._base_query()
            .where(Employee.id.in_(select(tree.c.id)))
            .order_by(Employee.last_name, Employee.first_name)
        )
        return (await self._session.scalars(stmt)).all()

    async def get_ancestor_ids(self, employee_id: UUID) -> set[UUID]:
        """IDs de todos los jefes por encima del empleado (jefe, jefe del jefe, ...)."""
        chain = (
            select(Employee.manager_id.label("id"))
            .where(Employee.id == employee_id)
            .cte("chain", recursive=True)
        )
        chain = chain.union(select(Employee.manager_id).join(chain, Employee.id == chain.c.id))
        stmt = select(chain.c.id).where(chain.c.id.is_not(None))
        return set((await self._session.scalars(stmt)).all())

    async def lock_hierarchy(self) -> None:
        """Serializa los cambios de jerarquía hasta el final de la transacción.

        Sin esto, dos requests simultáneos (A jefe de B, y B jefe de A) pasarían cada uno la
        validación de ciclos y juntos crearían uno.
        """
        await self._session.execute(select(func.pg_advisory_xact_lock(_HIERARCHY_LOCK_ID)))

    async def clear_manager(self, manager_id: UUID) -> None:
        await self._session.execute(
            update(Employee).where(Employee.manager_id == manager_id).values(manager_id=None)
        )

    async def save(self, employee: Employee) -> Employee:
        self._session.add(employee)
        await flush(self._session, _CONFLICTS)
        # populate_existing refresca el objeto que ya está en memoria con lo que hay en la DB.
        stmt = (
            self._base_query()
            .where(Employee.id == employee.id)
            .execution_options(populate_existing=True)
        )
        return (await self._session.scalars(stmt)).one()
