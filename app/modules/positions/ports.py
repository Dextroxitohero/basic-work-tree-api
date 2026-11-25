"""Puertos: lo que el servicio necesita de fuera, sin saber quién lo implementa."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from app.modules.positions.models import PositionHistory


class PositionStore(Protocol):
    async def list_by_employee(self, employee_id: UUID) -> Sequence[PositionHistory]: ...
    async def get_current(self, employee_id: UUID) -> PositionHistory | None: ...
    async def get_latest(self, employee_id: UUID) -> PositionHistory | None: ...
    async def save(self, position: PositionHistory) -> PositionHistory: ...


class Employees(Protocol):
    """Lo aporta el módulo employees."""

    async def ensure_exists(self, employee_id: UUID) -> None: ...
    async def ensure_active(self, employee_id: UUID) -> None: ...


class JobTitles(Protocol):
    """Lo aporta el módulo job_titles."""

    async def ensure_assignable(self, job_title_id: UUID) -> None: ...
