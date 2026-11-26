from datetime import datetime
from typing import Annotated, ClassVar
from uuid import UUID

from app.core.schemas import InputModel, OutputModel, PatchModel, text_field

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
    employee_count: int  # empleados ACTIVOS del departamento
    created_at: datetime
