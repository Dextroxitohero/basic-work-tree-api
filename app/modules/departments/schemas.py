from datetime import datetime
from typing import Annotated, ClassVar
from uuid import UUID

from app.core.schemas import InputModel, OutputModel, PatchModel, text_field
from app.modules.employees.schemas import EmployeeResponse

DepartmentName = Annotated[str, text_field(100)]


class DepartmentCreate(InputModel):
    name: DepartmentName
    manager_id: UUID | None = None


class DepartmentUpdate(PatchModel):
    not_nullable: ClassVar[frozenset[str]] = frozenset({"name"})

    name: DepartmentName | None = None
    manager_id: UUID | None = None


class DepartmentResponse(OutputModel):
    id: UUID
    name: str
    manager_id: UUID | None
    created_at: datetime


class DepartmentDetail(DepartmentResponse):
    employees: list[EmployeeResponse]
