from datetime import date, datetime
from typing import Annotated, ClassVar
from uuid import UUID

from pydantic import AfterValidator, EmailStr, field_validator

from app.core.schemas import InputModel, OutputModel, PatchModel, text_field
from app.modules.positions.schemas import PositionHistoryResponse, PositionSummary

PersonName = Annotated[str, text_field(80)]
Phone = Annotated[str, text_field(20)]
# EmailStr solo normaliza el dominio. Pasamos todo a minúsculas para que Ana@x.com y
# ana@x.com cuenten como el mismo email en el UNIQUE de la DB.
Email = Annotated[EmailStr, AfterValidator(str.lower)]


class EmployeeCreate(InputModel):
    first_name: PersonName
    last_name: PersonName
    email: Email
    phone: Phone | None = None
    hire_date: date
    manager_id: UUID | None = None
    department_id: UUID | None = None

    @field_validator("hire_date")
    @classmethod
    def hire_date_not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("hire_date no puede ser una fecha futura")
        return value


class EmployeeUpdate(PatchModel):
    # phone, manager_id y department_id sí aceptan null: sirve para quitar el valor.
    not_nullable: ClassVar[frozenset[str]] = frozenset({"first_name", "last_name", "is_active"})

    first_name: PersonName | None = None
    last_name: PersonName | None = None
    phone: Phone | None = None
    manager_id: UUID | None = None
    department_id: UUID | None = None
    is_active: bool | None = None  # true permite reactivar a un empleado dado de baja


class EmployeeResponse(OutputModel):
    id: UUID
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None
    hire_date: date
    is_active: bool
    manager_id: UUID | None
    department_id: UUID | None
    current_position: PositionSummary | None
    created_at: datetime
    updated_at: datetime


class EmployeeDetail(EmployeeResponse):
    """Respuesta extendida: hereda los campos y agrega los más costosos de cargar."""

    position_history: list[PositionHistoryResponse]
    direct_reports: list[EmployeeResponse]


class EmployeeTreeNode(OutputModel):
    """Nodo del organigrama. Se referencia a sí mismo, por eso es recursivo."""

    employee: EmployeeResponse
    reports: list["EmployeeTreeNode"]
