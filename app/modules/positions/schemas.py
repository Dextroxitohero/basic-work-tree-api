from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import Field, field_validator

from app.core.schemas import InputModel, OutputModel
from app.modules.job_titles.schemas import JobTitleResponse

# Decimal y no float: con float 0.1 + 0.2 != 0.3, inaceptable para dinero.
# max_digits=12 coincide con NUMERIC(12, 2): un número enorme da 422 y no un error de DB.
Salary = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


class PositionCreate(InputModel):
    job_title_id: UUID  # referencia al catálogo, no texto libre
    salary: Salary
    start_date: date
    notes: Annotated[str | None, Field(max_length=500)] = None

    # field_validator se ejecuta tras la validación del tipo: value ya es un date.
    @field_validator("start_date")
    @classmethod
    def start_date_not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("start_date no puede ser una fecha futura")
        return value


class PositionSummary(OutputModel):
    """Resumen del puesto actual, embebido en EmployeeResponse."""

    job_title: JobTitleResponse
    salary: Decimal  # en JSON se envía como string ("1500.50") para no perder precisión
    start_date: date


class PositionHistoryResponse(OutputModel):
    id: UUID
    employee_id: UUID
    job_title: JobTitleResponse
    salary: Decimal
    start_date: date
    end_date: date | None  # None = puesto actual
    notes: str | None
    created_at: datetime
