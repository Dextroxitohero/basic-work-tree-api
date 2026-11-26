"""Puertos: lo que el servicio necesita de fuera, sin saber quién lo implementa."""

from typing import Protocol
from uuid import UUID

from app.core.pagination import Order, Page
from app.modules.departments.models import Department


class DepartmentStore(Protocol):
    async def get_by_id(self, department_id: UUID) -> Department | None: ...
    async def get_detail(self, department_id: UUID) -> Department | None: ...
    async def list_page(
        self, *, q: str | None, sort: str, order: Order, after: str | None
    ) -> Page[Department]: ...
    async def clear_manager(self, manager_id: UUID) -> None: ...
    async def save(self, department: Department) -> Department: ...


class Managers(Protocol):
    """Lo aporta el módulo employees."""

    async def ensure_can_manage(self, employee_id: UUID) -> None: ...
