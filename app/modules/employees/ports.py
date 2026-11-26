"""Puertos: lo que el servicio necesita de fuera, sin saber quién lo implementa."""

from collections.abc import Sequence
from datetime import date
from typing import Protocol
from uuid import UUID

from app.core.pagination import Order, Page
from app.modules.employees.models import Employee


class EmployeeStore(Protocol):
    async def get_by_id(self, employee_id: UUID) -> Employee | None: ...
    async def get_detail(self, employee_id: UUID) -> Employee | None: ...
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
    ) -> Page[Employee]: ...
    async def list_reports(self, manager_id: UUID) -> Sequence[Employee]: ...
    async def list_subtree(self, root_id: UUID) -> Sequence[Employee]: ...
    async def get_ancestor_ids(self, employee_id: UUID) -> set[UUID]: ...
    async def lock_hierarchy(self) -> None: ...
    async def clear_manager(self, manager_id: UUID) -> None: ...
    async def save(self, employee: Employee) -> Employee: ...


class Positions(Protocol):
    """Lo aporta el módulo positions."""

    async def close_current(self, employee_id: UUID, end_date: date) -> None: ...


class Departments(Protocol):
    """Lo aporta el módulo departments."""

    async def ensure_exists(self, department_id: UUID) -> None: ...
    async def release_manager(self, employee_id: UUID) -> None: ...
